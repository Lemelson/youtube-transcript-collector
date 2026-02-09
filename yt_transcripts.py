#!/usr/bin/env python3
"""
YouTube Transcript Collector
Собирает транскрипты с YouTube каналов и видео с фильтрами по длительности и просмотрам.

Использование:
    # Один ролик:
    python yt_transcripts.py "https://www.youtube.com/watch?v=VIDEO_ID"
    
    # Канал (топ-20 видео):
    python yt_transcripts.py "https://www.youtube.com/@ChannelName" --top 20
    
    # С фильтрами:
    python yt_transcripts.py "https://www.youtube.com/@ChannelName" --top 20 --max-duration 40 --min-views 10000
"""

import subprocess
import json
import re
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


def yt_dlp_base_cmd() -> list[str]:
    """
    Prefer yt-dlp that matches the current Python environment when possible.
    Fallback to the repo venv's yt-dlp if present; else use PATH.
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


def run_command(cmd: list[str], timeout: int = 120) -> tuple[str, str, int]:
    """Запуск команды и возврат stdout, stderr, return code."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1


def is_channel_url(url: str) -> bool:
    """Проверяет, является ли URL ссылкой на канал."""
    channel_patterns = [
        r'youtube\.com/@[\w-]+',
        r'youtube\.com/channel/',
        r'youtube\.com/c/',
        r'youtube\.com/user/',
    ]
    return any(re.search(pattern, url) for pattern in channel_patterns)


def get_channel_videos(url: str, limit: int = 20) -> list[dict]:
    """Получает список видео с канала."""
    print(f"📺 Получаю список видео с канала (лимит: {limit})...")
    
    # Добавляем /videos если это просто ссылка на канал
    if not url.endswith('/videos'):
        if url.endswith('/'):
            url = url + 'videos'
        else:
            url = url + '/videos'
    
    cmd = [
        *yt_dlp_base_cmd(),
        '--cookies-from-browser', 'chrome',
        '--flat-playlist',
        '--print', '%(id)s|%(title)s|%(duration)s|%(view_count)s',
        url,
        '--playlist-end', str(limit * 2)  # берём больше, чтобы потом отфильтровать
    ]
    
    stdout, stderr, code = run_command(cmd, timeout=120)
    
    if code != 0:
        print(f"❌ Ошибка получения списка видео: {stderr}")
        return []
    
    videos = []
    for line in stdout.strip().split('\n'):
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) >= 4:
            try:
                video = {
                    'id': parts[0],
                    'title': parts[1],
                    'duration': float(parts[2]) if parts[2] != 'NA' else 0,
                    'views': int(parts[3]) if parts[3] != 'NA' else 0,
                    'url': f'https://www.youtube.com/watch?v={parts[0]}'
                }
                videos.append(video)
            except (ValueError, IndexError):
                continue
    
    return videos


def filter_videos(videos: list[dict], 
                  max_duration_min: int = None,
                  min_duration_min: int = None,
                  min_views: int = None,
                  sort_by: str = 'views') -> list[dict]:
    """Фильтрует и сортирует видео."""
    filtered = videos.copy()
    
    if max_duration_min:
        max_seconds = max_duration_min * 60
        filtered = [v for v in filtered if v['duration'] <= max_seconds]
    
    if min_duration_min:
        min_seconds = min_duration_min * 60
        filtered = [v for v in filtered if v['duration'] >= min_seconds]
    
    if min_views:
        filtered = [v for v in filtered if v['views'] >= min_views]
    
    # Сортировка
    if sort_by == 'views':
        filtered.sort(key=lambda x: x['views'], reverse=True)
    elif sort_by == 'duration':
        filtered.sort(key=lambda x: x['duration'], reverse=True)
    
    return filtered


