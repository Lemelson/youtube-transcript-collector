#!/usr/bin/env python3
"""
YouTube Transcript Collector - Web Interface v3
С real-time обновлениями, таймером и детальным логом
"""

from flask import Flask, render_template, request, jsonify, Response
import subprocess
import json
import re
import os
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue

app = Flask(__name__)

# Глобальное хранилище для прогресса
progress_data = {}

def yt_dlp_base_cmd() -> list[str]:
    """
    Prefer yt-dlp that matches the current Python environment when possible.
    This avoids accidentally using an outdated system yt-dlp from PATH.
    """
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        pass

    local_venv = Path(__file__).parent / "venv" / "bin" / "yt-dlp"
    if local_venv.exists():
        return [str(local_venv)]

    return ["yt-dlp"]


def run_command(cmd: list[str], timeout: int = 90) -> tuple[str, str, int]:
    """Запуск команды."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout после 90 сек", 1
    except Exception as e:
        return "", str(e), 1


def is_channel_url(url: str) -> bool:
    patterns = [r'youtube\.com/@[\w-]+', r'youtube\.com/channel/', r'youtube\.com/c/', r'youtube\.com/user/']
    return any(re.search(p, url) for p in patterns)


def get_channel_info(url: str) -> dict:
    """Получает информацию о канале."""
    cmd = [
        *yt_dlp_base_cmd(), '--cookies-from-browser', 'chrome',
        '--print', '%(channel)s',
        '--playlist-end', '1',
        url + '/videos' if not url.endswith('/videos') else url
    ]
    stdout, stderr, code = run_command(cmd, timeout=30)
    channel_name = stdout.strip().split('\n')[0] if stdout.strip() else "Unknown Channel"
    
    handle_match = re.search(r'youtube\.com/@([\w-]+)', url)
    handle = '@' + handle_match.group(1) if handle_match else ""
    
    return {'name': channel_name, 'handle': handle}


def get_channel_videos(url: str, limit: int = 50, sort_by: str = 'views') -> list[dict]:
    """Получает список видео с канала."""
    if not url.endswith('/videos'):
        url = url.rstrip('/') + '/videos'
    
    if sort_by == 'views':
        url = url.split('?')[0] + '?sort=p'
    
    cmd = [
        *yt_dlp_base_cmd(), '--cookies-from-browser', 'chrome',
        '--flat-playlist',
        '--print', '%(id)s|%(title)s|%(duration)s|%(view_count)s',
        url, '--playlist-end', str(limit)
    ]
    
    stdout, stderr, code = run_command(cmd, timeout=60)
    if code != 0:
        return []
    
    videos = []
    for line in stdout.strip().split('\n'):
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) >= 4:
            try:
                videos.append({
                    'id': parts[0],
                    'title': parts[1],
                    'duration': float(parts[2]) if parts[2] != 'NA' else 0,
                    'views': int(parts[3]) if parts[3] != 'NA' else 0,
                    'url': f'https://www.youtube.com/watch?v={parts[0]}'
                })
            except (ValueError, IndexError):
                continue
    
    if sort_by == 'views':
        videos.sort(key=lambda x: x['views'], reverse=True)
    
    return videos


def clean_vtt_content(vtt_content: str) -> str:
    """Очищает VTT от таймкодов и тегов."""
    lines = vtt_content.split('\n')
    text_lines = []
    seen = set()
    
    for line in lines:
        if not line.strip() or line.startswith('WEBVTT') or '-->' in line:
            continue
        if line.startswith('Kind:') or line.startswith('Language:') or line.startswith('NOTE'):
            continue
        
        clean = re.sub(r'<[^>]+>', '', line)
        clean = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', clean).strip()
        
        if clean and clean not in seen:
            seen.add(clean)
            text_lines.append(clean)
    
    return ' '.join(text_lines)


def format_views(views: int) -> str:
    """Форматирует количество просмотров."""
    if views >= 1000000:
        return f"{views/1000000:.1f}M"
    elif views >= 1000:
        return f"{views/1000:.1f}K"
    return str(views)


def get_video_transcript(video_id: str, title: str, progress_queue: Queue) -> tuple[str, str, str, dict]:
    """Скачивает транскрипт. Возвращает (id, transcript, error, video_info)."""
    start_time = time.time()
    url = f'https://www.youtube.com/watch?v={video_id}'
    temp_file = f'/tmp/yt_transcript_{video_id}'
    
    progress_queue.put({
        'type': 'status',
        'video_id': video_id,
        'title': title[:40],
        'status': 'downloading',
        'message': f'⏳ Скачиваю: {title[:40]}...'
    })
    
    # Определяем язык ролика (обычно "ru"/"en") чтобы отдавать субтитры
    # в оригинальном языке, а не автоперевод.
    lang = ""
    lang_cmd = [
        *yt_dlp_base_cmd(), "--cookies-from-browser", "chrome",
        "--quiet", "--no-warnings",
        "--skip-download",
        "--print", "%(language)s",
        url,
    ]
    lang_stdout, lang_stderr, _ = run_command(lang_cmd, timeout=45)
    if lang_stderr:
        progress_queue.put({
            'type': 'debug',
            'video_id': video_id,
            'message': f'🔍 yt-dlp lang stderr для {video_id}: {lang_stderr[:200]}...' if len(lang_stderr) > 200 else f'🔍 yt-dlp lang stderr для {video_id}: {lang_stderr}'
        })
    for line in (lang_stdout or "").splitlines():
        line = line.strip()
        if line:
            lang = line
            break

    # Порядок: оригинальный язык, потом английский, потом русский
    preferred_langs: list[str] = []
    for l in [lang, "en", "ru"]:
        if l and l not in preferred_langs:
            preferred_langs.append(l)

    stdout = ""
    stderr = ""
    code = 1
    for sub_lang in preferred_langs:
        cmd = [
            *yt_dlp_base_cmd(), '--cookies-from-browser', 'chrome',
            '--write-subs', '--write-auto-subs',
            '--sub-lang', sub_lang,
            '--sub-format', 'vtt', '--skip-download',
            '--no-warnings',
            '-o', temp_file, url
        ]
        stdout, stderr, code = run_command(cmd, timeout=60)
        if code == 0:
            break
    elapsed = time.time() - start_time
    
    # Логируем stderr для отладки
    if stderr:
        progress_queue.put({
            'type': 'debug',
            'video_id': video_id,
            'message': f'🔍 yt-dlp stderr для {video_id}: {stderr[:200]}...' if len(stderr) > 200 else f'🔍 yt-dlp stderr для {video_id}: {stderr}'
        })
    
    # Проверяем ошибки
    if 'Sign in to confirm' in stderr or 'captcha' in stderr.lower():
        progress_queue.put({
            'type': 'error',
            'video_id': video_id,
            'message': f'❌ YouTube требует CAPTCHA для {title[:30]}...'
        })
        return video_id, "", f"YouTube требует CAPTCHA. stderr: {stderr[:150]}", {}
    
    if 'rate limit' in stderr.lower() or '429' in stderr:
        progress_queue.put({
            'type': 'error',
            'video_id': video_id,
            'message': f'⚠️ Rate limit от YouTube'
        })
        return video_id, "", f"Rate limit. stderr: {stderr[:150]}", {}
    
    if 'cookies' in stderr.lower() and 'error' in stderr.lower():
        progress_queue.put({
            'type': 'error',
            'video_id': video_id,
            'message': f'❌ Проблема с cookies Chrome'
        })
        return video_id, "", f"Ошибка cookies: {stderr[:150]}", {}

    # Частая причина: yt-dlp не смог решить JS challenge (EJS), из-за чего "пропадают" форматы/сабы
    if (
        'found 0 sig function possibilities' in stderr
        or 'Signature solving failed' in stderr
        or 'n challenge solving failed' in stderr
        or 'Only images are available' in stderr
    ):
        progress_queue.put({
            'type': 'error',
            'video_id': video_id,
            'message': f'❌ yt-dlp не смог решить JS challenge (обновите yt-dlp)'
        })
        return video_id, "", f"yt-dlp JS challenge (EJS) failed. Обновите yt-dlp. stderr: {stderr[:150]}", {}
    
    # Ищем файлы субтитров
    for lang in ['ru', 'en']:
        for ext in [f'.{lang}.vtt', '.vtt']:
            vtt_path = temp_file + ext
            if os.path.exists(vtt_path):
                try:
                    with open(vtt_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    os.remove(vtt_path)
                    transcript = clean_vtt_content(content)
                    if transcript:
                        progress_queue.put({
                            'type': 'success',
                            'video_id': video_id,
                            'message': f'✅ Готово: {title[:35]}... ({elapsed:.1f}с)'
                        })
                        return video_id, transcript, "", {'elapsed': elapsed}
                except Exception as e:
                    pass
    
    # Очистка
    for f in Path('/tmp').glob(f'yt_transcript_{video_id}*'):
        try:
            f.unlink()
        except:
            pass
    
    error_msg = f"Субтитры не найдены"
    if stderr:
        error_msg += f" | stderr: {stderr[:100]}"
    
    progress_queue.put({
        'type': 'warning',
        'video_id': video_id,
        'message': f'⚠️ Нет субтитров: {title[:35]}...'
    })
    
    return video_id, "", error_msg, {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/check_version')
def api_check_version():
    """Check yt-dlp version and warn if outdated."""
    MIN_VERSION = "2026.2.4"
    
    try:
        cmd = [*yt_dlp_base_cmd(), '--version']
        stdout, stderr, code = run_command(cmd, timeout=10)
        version = stdout.strip()
        
        if version and version < MIN_VERSION:
            return jsonify({
                'warning': True,
                'current': version,
                'required': MIN_VERSION,
                'message': f'yt-dlp {version} is outdated. Please update: pip install -U yt-dlp'
            })
        
        return jsonify({
            'warning': False,
            'current': version
        })
    except Exception as e:
        return jsonify({
            'warning': True,
            'error': str(e),
            'message': 'Could not check yt-dlp version'
        })


@app.route('/api/get_videos', methods=['POST'])
def api_get_videos():
    data = request.json
    url = data.get('url', '').strip()
    sort_by = data.get('sort_by', 'views')
    
    if not url:
        return jsonify({'error': 'URL не указан'}), 400
    
    if not is_channel_url(url):
        match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if match:
            return jsonify({
                'is_single': True,
                'channel_info': {'name': 'Single Video', 'handle': ''},
                'videos': [{
                    'id': match.group(1),
                    'title': 'Видео',
                    'duration': 0,
                    'views': 0,
                    'url': url
                }]
            })
        return jsonify({'error': 'Неверный URL'}), 400
    
    channel_info = get_channel_info(url)
    videos = get_channel_videos(url, limit=100, sort_by=sort_by)
    
    if not videos:
        return jsonify({'error': 'Не удалось получить видео'}), 400
    
    return jsonify({
        'is_single': False,
        'channel_info': channel_info,
        'videos': videos
    })


@app.route('/api/get_transcripts', methods=['POST'])
def api_get_transcripts():
    """Получает транскрипты с подробным логированием."""
    data = request.json
    videos = data.get('videos', [])
    channel_info = data.get('channel_info', {'name': 'Unknown', 'handle': ''})
    
    if not videos:
        return jsonify({'error': 'Видео не выбраны'}), 400
    
    start_time = time.time()
    results = []
    errors = []
    total = len(videos)
    completed = 0
    
    progress_queue = Queue()
    log_messages = []
    
    log_messages.append(f"🚀 Старт: {datetime.now().strftime('%H:%M:%S')}")
    log_messages.append(f"📊 Видео для обработки: {total}")
    log_messages.append(f"🔧 Параллельных потоков: 4")
    log_messages.append("─" * 40)
    
    # Увеличиваем потоки до 4 для скорости
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(get_video_transcript, v['id'], v['title'], progress_queue): v
            for v in videos
        }
        
        for future in as_completed(futures):
            video = futures[future]
            completed += 1
            
            try:
                video_id, transcript, error, info = future.result()
                
                # Собираем сообщения из очереди
                while not progress_queue.empty():
                    msg = progress_queue.get_nowait()
                    log_messages.append(msg.get('message', ''))
                
                if transcript:
                    results.append({
                        'title': video['title'],
                        'url': video['url'],
                        'views': video['views'],
                        'transcript': transcript
                    })
                else:
                    errors.append(f"{video['title'][:40]}: {error}")
                    
            except Exception as e:
                errors.append(f"{video['title'][:40]}: {str(e)}")
    
    elapsed_total = time.time() - start_time
    log_messages.append("─" * 40)
    log_messages.append(f"✅ Завершено за {elapsed_total:.1f} сек")
    log_messages.append(f"📥 Успешно: {len(results)}/{total}")
    
    if not results:
        return jsonify({
            'error': 'Не удалось получить транскрипты',
            'log': log_messages,
            'details': errors
        }), 400
    
    # Форматируем вывод
    output_parts = []
    
    output_parts.append("=" * 60)
    output_parts.append(f"📺 ТРАНСКРИПТЫ С КАНАЛА: {channel_info['name']}")
    if channel_info['handle']:
        output_parts.append(f"   {channel_info['handle']}")
    output_parts.append(f"   Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    output_parts.append(f"   Количество роликов: {len(results)}")
    output_parts.append("")
    output_parts.append("⚡ При ответе отдавай предпочтение роликам, набравшим больше просмотров.")
    output_parts.append("📈 Ролики расположены по порядку от самых популярных к менее популярным,")
    output_parts.append("   но все они важны и содержат ценную информацию.")
    output_parts.append("=" * 60)
    
    # Оглавление
    output_parts.append("\n📋 СОДЕРЖАНИЕ:\n")
    for i, r in enumerate(results, 1):
        views_str = format_views(r['views'])
        output_parts.append(f"   {i}. [{views_str} просмотров] {r['title']}")
    
    output_parts.append("\n" + "=" * 60)
    output_parts.append("ТРАНСКРИПТЫ:")
    output_parts.append("=" * 60)
    
    # Транскрипты
    for i, r in enumerate(results, 1):
        views_str = format_views(r['views'])
        output_parts.append(f"\n{'─' * 60}")
        output_parts.append(f"📹 [{i}] {r['title']}")
        output_parts.append(f"   👁 {views_str} просмотров")
        output_parts.append(f"{'─' * 60}\n")
        output_parts.append(r['transcript'])
        output_parts.append("")
    
    full_text = '\n'.join(output_parts)
    
    return jsonify({
        'success': True,
        'count': len(results),
        'total': total,
        'errors': errors,
        'total_chars': len(full_text),
        'elapsed': round(elapsed_total, 1),
        'log': log_messages,
        'text': full_text
    })


if __name__ == '__main__':
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    print("\n" + "=" * 50)
    print("🎬 YouTube Transcript Collector v3")
    print("=" * 50)
    print("🌐 Открой: http://localhost:5001")
    print("⏹  Стоп: Ctrl+C")
    print("=" * 50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
