# ⚡ Быстрое развёртывание на Ubuntu

## 🎯 Одной командой (на сервере)

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/shorts_news/main/deploy/install_ubuntu.sh | bash
```

## 📋 Пошаговая установка

### 1. На Windows (подготовка)

```powershell
# Упакуйте необходимые ресурсы
Compress-Archive -Path resources\music\* -DestinationPath resources_music.zip
Compress-Archive -Path resources\fonts\* -DestinationPath resources_fonts.zip

# Скопируйте через SCP или SFTP на сервер
```

### 2. На Ubuntu сервере

```bash
# Клонирование
cd /home/dzianis
git clone https://github.com/YOUR_USERNAME/shorts_news.git
cd shorts_news

# Установка
chmod +x deploy/install_ubuntu.sh
./deploy/install_ubuntu.sh

# Настройка .env
nano .env

# Копирование ресурсов
unzip ~/resources_music.zip -d resources/music/
unzip ~/resources_fonts.zip -d resources/fonts/

# Копирование YouTube credentials
cp ~/client_secret.json config/

# Запуск
sudo systemctl enable shorts-news
sudo systemctl start shorts-news

# Проверка
sudo systemctl status shorts-news
sudo journalctl -u shorts-news -f
```

## 🔧 Настройка update_bot.sh

```bash
# Сделать скрипт исполняемым
chmod +x deploy/update_bot.sh
chmod +x deploy/view_logs.sh

# Создать алиас для удобства
echo "alias shorts-update='~/shorts_news/deploy/update_bot.sh'" >> ~/.bashrc
echo "alias shorts-logs='~/shorts_news/deploy/view_logs.sh'" >> ~/.bashrc
source ~/.bashrc

# Теперь можно использовать короткие команды
shorts-update status
shorts-update logs
shorts-logs live
```

## 📊 Полезные команды

```bash
# Статус
sudo systemctl status shorts-news

# Перезапуск
sudo systemctl restart shorts-news

# Логи
sudo journalctl -u shorts-news -f

# Обновление
cd /home/dzianis/shorts_news && ./deploy/update_bot.sh update

# Бэкап
cd /home/dzianis/shorts_news && ./deploy/update_bot.sh backup

# Откат
cd /home/dzianis/shorts_news && ./deploy/update_bot.sh rollback
```

## 🎯 Чек-лист после установки

- [ ] Сервис запущен: `sudo systemctl status shorts-news`
- [ ] .env настроен с правильными токенами
- [ ] Музыка в `resources/music/` (минимум 1 файл)
- [ ] Шрифты в `resources/fonts/` (минимум 1 файл)
- [ ] YouTube credentials в `config/client_secret.json`
- [ ] База данных создана в `data/user_news.db`
- [ ] Логи пишутся: `tail -f logs/channel_monitor.log`
- [ ] Telegram бот отвечает на команды
- [ ] Видео создаются и загружаются на YouTube

## 🚨 Troubleshooting

### Сервис не запускается

```bash
# Проверить логи ошибок
sudo journalctl -u shorts-news -n 50 --no-pager

# Проверить Python
source venv/bin/activate
python channel_monitor.py

# Проверить зависимости
pip list
```

### Chrome/Selenium проблемы

```bash
# Установить Xvfb
sudo apt install xvfb

# Запустить виртуальный дисплей
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
export DISPLAY=:99

# Добавить в systemd service
sudo nano /etc/systemd/system/shorts-news.service
# Добавить: Environment=DISPLAY=:99
```

### FFmpeg не найден

```bash
sudo apt install ffmpeg
ffmpeg -version
```

### Недостаточно места

```bash
# Очистить старые видео
rm -rf outputs/*.mp4
rm -rf temp/*

# Очистить логи
truncate -s 0 logs/*.log

# Проверить место
df -h
```