def clean_vtt_content(vtt_content: str) -> str:
    """Очищает VTT контент от таймкодов и тегов, оставляя только текст."""
    lines = vtt_content.split('\n')
    text_lines = []
    seen_lines = set()  # Для удаления дубликатов
    
    for line in lines:
        # Пропускаем заголовки и пустые строки
        if not line.strip():
            continue
        if line.startswith('WEBVTT'):
            continue
        if line.startswith('Kind:') or line.startswith('Language:'):
            continue
        # Пропускаем таймкоды
        if '-->' in line:
            continue
        # Пропускаем строки с только пробелами или NOTE
        if line.strip() == '' or line.startswith('NOTE'):
            continue
        
        # Удаляем HTML-теги
        clean_line = re.sub(r'<[^>]+>', '', line)
        # Удаляем таймкоды внутри текста вида <00:00:00.000>
        clean_line = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', clean_line)
        clean_line = clean_line.strip()
        
        if clean_line and clean_line not in seen_lines:
            seen_lines.add(clean_line)
            text_lines.append(clean_line)
    
    return ' '.join(text_lines)


def get_video_transcript(video_id: str, title: str = "") -> tuple[str, str]:
    """Скачивает транскрипт для одного видео."""
    url = f'https://www.youtube.com/watch?v={video_id}'
    temp_file = f'/tmp/yt_transcript_{video_id}'

    # Один запуск yt-dlp: качаем ru+en субтитры и сохраняем info.json,
    # из которого берём язык ролика.
    cmd = [
        *yt_dlp_base_cmd(),
        '--cookies-from-browser', 'chrome',
        '--write-info-json',
        '--write-subs', '--write-auto-subs',
        '--sub-lang', 'ru,en',
        '--sub-format', 'vtt',
        '--skip-download',
        '--no-warnings', '--no-progress',
        '-o', temp_file,
        url
    ]

    stdout, stderr, code = run_command(cmd, timeout=90)
    lang = ""
    info_json_path = temp_file + ".info.json"
    if os.path.exists(info_json_path):
        try:
            with open(info_json_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            lang = (info.get("language") or "").strip()
        except Exception:
            pass
        try:
            os.remove(info_json_path)
        except OSError:
            pass

    preferred_files: list[str] = []
    if lang:
        preferred_files.append(f'.{lang}.vtt')
    preferred_files.extend(['.en.vtt', '.ru.vtt', '.vtt'])

    for ext in preferred_files:
        vtt_path = temp_file + ext
        if os.path.exists(vtt_path):
            with open(vtt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            try:
                os.remove(vtt_path)
            except OSError:
                pass
            return video_id, clean_vtt_content(content)

    # Cleanup any leftover temp files
    for f in Path('/tmp').glob(f'yt_transcript_{video_id}*'):
        try:
            f.unlink()
        except OSError:
            pass
    
    return video_id, ""


def download_transcripts(videos: list[dict], max_workers: int = 4) -> dict[str, str]:
    """Скачивает транскрипты для списка видео параллельно."""
    transcripts = {}
    total = len(videos)
    
    print(f"\n📥 Скачиваю транскрипты для {total} видео...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(get_video_transcript, v['id'], v['title']): v 
            for v in videos
        }
        
        for i, future in enumerate(as_completed(futures), 1):
            video = futures[future]
            try:
                video_id, transcript = future.result()
                if transcript:
                    transcripts[video_id] = transcript
                    print(f"  ✅ [{i}/{total}] {video['title'][:50]}...")
                else:
                    print(f"  ⚠️  [{i}/{total}] Нет субтитров: {video['title'][:50]}...")
            except Exception as e:
                print(f"  ❌ [{i}/{total}] Ошибка: {video['title'][:50]} - {e}")
    
    return transcripts


def format_duration(seconds: float) -> str:
    """Форматирует длительность в минуты:секунды."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def main():
    parser = argparse.ArgumentParser(
        description='📝 YouTube Transcript Collector - Собирает транскрипты с YouTube'
    )
    parser.add_argument('url', help='URL видео или канала')
    parser.add_argument('--top', type=int, default=10, 
                        help='Количество видео для обработки (по умолчанию: 10)')
    parser.add_argument('--max-duration', type=int, default=None,
                        help='Максимальная длительность видео в минутах')
    parser.add_argument('--min-duration', type=int, default=None,
                        help='Минимальная длительность видео в минутах')
    parser.add_argument('--min-views', type=int, default=None,
                        help='Минимальное количество просмотров')
    parser.add_argument('--sort', choices=['views', 'duration'], default='views',
                        help='Сортировка: views (по просмотрам) или duration (по длительности)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Имя выходного файла (по умолчанию: автоматически)')
    parser.add_argument('--copy', action='store_true',
                        help='Скопировать результат в буфер обмена (macOS)')
    parser.add_argument('--workers', type=int, default=4,
                        help='Количество параллельных потоков (по умолчанию: 4)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📝 YouTube Transcript Collector")
    print("=" * 60)
    
    # Определяем тип URL
    if is_channel_url(args.url):
        print(f"\n🔗 Обнаружен канал: {args.url}")
        
        # Получаем список видео
        videos = get_channel_videos(args.url, args.top * 3)
        
        if not videos:
            print("❌ Не удалось получить список видео с канала")
            sys.exit(1)
        
        print(f"   Найдено видео: {len(videos)}")
        
        # Фильтруем
        videos = filter_videos(
            videos,
            max_duration_min=args.max_duration,
            min_duration_min=args.min_duration,
            min_views=args.min_views,
            sort_by=args.sort
        )
        
        # Ограничиваем количество
        videos = videos[:args.top]
        
        if not videos:
            print("❌ После фильтрации не осталось видео")
            sys.exit(1)
        
        print(f"\n📋 Выбрано {len(videos)} видео:")
        for i, v in enumerate(videos, 1):
            duration = format_duration(v['duration'])
            views = f"{v['views']:,}".replace(',', ' ')
            print(f"   {i}. [{duration}] {views} views - {v['title'][:45]}...")
        
    else:
        # Одно видео
        print(f"\n🔗 Обнаружено видео: {args.url}")
        video_id_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', args.url)
        if not video_id_match:
            print("❌ Не удалось извлечь ID видео")
            sys.exit(1)
        
        video_id = video_id_match.group(1)
        videos = [{
            'id': video_id,
            'title': 'Single Video',
            'duration': 0,
            'views': 0,
            'url': args.url
        }]
    
    # Скачиваем транскрипты
    transcripts = download_transcripts(videos, max_workers=max(1, min(10, args.workers)))
    
    if not transcripts:
        print("\n❌ Не удалось получить ни одного транскрипта")
        sys.exit(1)
    
    # Формируем итоговый текст
    output_parts = []
    for video in videos:
        if video['id'] in transcripts:
            output_parts.append(f"\n{'='*60}")
            output_parts.append(f"📹 {video['title']}")
            output_parts.append(f"🔗 {video['url']}")
            output_parts.append(f"{'='*60}\n")
            output_parts.append(transcripts[video['id']])
            output_parts.append("\n")
    
    output_text = '\n'.join(output_parts)
    
    # Определяем имя файла
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"transcripts_{timestamp}.txt"
    
    # Сохраняем файл
    output_path = Path(output_file)
    output_path.write_text(output_text, encoding='utf-8')
    
    print(f"\n{'='*60}")
    print(f"✅ Готово!")
    print(f"   📁 Файл: {output_path.absolute()}")
    print(f"   📊 Видео с транскриптами: {len(transcripts)}/{len(videos)}")
    print(f"   📝 Размер: {len(output_text):,} символов")
    
    # Копируем в буфер если нужно
    if args.copy:
        try:
            subprocess.run(['pbcopy'], input=output_text.encode('utf-8'), check=True)
            print(f"   📋 Скопировано в буфер обмена!")
        except Exception as e:
            print(f"   ⚠️  Не удалось скопировать в буфер: {e}")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
