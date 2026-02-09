#!/bin/bash
# Быстрый запуск YouTube Transcript Collector

cd "$(dirname "$0")"

# Активируем виртуальное окружение
source venv/bin/activate

echo ""
echo "=============================================="
echo "🎬 YouTube Transcript Collector"
echo "=============================================="
echo "🌐 Открой в браузере: http://localhost:5847"
echo "⏹  Для остановки нажми Ctrl+C"
echo "=============================================="
echo ""

python3 app.py
