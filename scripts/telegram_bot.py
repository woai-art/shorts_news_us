#!/usr/bin/env python3
"""
Telegram бот для системы shorts_news
Принимает ссылки на новости и добавляет их в очередь обработки
"""

import os
import sys
import logging
import asyncio
import re
import time
from typing import Dict, Optional, Any
import yaml
import sqlite3
from datetime import datetime

# Добавление пути к модулям
sys.path.append(os.path.dirname(__file__))

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NewsTelegramBot:
    """Telegram бот для приема новостей"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.project_path = self.config['project']['base_path']

        # Настройки Telegram
        self.telegram_config = self.config['telegram']
        # Используем фиксированный токен для tubepull_bot
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
        self.channel = self.telegram_config.get('channel', "@tubepull_bot")
        self.channel_id = self.telegram_config.get('channel_id', "")
        # Админ-группа для сервисных уведомлений/команд (из .env)
        self.publish_group_id = int(os.getenv("PUBLISH_CHANNEL_ID", "0"))
        # Токен бота, который отправляет сервисные сообщения (по умолчанию тот же)
        self.publish_bot_token = os.getenv("PUBLISH_BOT_TOKEN", self.bot_token)

        # Диагностика конфигурации отправки
        try:
            masked_push = (self.publish_bot_token[:6] + "..." + self.publish_bot_token[-4:]) if self.publish_bot_token else ""
            logger.info(f"📡 Publish group: {self.publish_group_id}, push bot: {masked_push}")
        except Exception:
            pass

        # Инициализация движков новостных источников
        from engines.registry import EngineRegistry
        self.engine_registry = EngineRegistry()

        # Инициализация БД для пользовательских новостей
        self.db_path = os.path.join(self.project_path, 'data', 'user_news.db')
        self._init_user_news_db()

        # Статистика
        self.stats = {
            'received_links': 0,
            'processed_links': 0,
            'start_time': datetime.now()
        }

    def _load_config(self, config_path: str) -> Dict:
        """Загрузка конфигурации"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _init_user_news_db(self):
        """Инициализация расширенной базы данных для новостей"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Основная таблица новостей
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    content TEXT,
                    published_date TEXT,
                    source TEXT,
                    content_type TEXT,
                    user_id INTEGER,
                    chat_id INTEGER,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed INTEGER DEFAULT 0,
                    processed_at TIMESTAMP,
                    fact_check_score REAL,
                    verification_status TEXT,
                    video_created INTEGER DEFAULT 0,
                    video_url TEXT,
                    video_start_seconds REAL DEFAULT 0,
                    username TEXT,
                    images TEXT,
                    videos TEXT,
                    local_video_path TEXT,
                    avatar_path TEXT
                )
            ''')

            # Таблица для изображений новости
            conn.execute('''
                CREATE TABLE IF NOT EXISTS news_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id INTEGER,
                    image_url TEXT NOT NULL,
                    local_path TEXT,
                    downloaded INTEGER DEFAULT 0,
                    FOREIGN KEY (news_id) REFERENCES user_news (id)
                )
            ''')

            # Таблица для источников проверки фактов
            conn.execute('''
                CREATE TABLE IF NOT EXISTS fact_check_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id INTEGER,
                    source_url TEXT,
                    source_title TEXT,
                    confidence_score REAL,
                    FOREIGN KEY (news_id) REFERENCES user_news (id)
                )
            ''')

            conn.commit()
        
        logger.info(f"Расширенная база данных новостей инициализирована: {self.db_path}")

        # Миграция: добавить недостающие столбцы
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(user_news)")
                columns = {row[1] for row in cursor.fetchall()}
                
                migrations = {
                    'video_start_seconds': 'REAL DEFAULT 0',
                    'content': 'TEXT',
                    'images': 'TEXT',
                    'videos': 'TEXT',
                    'local_video_path': 'TEXT',
                    'avatar_path': 'TEXT'
                }
                
                for col, col_type in migrations.items():
                    if col not in columns:
                        cursor.execute(f'ALTER TABLE user_news ADD COLUMN {col} {col_type}')
                        logger.info(f"🔧 Добавлен столбец {col} в таблицу user_news")
                
                conn.commit()
        except Exception as e:
            logger.warning(f"Не удалось выполнить миграцию базы данных: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_message = """
