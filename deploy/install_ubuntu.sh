#!/bin/bash
# Скрипт установки Shorts News на Ubuntu сервер

set -e

echo "🚀 Установка Shorts News Bot..."

# Обновление системы
echo "📦 Обновление пакетов системы..."
sudo apt update
sudo apt upgrade -y

# Установка зависимостей
echo "📦 Установка системных зависимостей..."
sudo apt install -y python3 python3-pip python3-venv git ffmpeg chromium-browser chromium-chromedriver

# Создание пользователя (опционально)
if ! id "dzianis" &>/dev/null; then
    echo "👤 Создание пользователя dzianis..."
    sudo useradd -m -s /bin/bash dzianis
    sudo usermod -aG sudo dzianis
fi

# Переход в домашнюю директорию
cd /home/dzianis

# Клонирование репозитория (замените URL на ваш)
echo "📁 Клонирование проекта..."
if [ -d "shorts_news" ]; then
    echo "Директория уже существует, обновляем..."
    cd shorts_news
    git pull
else
    git clone https://github.com/YOUR_USERNAME/shorts_news.git
    cd shorts_news
fi

# Создание виртуального окружения
echo "🐍 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Установка Python зависимостей
echo "📦 Установка Python пакетов..."
pip install --upgrade pip
pip install -r requirements.txt

# Создание необходимых директорий
echo "📁 Создание рабочих директорий..."
mkdir -p resources/music
mkdir -p resources/fonts
mkdir -p resources/logos
mkdir -p resources/media/news
mkdir -p outputs
mkdir -p temp
mkdir -p logs
mkdir -p data

# Копирование примера конфигурации
if [ ! -f ".env" ]; then
    echo "⚙️ Создание .env файла..."
    echo "# Telegram Bot Configuration" > .env
    echo "TELEGRAM_BOT_TOKEN=your_bot_token_here" >> .env
    echo "TELEGRAM_CHANNEL_ID=@your_channel" >> .env
    echo "TELEGRAM_ADMIN_GROUP_ID=-your_group_id" >> .env
    echo "TELEGRAM_PUBLISH_CHANNEL_ID=@your_publish_channel" >> .env
    echo "" >> .env
    echo "# Google AI Configuration" >> .env
    echo "GEMINI_API_KEY=your_gemini_api_key_here" >> .env
    echo "" >> .env
    echo "# YouTube Configuration" >> .env
    echo "# Place your client_secret.json in config/ directory" >> .env
    echo "" >> .env
    echo "❗ ВНИМАНИЕ: Отредактируйте файл .env с вашими API ключами!"
    echo "nano .env"
fi

# Установка прав
sudo chown -R dzianis:dzianis /home/dzianis/shorts_news

# Создание systemd service
echo "🔧 Создание systemd сервиса..."
sudo tee /etc/systemd/system/shorts-news.service > /dev/null <<EOF
[Unit]
Description=Shorts News - AI News Video Generator
After=network.target

[Service]
Type=simple
User=dzianis
WorkingDirectory=/home/dzianis/shorts_news
Environment=PATH=/home/dzianis/shorts_news/venv/bin
Environment=DISPLAY=:99
ExecStart=/home/dzianis/shorts_news/venv/bin/python channel_monitor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd
sudo systemctl daemon-reload

echo "✅ Установка завершена!"
echo ""
echo "🔧 Следующие шаги:"
echo "1. Отредактируйте .env файл: sudo -u dzianis nano /home/dzianis/shorts_news/.env"
echo "2. Добавьте музыкальные файлы в: /home/dzianis/shorts_news/resources/music/"
echo "3. Добавьте шрифты в: /home/dzianis/shorts_news/resources/fonts/"
echo "4. Добавьте YouTube credentials JSON файл: config/client_secret.json"
echo "5. Запустите сервис: sudo systemctl enable shorts-news && sudo systemctl start shorts-news"
echo "6. Проверьте статус: sudo systemctl status shorts-news"
echo "7. Просмотр логов: sudo journalctl -u shorts-news -f"
echo ""
echo "📚 Подробная документация в README.md"

