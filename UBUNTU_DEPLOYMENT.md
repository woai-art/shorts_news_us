# 🐧 Развёртывание Shorts News на Ubuntu Server

Руководство по установке и настройке бота на Ubuntu-сервере с использованием systemd.

## 📋 Предварительные требования

- Ubuntu 20.04 LTS или выше
- Root доступ или sudo привилегии
- Git установлен
- Интернет соединение

## 🚀 Быстрая установка

### 1. Клонирование репозитория

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/shorts_news.git
cd shorts_news
```

### 2. Запуск скрипта установки

```bash
chmod +x deploy/install_ubuntu.sh
./deploy/install_ubuntu.sh
```

Скрипт автоматически:
- Обновит систему
- Установит Python 3, pip, venv, git, ffmpeg, chromium
- Создаст виртуальное окружение
- Установит Python зависимости
- Создаст необходимые директории
- Настроит systemd сервис

### 3. Настройка конфигурации

```bash
nano .env
```

Заполните:
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel
TELEGRAM_ADMIN_GROUP_ID=-your_group_id
TELEGRAM_PUBLISH_CHANNEL_ID=@your_publish_channel

# Google AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# YouTube Configuration
# Place your client_secret.json in config/ directory
```

### 4. Добавление ресурсов

```bash
# Музыка (mp3 файлы)
cp /path/to/music/*.mp3 resources/music/

# Шрифты (ttf файлы)
cp /path/to/fonts/*.ttf resources/fonts/

# YouTube credentials
cp /path/to/client_secret.json config/client_secret.json
```

### 5. Запуск сервиса

```bash
# Включить автозапуск
sudo systemctl enable shorts-news

# Запустить сервис
sudo systemctl start shorts-news

# Проверить статус
sudo systemctl status shorts-news
```

## 📊 Управление сервисом

### Просмотр логов в реальном времени

```bash
sudo journalctl -u shorts-news -f
```

### Перезапуск сервиса

```bash
sudo systemctl restart shorts-news
```

### Остановка сервиса

```bash
sudo systemctl stop shorts-news
```

### Отключение автозапуска

```bash
sudo systemctl disable shorts-news
```

## 🔧 Скрипты управления

### update_bot.sh - Автообновление

```bash
cd /home/dzianis/shorts_news
chmod +x deploy/update_bot.sh

# Обновить бота с Git
./deploy/update_bot.sh update

# Перезапустить сервис
./deploy/update_bot.sh restart

# Показать статус
./deploy/update_bot.sh status

# Просмотр логов
./deploy/update_bot.sh logs

# Создать бэкап
./deploy/update_bot.sh backup

# Откатить к последнему бэкапу
./deploy/update_bot.sh rollback
```

### view_logs.sh - Просмотр логов

```bash
chmod +x deploy/view_logs.sh

# Логи в реальном времени (systemd)
./deploy/view_logs.sh live

# Логи из файла
./deploy/view_logs.sh file

# Только ошибки
./deploy/view_logs.sh errors

# Логи за сегодня
./deploy/view_logs.sh today

# Последние 100 строк
./deploy/view_logs.sh last

# Поиск по паттерну
./deploy/view_logs.sh grep "video"
```

## 🔍 Отладка

### Проверка работы бота

```bash
# Статус сервиса
sudo systemctl status shorts-news

# Последние логи
sudo journalctl -u shorts-news --lines=50 --no-pager

# Проверка процесса
ps aux | grep channel_monitor

# Проверка портов (если используется webhook)
sudo netstat -tulpn | grep python
```

### Проблемы и решения

#### Сервис не запускается

```bash
# Проверьте логи ошибок
sudo journalctl -u shorts-news -n 100 --no-pager

# Проверьте права доступа
ls -la /home/dzianis/shorts_news/

# Проверьте виртуальное окружение
source /home/dzianis/shorts_news/venv/bin/activate
python --version
pip list
```

#### Ошибки с Selenium/Chrome

```bash
# Установите Xvfb для headless режима
sudo apt install xvfb

# Проверьте chromium
chromium-browser --version
chromedriver --version

# Запустите Xvfb
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
```

#### Недостаточно прав

```bash
# Проверьте владельца файлов
sudo chown -R dzianis:dzianis /home/dzianis/shorts_news/

# Проверьте права на выполнение
chmod +x /home/dzianis/shorts_news/channel_monitor.py
```

## 📁 Структура директорий на сервере

```
/home/dzianis/
└── shorts_news/
    ├── venv/                    # Виртуальное окружение
    ├── config/                  # Конфигурация
    │   ├── config.yaml
    │   ├── prompts.yaml
    │   └── client_secret.json
    ├── data/                    # Базы данных
    │   └── user_news.db
    ├── logs/                    # Логи приложения
    │   └── channel_monitor.log
    ├── outputs/                 # Готовые видео
    ├── resources/               # Ресурсы
    │   ├── music/
    │   ├── fonts/
    │   └── logos/
    ├── temp/                    # Временные файлы
    ├── .env                     # Переменные окружения
    └── channel_monitor.py       # Точка входа
```

## 🔒 Безопасность

### Защита API ключей

```bash
# Убедитесь что .env не доступен публично
chmod 600 .env

# Проверьте .gitignore
cat .gitignore | grep .env
```

### Firewall (опционально)

```bash
# Разрешить SSH
sudo ufw allow 22/tcp

# Включить firewall
sudo ufw enable

# Проверить статус
sudo ufw status
```

## 📈 Мониторинг

### Автоматический перезапуск при сбое

Systemd автоматически перезапустит сервис при падении (настроено в `Restart=always`).

### Проверка использования ресурсов

```bash
# CPU и память
top -p $(pgrep -f channel_monitor)

# Дисковое пространство
df -h

# Размер логов
du -sh logs/
```

### Ротация логов

```bash
# Создайте конфигурацию logrotate
sudo nano /etc/logrotate.d/shorts-news
```

Содержимое:
```
/home/dzianis/shorts_news/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 644 dzianis dzianis
}
```

## 🔄 Обновление

### Автоматическое обновление из Git

```bash
./deploy/update_bot.sh update
```

Скрипт:
1. Создаст бэкап текущей версии
2. Остановит сервис
3. Применит обновления из Git
4. Обновит зависимости (если изменился requirements.txt)
5. Запустит сервис
6. Проверит статус

### Откат к предыдущей версии

```bash
./deploy/update_bot.sh rollback
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `sudo journalctl -u shorts-news -n 100`
2. Проверьте статус: `sudo systemctl status shorts-news`
3. Проверьте конфигурацию: `.env` и `config/config.yaml`
4. Проверьте наличие ресурсов: музыка, шрифты, credentials

## 📚 Дополнительные ресурсы

- [README.md](README.md) - Основная документация
- [PROJECT_INFO.md](PROJECT_INFO.md) - Архитектура проекта
- [CLEANUP_ANALYSIS.md](CLEANUP_ANALYSIS.md) - Анализ структуры проекта