🤖 Привет! Я бот для создания новостных Shorts!

📝 Отправьте мне ссылку на новость, и я создам из неё короткое видео для YouTube.

📋 Поддерживаемые форматы:
• Прямые ссылки на новости
• Ссылки из Telegram каналов
• Любые URL с новостным контентом

⚙️ Доступные команды:
/start - показать это сообщение
/stats - показать статистику
/help - справка

🚀 Просто отправьте ссылку на новость!
        """

        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_message = """
📖 Справка по использованию бота

🎯 Как использовать:
1. Найдите интересную новость
2. Скопируйте ссылку на неё
3. Отправьте ссылку мне в чат

🤖 Что делает бот:
• Извлекает текст новости по ссылке
• Создает краткое содержание с помощью ИИ
• Генерирует анимированное видео
• Загружает видео на YouTube Shorts

📊 Форматы ссылок:
✅ https://www.bbc.com/news/article
✅ https://cnn.com/article
✅ https://t.me/channel/123
✅ Любые другие URL

⚠️ Ограничения:
• Ссылка должна вести на новость
• Новость должна быть на русском или английском
• Максимум 5 ссылок в час от одного пользователя

📈 Статистика: /stats
        """

        await update.message.reply_text(help_message)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN processed = 1 THEN 1 END) as processed,
                       COUNT(CASE WHEN processed = 0 THEN 1 END) as pending
                FROM user_news
            ''')
            stats = cursor.fetchone()

        runtime = datetime.now() - self.stats['start_time']

        stats_message = f"""
📊 Статистика бота

⏱️ Время работы: {str(runtime).split('.')[0]}
📨 Получено ссылок: {self.stats['received_links']}
✅ Обработано: {stats[1] if stats else 0}
⏳ В очереди: {stats[2] if stats else 0}
📈 Всего в БД: {stats[0] if stats else 0}

