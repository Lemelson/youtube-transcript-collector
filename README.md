# 🎬 YouTube Transcript Collector

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web_App-green?logo=flask)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)

**Collect YouTube transcripts from any channel for AI processing**

[🚀 Quick Start](#-quick-start) • [📖 Usage](#-usage) • [🛠 Installation](#-installation) • [🇷🇺 Русская версия](#-русская-версия)

</div>

---

## ✨ Features

- 🌐 **Web Interface** — beautiful UI for collecting transcripts
- 💻 **CLI Version** — for power users and automation
- 🔍 **Filters** — by duration, views, video count
- 📊 **Sorting** — by popularity or upload date
- 🍪 **Cookie Support** — uses Chrome cookies to bypass restrictions
- 🌍 **Smart Language Detection** — auto-detects original video language
- ⚡ **Parallel Download** — 4 threads for faster processing
- 📋 **Copy/Download** — to clipboard or `.txt` file
- 🔧 **Debug Panel** — detailed logs for troubleshooting
- 🌐 **Bilingual UI** — English/Russian interface switcher

---

## ⚠️ Important: Keep yt-dlp Updated!

This tool relies on [yt-dlp](https://github.com/yt-dlp/yt-dlp) which must be kept up-to-date. YouTube frequently changes its protection (JS challenges), and outdated yt-dlp versions will fail.

```bash
# Update yt-dlp regularly:
pip install -U yt-dlp
```

The app will warn you if your yt-dlp version is outdated.

---

## 🚀 Quick Start

### Option 1: Launch Script (recommended)

```bash
cd /path/to/youtube-transcript-collector
./start.sh
```

### Option 2: Manual

```bash
cd /path/to/youtube-transcript-collector
source venv/bin/activate
python3 app.py
```

### Then open in browser:

```
http://localhost:5001
```

### To stop:

Press `Ctrl+C` in terminal.

---

## 📖 Usage

### Web Interface

1. **Paste URL** of a channel (`youtube.com/@channel`) or video
2. **Set filters**: 
   - Number of videos (1-50)
   - Sort by (views / date)
   - Max/min duration
   - Minimum views
3. **Select videos** from the loaded list
4. **Click "Get Transcripts"**
5. **Copy or download** the result

### Command Line (CLI)

```bash
# Activate virtual environment
source venv/bin/activate

# Single video:
python3 yt_transcripts.py "https://www.youtube.com/watch?v=VIDEO_ID" --copy

# Top 10 videos from channel:
python3 yt_transcripts.py "https://www.youtube.com/@ChannelName" --top 10

# With filters:
python3 yt_transcripts.py "URL" --top 20 --max-duration 30 --min-views 50000 -o result.txt
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--top N` | Number of videos to process |
| `--max-duration N` | Maximum duration (minutes) |
| `--min-duration N` | Minimum duration (minutes) |
| `--min-views N` | Minimum view count |
| `--copy` | Copy result to clipboard |
| `-o FILE` | Save to file |

---

## 🛠 Installation

### Requirements

- Python 3.9+
- Google Chrome (for cookies)
- yt-dlp (latest version)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Lemelson/youtube-transcript-collector.git
cd youtube-transcript-collector

# 2. Install yt-dlp
brew install yt-dlp   # macOS
# or
pip install yt-dlp    # any OS

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# or venv\Scripts\activate   # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run
./start.sh
# or
python3 app.py
```

---

## 📁 Project Structure

```
youtube-transcript-collector/
├── 📄 app.py               # Flask web server
├── 📄 yt_transcripts.py    # CLI version
├── 📄 start.sh             # Quick launch script
├── 📄 requirements.txt     # Python dependencies
├── 📁 templates/
│   └── index.html          # Web interface (EN/RU)
├── 📁 venv/                # Virtual environment (not in git)
├── 📄 README.md            # Documentation
├── 📄 LICENSE              # MIT license
└── 📄 .gitignore           # Ignored files
```

---

## 🔧 Troubleshooting

### "Failed to get transcripts"

**Possible causes:**

1. **Outdated yt-dlp** — YouTube frequently changes protection. Update: `pip install -U yt-dlp`
2. **YouTube requires CAPTCHA** — open YouTube in Chrome and pass verification
3. **Subtitles disabled by author** — some videos don't have subtitles
4. **Cookies problem** — close Chrome completely and try again
5. **Rate limit** — YouTube throttled requests, wait 5-10 minutes

### "yt-dlp JS challenge failed" (EJS)

Most common issue! YouTube updated protection and your yt-dlp can't bypass it.

```bash
# Update yt-dlp to latest version:
source venv/bin/activate
pip install -U yt-dlp

# Check version (should be >= 2026.2.4):
python -m yt_dlp --version
```

### Debug Panel

On error, the debug panel stays open showing:
- Detailed logs of each step
- yt-dlp responses
- Possible causes of the problem

---

## 🤝 Contributing

Pull requests welcome! For major changes, please open an issue first.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<br>

# 🇷🇺 Русская версия

## ✨ Возможности

- 🌐 **Веб-интерфейс** — удобный UI для сбора транскриптов
- 💻 **CLI версия** — для продвинутых пользователей и автоматизации
- 🔍 **Фильтры** — по длительности, просмотрам, количеству видео
- 📊 **Сортировка** — по популярности или дате публикации
- 🍪 **Поддержка Cookie** — использует cookies Chrome для обхода ограничений
- 🌍 **Умный выбор языка** — автоматически определяет язык видео
- ⚡ **Параллельная загрузка** — 4 потока для быстрой работы
- 📋 **Копирование/Скачивание** — в буфер обмена или `.txt` файл
- 🔧 **Debug-панель** — подробные логи для диагностики
- 🌐 **Двуязычный интерфейс** — переключатель EN/RU

---

## ⚠️ Важно: Обновляйте yt-dlp!

Этот инструмент использует [yt-dlp](https://github.com/yt-dlp/yt-dlp), который необходимо поддерживать в актуальном состоянии. YouTube часто меняет защиту (JS challenges), и устаревшие версии yt-dlp перестают работать.

```bash
# Регулярно обновляйте yt-dlp:
pip install -U yt-dlp
```

Приложение предупредит вас, если версия yt-dlp устарела.

---

## � Быстрый старт

```bash
cd /path/to/youtube-transcript-collector
./start.sh
```

Затем откройте в браузере: **http://localhost:5001**

Для остановки: `Ctrl+C`

---

## 📖 Использование

### Веб-интерфейс

1. **Вставь ссылку** на канал или видео
2. **Настрой фильтры**: количество, длительность, просмотры
3. **Выбери видео** из списка
4. **Нажми "Get Transcripts"**
5. **Скопируй или скачай** результат

### Командная строка

```bash
source venv/bin/activate

# Один ролик:
python3 yt_transcripts.py "https://www.youtube.com/watch?v=VIDEO_ID" --copy

# Топ-10 с канала:
python3 yt_transcripts.py "https://www.youtube.com/@ChannelName" --top 10
```

---

## 🔧 Решение проблем

### "Не удалось получить транскрипты"

1. **Устаревший yt-dlp** — обновите: `pip install -U yt-dlp`
2. **YouTube требует CAPTCHA** — пройдите проверку в Chrome
3. **Субтитры отключены** — автор отключил субтитры
4. **Проблема с cookies** — закройте Chrome и попробуйте снова
5. **Rate limit** — подождите 5-10 минут

### "yt-dlp JS challenge failed"

Самая частая причина! YouTube обновил защиту.

```bash
source venv/bin/activate
pip install -U yt-dlp
python -m yt_dlp --version  # должно быть >= 2026.2.4
```

---

<div align="center">

**Made with ❤️ for AI enthusiasts**

⭐ If you find this useful — star the repo!

</div>