🤖 Статус: {'🟢 Активен' if self.stats['received_links'] > 0 else '🟡 Ожидание'}
        """

        await update.message.reply_text(stats_message)

    async def startat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка стартового времени для видео: /startat <news_id> <seconds>"""
        try:
            chat_id = update.effective_chat.id
            if self.publish_group_id and chat_id != self.publish_group_id:
                await update.message.reply_text("Эта команда доступна только в админ-группе.")
                return

            args = context.args or []
            if len(args) < 2:
                await update.message.reply_text("Использование: /startat <news_id> <seconds>")
                return

            news_id = int(args[0])
            seconds = float(args[1])
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('UPDATE user_news SET video_start_seconds=? WHERE id=?', (seconds, news_id))
                conn.commit()
            await update.message.reply_text(f"✅ Старт для видео новости {news_id} установлен: {seconds} c")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    def _set_video_start_seconds(self, news_id: int, start_seconds: float):
        """Устанавливает время старта видео для новости."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE user_news 
                SET video_start_seconds = ? 
                WHERE id = ?
            """, (start_seconds, news_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Установлено время старта видео для новости {news_id}: {start_seconds}с")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка установки времени старта видео: {e}")
            return False

    async def _handle_channel_message(self, message_text: str, user_id: int, chat_id: int):
        """Обработка сообщений из канала мониторинга"""
        logger.info(f"🔄 Обработка сообщения из канала: {message_text[:100]}...")

        # Проверка на URL
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message_text)

        if not urls:
            # Если нет ссылок, возможно это просто текст новости
            if len(message_text) > 20:  # Минимум 20 символов для новости
                await self._process_channel_text_news(message_text, user_id, chat_id)
            else:
                logger.info("⚠️ В сообщении канала не найдено ссылок или достаточного текста")
            return

        # Обработка каждой ссылки из канала
        for url in urls[:3]:  # Максимум 3 ссылки за раз
            try:
                await self._process_channel_news_url(url, user_id, chat_id)
            except Exception as e:
                logger.error(f"❌ Ошибка обработки URL из канала {url}: {e}")

    async def _process_channel_news_url(self, url: str, user_id: int, chat_id: int):
        """Обработка URL новости из канала (без ответных сообщений)"""
        logger.info(f"🌐 Обработка URL из канала: {url}")

        # Проверка на дубликат
        if self._is_url_already_processed(url):
            logger.info(f"📋 URL уже обработан ранее: {url}")
            return

        try:
            # Парсинг веб-страницы через движки
            parsed_data = await self._parse_url_with_engines(url)

            if not parsed_data or not parsed_data.get('title'):
                logger.error(f"❌ Не удалось спарсить новость: {url}")
                return

            # Сохранение в базу данных
            news_id = self._save_parsed_news(parsed_data, user_id, chat_id)
            logger.info(f"✅ Новость сохранена в БД (ID: {news_id}): {parsed_data['title'][:50]}...")

            # Отправка статуса в канал публикации
            if hasattr(self, 'telegram_publisher') and self.telegram_publisher:
                try:
                    import asyncio
                    asyncio.create_task(
                        self.telegram_publisher.publish_status_update(
                            f"📰 Новая новость получена: {parsed_data['title'][:50]}..."
                        )
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки статуса: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки URL из канала: {e}")

    async def _process_channel_text_news(self, message_text: str, user_id: int, chat_id: int):
        """Обработка текста новости из канала"""
        logger.info(f"📝 Обработка текста новости из канала: {message_text[:50]}...")

        try:
            # Создание базовой новости из текста
            news_data = {
                'url': f'channel_text_{int(time.time())}',
                'title': message_text[:100] + ('...' if len(message_text) > 100 else ''),
                'description': message_text,
                'source': 'Channel Message',
                'content_type': 'text'
            }

            # Сохранение в базу данных
            news_id = self._save_parsed_news(news_data, user_id, chat_id)
            logger.info(f"✅ Текстовая новость сохранена в БД (ID: {news_id})")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки текста из канала: {e}")

    def _notify_group_on_video(self, news_id: int, title: str, videos: list[str]):
        """Сервисное уведомление в админ-группу о найденном видео и просьба указать старт."""
        try:
            if not self.publish_group_id or not self.publish_bot_token or not videos:
                return
            import requests
            preview = videos[0][:80] + ('...' if len(videos[0]) > 80 else '')
            text = (
                f"🎬 Готовим новость ID {news_id}: {title[:64]}\n"
                f"Видео найдено: {preview}\n\n"
                f"Укажите старт (в секундах) командой: /startat {news_id} <seconds>\n"
                f"Напр.: /startat {news_id} 5 — начать с 5 секунды.\n"
                f"Оставьте как есть — будет 0 c."
            )
            url = f"https://api.telegram.org/bot{self.publish_bot_token}/sendMessage"
            resp = requests.post(url, json={
                'chat_id': self.publish_group_id,
                'text': text
            }, timeout=8)
            try:
                logger.info(f"📨 push status={resp.status_code}: {resp.text[:200]}")
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Не удалось отправить сервисное сообщение в группу (HTTP): {e}")

    def _send_group_ping(self):
        """Пробная отправка сообщения в админ-группу для проверки конфигурации."""
        try:
            if not self.publish_group_id or not self.publish_bot_token:
                return
            import requests
            url = f"https://api.telegram.org/bot{self.publish_bot_token}/sendMessage"
            resp = requests.post(url, json={
                'chat_id': self.publish_group_id,
                'text': '✅ Monitor online. Сервисные уведомления активны.'
            }, timeout=8)
            logger.info(f"📡 ping status={resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Не удалось отправить ping в группу: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        message_text = update.message.text.strip()
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id

        # Проверка, является ли сообщение из канала мониторинга
        if str(chat_id) == self.channel_id:
            logger.info(f"📡 Получено сообщение из канала {self.channel}: {message_text[:100]}...")
            await self._handle_channel_message(message_text, user_id, chat_id)
            return

        # Команда из админ-группы для установки старта видео
        if self.publish_group_id and chat_id == self.publish_group_id and message_text.lower().startswith('/startat'):
            try:
                parts = message_text.split()
                if len(parts) >= 3:
                    news_id = int(parts[1])
                    seconds = float(parts[2])
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute('UPDATE user_news SET video_start_seconds=? WHERE id=?', (seconds, news_id))
                        conn.commit()
                    await update.message.reply_text(f"✅ Старт для видео новости {news_id} установлен: {seconds} c")
                    return
                else:
                    await update.message.reply_text("Использование: /startat <news_id> <seconds>")
                    return
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка: {e}")
                return

        # Проверка на URL
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message_text)

        if not urls:
            # Если нет ссылок, возможно это просто текст новости
            if len(message_text) > 10:  # Минимум 10 символов для новости
                await self._process_text_news(message_text, user_id, chat_id, update)
            else:
                await update.message.reply_text(
                    "❌ Не найдено ссылок или текста новости в сообщении.\n\n"
                    "📝 Отправьте:\n"
                    "• Ссылку на новость\n"
                    "• Текст новости с ссылкой\n"
                    "• Репост новости из другого канала"
                )
            return

        # Обработка каждой ссылки
        for url in urls[:3]:  # Максимум 3 ссылки за раз
            try:
                await self._process_news_url(url, user_id, chat_id, update)
            except Exception as e:
                logger.error(f"Ошибка обработки URL {url}: {e}")
                await update.message.reply_text(f"❌ Ошибка обработки ссылки: {url}")

    async def _process_news_url(self, url: str, user_id: int, chat_id: int, update: Update):
        """Обработка URL новости с парсингом"""

        # Проверка на дубликат
        if self._is_url_already_processed(url):
            await update.message.reply_text(
                f"📋 Эта ссылка уже была обработана ранее:\n{url}"
            )
            return

        # Отправка подтверждения о начале обработки
        await update.message.reply_text(
            f"🔄 Начинаю обработку ссылки:\n{url}\n\n"
            f"⏳ Парсинг веб-страницы..."
        )

        try:
            # Парсинг веб-страницы через движки
            parsed_data = self._parse_url_with_engines(url)

            if not parsed_data.get('success', False):
                await update.message.reply_text(
                    f"⚠️ Не удалось полностью распарсить страницу:\n{url}\n\n"
                    f"Будет использовано базовое содержимое."
                )

            # Сохранение полной информации о новости
            news_id = self._save_parsed_news(parsed_data, user_id, chat_id)

            # Подтверждение успешного парсинга
            success_msg = (
                f"✅ Новость успешно обработана!\n\n"
                f"📰 **{parsed_data.get('title', 'Без заголовка')}**\n"
                f"📊 ID в системе: {news_id}\n"
                f"🔗 Источник: {parsed_data.get('source', 'Неизвестен')}\n"
                f"📝 Длина текста: {len(parsed_data.get('description', ''))} символов\n"
                f"🖼️ Изображений: {len(parsed_data.get('images', []))}\n\n"
                f"🎬 Видео будет создано автоматически..."
            )

            await update.message.reply_text(success_msg, parse_mode='Markdown')

            self.stats['received_links'] += 1
            logger.info(f"Успешно обработана ссылка от пользователя {user_id}: {url}")

        except Exception as e:
            logger.error(f"Ошибка парсинга URL {url}: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при парсинге ссылки:\n{url}\n\n"
                f"Детали: {str(e)}"
            )

    async def _process_text_news(self, text: str, user_id: int, chat_id: int, update: Update):
        """Обработка текстовой новости без ссылки"""
        try:
            # Создание базовой новости из текста
            news_data = {
                'success': True,
                'url': None,
                'title': text[:100] + "..." if len(text) > 100 else text,
                'description': text,
                'published': datetime.now().isoformat(),
                'source': 'Telegram Text',
                'images': [],
                'content_type': 'text_news'
            }

            # Сохранение новости
            news_id = self._save_parsed_news(news_data, user_id, chat_id)

            await update.message.reply_text(
                f"✅ Текстовая новость принята!\n\n"
                f"📊 ID в системе: {news_id}\n"
                f"📝 Длина текста: {len(text)} символов\n\n"
                f"🎬 Видео будет создано автоматически..."
            )

            self.stats['received_links'] += 1
            logger.info(f"Принята текстовая новость от пользователя {user_id}")

        except Exception as e:
            logger.error(f"Ошибка обработки текстовой новости: {e}")
            await update.message.reply_text(f"❌ Ошибка обработки текста: {str(e)}")

    def _is_url_already_processed(self, url: str) -> bool:
        """Проверка, была ли ссылка уже обработана"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT id FROM user_news WHERE url = ?',
                (url,)
            )
            return cursor.fetchone() is not None

    def _save_parsed_news(self, news_data: Dict, user_id: int, chat_id: int) -> int:
        """Сохранение полной информации о новости в расширенную БД"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                # ЗАГЛУШКА ДЛЯ ТЕСТИРОВАНИЯ: Удаляем существующую новость с таким же URL.
                # Это позволяет повторно обрабатывать одну и ту же новость во время тестов.
                url_to_check = news_data.get('url')
                if url_to_check:
                    conn.execute('DELETE FROM user_news WHERE url = ?', (url_to_check,))
                    logger.info(f"Удалена старая запись для URL (тестовый режим): {url_to_check}")

                # Сохранение основной информации о новости
                cursor = conn.execute('''
                    INSERT INTO user_news (
                        url, title, description, content, published_date, source,
                        content_type, user_id, chat_id, fact_check_score,
                        verification_status, images, videos, username, avatar_url, local_video_path, avatar_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    news_data.get('url'),
                    news_data.get('title', 'Без заголовка'),
                    news_data.get('description', ''),
                    news_data.get('content', ''),  # Добавляем полный контент статьи
                    news_data.get('published'),
                    news_data.get('source', 'Неизвестен'),
                    news_data.get('content_type', 'webpage'),
                    user_id,
                    chat_id,
                    news_data.get('fact_verification', {}).get('accuracy_score'),
                    news_data.get('fact_verification', {}).get('verification_status'),
                    '|'.join(news_data.get('images', [])),
                    '|'.join(news_data.get('videos', [])),
                    news_data.get('username', ''),  # Добавляем username для аватарки
                    news_data.get('avatar_url', ''),  # Добавляем URL аватарки
                    news_data.get('local_video_path', ''),  # Добавляем путь к локальному видео
                    news_data.get('avatar_path', '')  # Добавляем путь к аватарке
                ))

                news_id = cursor.lastrowid

                # Сохранение изображений
                images = news_data.get('images', [])
                for image_url in images:
                    conn.execute('''
                        INSERT INTO news_images (news_id, image_url)
                        VALUES (?, ?)
                    ''', (news_id, image_url))

                # Сохранение источников проверки фактов
                verification_sources = news_data.get('verification_sources', [])
                for source in verification_sources:
                    conn.execute('''
                        INSERT INTO fact_check_sources (
                            news_id, source_url, source_title, confidence_score
                        ) VALUES (?, ?, ?, ?)
                    ''', (
                        news_id,
                        source.get('uri', ''),
                        source.get('title', ''),
                        0.8  # Пока фиксированная уверенность
                    ))

                conn.commit()
                logger.info(f"Новость сохранена в БД с ID {news_id}")

                # Сервисное уведомление в группу, если есть видео
                try:
                    videos_list = news_data.get('videos') or []
                    if isinstance(videos_list, str):
                        videos_list = [v for v in videos_list.split(',') if v]
                    if videos_list:
                        self._notify_group_on_video(news_id, news_data.get('title',''), videos_list)
                except Exception as e:
                    logger.warning(f"Не удалось уведомить группу о видео: {e}")
                return news_id

            except Exception as e:
                conn.rollback()
                logger.error(f"Ошибка сохранения новости: {e}")
                raise

    def _save_user_news(self, url: str, user_id: int, chat_id: int) -> int:
        """Устаревший метод для совместимости - сохраняет базовую новость"""
        news_data = {
            'url': url,
            'title': f'Ссылка: {url}',
            'description': f'Обработка ссылки: {url}',
            'source': 'URL',
            'content_type': 'url_only'
        }
        return self._save_parsed_news(news_data, user_id, chat_id)

    def mark_news_processed(self, news_id: int, title: str = None, description: str = None):
        """Отметить новость как обработанную"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE user_news
                SET processed = 1, processed_at = ?
                WHERE id = ?
            ''', (datetime.now(), news_id))

            # Если переданы обновленные данные, обновляем их
            if title or description:
                update_fields = []
                update_values = []

                if title:
                    update_fields.append("title = ?")
                    update_values.append(title)

                if description:
                    update_fields.append("description = ?")
                    update_values.append(description)

                if update_fields:
                    update_values.append(news_id)
                    conn.execute(f'''
                        UPDATE user_news
                        SET {', '.join(update_fields)}
                        WHERE id = ?
                    ''', update_values)

            conn.commit()

    def get_pending_news(self, limit: int = 10) -> list:
        """Получение необработанных новостей с полной информацией"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Получение основных данных новостей
            news_cursor = conn.execute('''
                SELECT * FROM user_news
                WHERE processed = 0
                ORDER BY received_at ASC
                LIMIT ?
            ''', (limit,))

            news_list = []
            for news_row in news_cursor.fetchall():
                news_dict = dict(news_row)
                
                # Маппинг полей БД к ожидаемым названиям
                if 'published_date' in news_dict:
                    news_dict['published'] = news_dict['published_date']
                
                # Обработка медиа из БД
                if 'images' in news_dict and news_dict['images']:
                    news_dict['images'] = news_dict['images'].split(',') if news_dict['images'] else []
                else:
                    news_dict['images'] = []
                    
                if 'videos' in news_dict and news_dict['videos']:
                    news_dict['videos'] = news_dict['videos'].split(',') if news_dict['videos'] else []
                else:
                    news_dict['videos'] = []

                # Получение изображений для новости (из БД + из news_images таблицы)
                images_cursor = conn.execute('''
                    SELECT image_url, local_path, downloaded
                    FROM news_images
                    WHERE news_id = ?
                    ORDER BY id ASC
                ''', (news_dict['id'],))

                # Объединяем изображения из БД и из news_images таблицы
                db_images = news_dict.get('images', [])
                table_images = [
                    {
                        'url': img['image_url'],
                        'local_path': img['local_path'],
                        'downloaded': img['downloaded']
                    } for img in images_cursor.fetchall()
                ]
                
                # Если есть изображения в таблице, используем их, иначе используем из БД
                if table_images:
                    news_dict['images'] = [img['url'] for img in table_images if img['url']]
                else:
                    news_dict['images'] = db_images

                # Добавляем пути к локальным файлам медиа
                if 'local_video_path' in news_dict and news_dict['local_video_path']:
                    # Если есть локальное видео, добавляем его в список видео
                    if news_dict['local_video_path'] not in news_dict['videos']:
                        news_dict['videos'].append(news_dict['local_video_path'])
                
                # Аватарка уже доступна через news_dict['avatar_path']

                # Получение источников проверки фактов
                sources_cursor = conn.execute('''
                    SELECT source_url, source_title, confidence_score
                    FROM fact_check_sources
                    WHERE news_id = ?
                    ORDER BY confidence_score DESC
                ''', (news_dict['id'],))

                news_dict['verification_sources'] = [
                    {
                        'url': src['source_url'],
                        'title': src['source_title'],
                        'confidence': src['confidence_score']
                    } for src in sources_cursor.fetchall()
                ]

                news_list.append(news_dict)

            return news_list

    def get_news_by_id(self, news_id: int) -> Dict:
        """Получение конкретной новости по ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute('''
                SELECT * FROM user_news
                WHERE id = ?
            ''', (news_id,))
            
            news_row = cursor.fetchone()
            if not news_row:
                return None
                
            news_dict = dict(news_row)
            
            # Маппинг полей БД к ожидаемым названиям
            if 'published_date' in news_dict:
                news_dict['published'] = news_dict['published_date']
            
            # Обработка медиа из БД - сначала проверяем поле images в user_news
            if 'images' in news_dict and news_dict['images']:
                # Если есть изображения в поле images, используем их
                if isinstance(news_dict['images'], str):
                    # Разбиение по разделителю |
                    news_dict['images'] = [url.strip() for url in news_dict['images'].split('|') if url.strip()]
                else:
                    news_dict['images'] = []
            else:
                news_dict['images'] = []
                
            if 'videos' in news_dict and news_dict['videos']:
                # Умное разбиение URL видео - ищем полные URL
                if isinstance(news_dict['videos'], str):
                    # Разбиение по разделителю |
                    news_dict['videos'] = [url.strip() for url in news_dict['videos'].split('|') if url.strip()]
                else:
                    news_dict['videos'] = []
            else:
                news_dict['videos'] = []
            
            # Если нет изображений в поле images, получаем из таблицы news_images
            if not news_dict['images']:
                images_cursor = conn.execute('''
                    SELECT image_url, local_path, downloaded
                    FROM news_images
                    WHERE news_id = ?
                    ORDER BY id ASC
                ''', (news_id,))
                
                news_dict['images'] = [
                {
                    'url': img['image_url'],
                    'local_path': img['local_path'],
                    'downloaded': img['downloaded']
                } for img in images_cursor.fetchall()
            ]
            
            # Добавляем пути к локальным файлам медиа (как в get_pending_news)
            if 'local_video_path' in news_dict and news_dict['local_video_path']:
                # Если есть локальное видео, добавляем его в список видео
                if news_dict['local_video_path'] not in news_dict['videos']:
                    news_dict['videos'].append(news_dict['local_video_path'])
                    
            # Добавляем локальные пути к изображениям если они есть
            if 'local_image_path' in news_dict and news_dict['local_image_path']:
                # Если есть локальное изображение, добавляем его в список изображений
                if isinstance(news_dict['images'], list):
                    if news_dict['local_image_path'] not in news_dict['images']:
                        news_dict['images'].append(news_dict['local_image_path'])
                else:
                    news_dict['images'] = [news_dict['local_image_path']]
            
            # Аватарка уже доступна через news_dict['avatar_path']
            
            return news_dict

    def mark_video_created(self, news_id: int, video_url: str = None):
        """Отметить, что видео создано для новости"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE user_news
                SET video_created = 1, video_url = ?
                WHERE id = ?
            ''', (video_url, news_id))
            conn.commit()
            logger.info(f"Видео отмечено как созданное для новости {news_id}")

    async def _trigger_news_processing(self, news_id: int, url: str):
        """Триггер обработки новости (заглушка для будущего использования)"""
        # Здесь можно добавить логику вызова основного обработчика новостей
        logger.info(f"Триггер обработки новости {news_id}: {url}")

        # Имитация обработки
        await asyncio.sleep(2)

        # Отметка как обработанная
        self.mark_news_processed(news_id, "Обработанная новость", "Описание новости")

        logger.info(f"Новость {news_id} отмечена как обработанная")

    async def run_bot(self):
        """Запуск бота"""
        if not self.bot_token:
            logger.error("Токен Telegram бота не найден в переменных окружения")
            logger.error(f"Установите переменную: {self.telegram_config['bot_token_env']}")
            return

        logger.info("🤖 Запуск Telegram бота...")

        # Создание приложения
        application = Application.builder().token(self.bot_token).build()

        # Добавление обработчиков
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(CommandHandler("startat", self.startat_command))
        application.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, self.handle_message))

        # Запуск бота
        logger.info("✅ Бот запущен и готов к работе")
        logger.info("Для остановки нажмите Ctrl+C")

        # Простой запуск без обработки исключений
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

    def _parse_url_with_engines(self, url: str) -> Dict[str, Any]:
        """Парсинг URL через движки новостных источников"""
        try:
            # Проверяем, может ли какой-то движок обработать URL
            engine = self.engine_registry.get_engine_for_url(url)
            if engine:
                logger.info(f"🎯 Используем движок {engine.__class__.__name__} для URL: {url}")
                result = engine.parse_url(url)
                
                # Преобразуем результат в формат, совместимый со старым web_parser
                if result and result.get('title'):
                    return {
                        'success': True,
                        'url': url,
                        'title': result.get('title', ''),
                        'description': result.get('description', ''),
                        'content': result.get('content', ''),
                        'published': result.get('published', ''),
                        'source': result.get('source', ''),
                        'author': result.get('author', ''),
                        'username': result.get('username', ''),
                        'images': result.get('images', []),
                        'videos': result.get('videos', []),
                        'content_type': result.get('content_type', '')
                    }
                else:
                    logger.warning(f"❌ Движок {engine.__class__.__name__} не смог обработать URL: {url}")
                    return {'success': False, 'url': url, 'error': 'Engine failed to parse'}
            else:
                logger.warning(f"❌ Нет подходящего движка для URL: {url}")
                return {'success': False, 'url': url, 'error': 'No suitable engine found'}
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга URL через движки: {e}")
            return {'success': False, 'url': url, 'error': str(e)}

def create_systemd_service():
    """Создание systemd service файла для автозапуска бота"""
    service_content = f"""[Unit]
Description=Shorts News Telegram Bot
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'www-data')}
WorkingDirectory={os.path.dirname(os.path.abspath(__file__))}/..
ExecStart={sys.executable} scripts/telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    service_path = "/etc/systemd/system/shorts-news-bot.service"
    try:
        with open(service_path, 'w') as f:
            f.write(service_content)
        logger.info(f"Создан systemd service файл: {service_path}")
        logger.info("Для активации выполните:")
        logger.info("sudo systemctl daemon-reload")
        logger.info("sudo systemctl enable shorts-news-bot")
        logger.info("sudo systemctl start shorts-news-bot")
    except PermissionError:
        logger.warning("Недостаточно прав для создания systemd service файла")
        logger.info("Создайте файл вручную или запустите с sudo")

def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Telegram Bot for Shorts News System')
    parser.add_argument('--config', default='../config/config.yaml',
                       help='Путь к конфигурационному файлу')
    parser.add_argument('--create-service', action='store_true',
                       help='Создать systemd service файл')

    args = parser.parse_args()

    if args.create_service:
        create_systemd_service()
        return

    # Определение пути к конфигу
    if not os.path.isabs(args.config):
        config_path = os.path.join(os.path.dirname(__file__), args.config)
    else:
        config_path = args.config

    if not os.path.exists(config_path):
        logger.error(f"Файл конфигурации не найден: {config_path}")
        sys.exit(1)

    try:
        # Создание и запуск бота
        bot = NewsTelegramBot(config_path)
        asyncio.run(bot.run_bot())

    except KeyboardInterrupt:
        logger.info("🛑 Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
