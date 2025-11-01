#!/usr/bin/env python3
"""
Главный оркестратор системы shorts_news
Управляет всем процессом от получения новостей до загрузки видео на YouTube
"""

import os
import sys
import time
import logging
import schedule
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import argparse

# Добавление пути к модулям
sys.path.append(os.path.dirname(__file__))

from news_processor import NewsProcessor
from llm_processor import LLMProcessor
from video_exporter import VideoExporter
from youtube_uploader import YouTubeUploader
from telegram_publisher import TelegramPublisher
from analytics import NewsAnalytics

# Импортируем новую архитектуру движков
from engines import registry, PoliticoEngine, WashingtonPostEngine, TwitterEngine, NBCNewsEngine, ABCNewsEngine, TelegramPostEngine, FinancialTimesEngine, TheHillEngine, NYPostEngine
# from engines import WSJEngine  # Отключен: требует подписку + Cloudflare

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/shorts_news.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ShortsNewsOrchestrator:
    """Главный оркестратор системы shorts_news"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.project_path = self.config['project']['base_path']

        # Инициализация компонентов
        self.news_processor = None
        self.llm_processor = None
        self.video_exporter = None
        self.youtube_uploader = None
        self.telegram_bot = None
        self.telegram_publisher = None
        self.analytics = NewsAnalytics()
        
        # Инициализация движков
        self.engines_initialized = False

        # Статистика работы
        self.stats = {
            'processed_news': 0,
            'successful_videos': 0,
            'failed_videos': 0,
            'uploaded_videos': 0,
            'skipped_low_quality': 0,
            'skipped_no_media': 0,
            'start_time': time.time()
        }

    def _load_config(self, config_path: str) -> Dict:
        """Загрузка конфигурации"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def initialize_engines(self):
        """Инициализация движков новостных источников"""
        if self.engines_initialized:
            return
            
        logger.info("Инициализация движков новостных источников...")
        
        try:
            # Регистрируем движки
            registry.register_engine('politico', PoliticoEngine)
            registry.register_engine('washingtonpost', WashingtonPostEngine)
            registry.register_engine('twitter', TwitterEngine)
            registry.register_engine('nbcnews', NBCNewsEngine)
            registry.register_engine('abcnews', ABCNewsEngine)
            registry.register_engine('telegrampost', TelegramPostEngine)
            registry.register_engine('financialtimes', FinancialTimesEngine)
            registry.register_engine('thehill', TheHillEngine)
            registry.register_engine('nypost', NYPostEngine)
            # registry.register_engine('wsj', WSJEngine)  # Отключен: требует подписку + Cloudflare
            
            # TODO: Добавить остальные движки
            # registry.register_engine('apnews', APNewsEngine)
            # registry.register_engine('cnn', CNNEngine)
            # registry.register_engine('reuters', ReutersEngine)
            
            self.engines_initialized = True
            logger.info("✓ Движки новостных источников инициализированы")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации движков: {e}")
            self.engines_initialized = False

    def parse_url_with_engines(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсит URL используя движки новостных источников
        
        Args:
            url: URL для парсинга
            
        Returns:
            Словарь с данными новости или None
        """
        if not self.engines_initialized:
            logger.warning("Движки не инициализированы, используем fallback")
            return None
        
        try:
            # Получаем подходящий движок
            engine = registry.get_engine_for_url(url, self.config)
            
            if not engine:
                logger.warning(f"Не найден подходящий движок для URL: {url[:50]}...")
                return None
            
            # Парсим URL через движок
            logger.info(f"🔍 Парсинг через движок {engine.source_name}: {url[:50]}...")
            content = engine.parse_url(url)
            
            # Извлекаем медиа
            media = engine.extract_media(url, content)
            content.update(media)
            
            # Валидируем контент
            if not engine.validate_content(content):
                logger.warning(f"Контент не прошел валидацию движка {engine.source_name}")
                return None
            
            logger.info(f"✅ URL успешно обработан движком {engine.source_name}")
            return content
            
        except Exception as e:
            logger.error(f"Ошибка парсинга через движки: {e}")
            return None

    def initialize_components(self):
        """Инициализация всех компонентов системы"""
        logger.info("Инициализация компонентов системы...")

        try:
            # Сначала инициализируем движки
            self.initialize_engines()
            # Telegram Bot для получения новостей
            from telegram_bot import NewsTelegramBot
            self.telegram_bot = NewsTelegramBot(self.config_path)
            logger.info("✓ Telegram Bot инициализирован")

            # LLM Processor
            self.llm_processor = LLMProcessor(self.config_path)
            logger.info("✓ LLM Processor инициализирован")

            # Video Exporter (используем Selenium для генерации HTML5 анимаций)
            video_config = self.config['video'].copy()
            video_config['news_sources'] = self.config.get('news_sources', {})
            self.video_exporter = VideoExporter(video_config, self.config['paths'])
            logger.info("✓ Video Exporter (Selenium) инициализирован")
            

            # YouTube Uploader (только если включен)
            if self.config['youtube'].get('upload_enabled', True):
                try:
                    self.youtube_uploader = YouTubeUploader(self.config_path)
                    logger.info("✓ YouTube Uploader инициализирован")
                except Exception as e:
                    logger.error(f"YouTube Uploader не доступен: {e}")
                    logger.warning("Загрузка на YouTube будет отключена")
            else:
                logger.info("YouTube загрузка отключена в конфигурации")

            # Telegram Publisher (для публикации результатов)
            try:
                self.telegram_publisher = TelegramPublisher(self.config_path)
                if self.telegram_publisher.is_available():
                    logger.info("✓ Telegram Publisher инициализирован")
                else:
                    logger.warning("Telegram Publisher отключен в конфигурации")
            except Exception as e:
                logger.error(f"Telegram Publisher не доступен: {e}")
                logger.warning("Публикация в Telegram будет отключена")

            logger.info("Все компоненты успешно инициализированы")

        except Exception as e:
            logger.error(f"Ошибка инициализации компонентов: {e}")
            raise

    def process_single_news_cycle(self):
        """Обработка одного цикла новостей из Telegram бота"""
        logger.info("🚀 Начинаем цикл обработки новостей из Telegram...")

        try:
            # Шаг 1: Получение необработанных новостей из Telegram бота
            logger.info("Шаг 1: Получение новостей из Telegram бота...")
            pending_news = self.telegram_bot.get_pending_news(limit=10)  # Обрабатываем по 10 новостей

            if not pending_news:
                logger.info("Нет новых новостей из Telegram для обработки")
                return

            logger.info(f"Найдено {len(pending_news)} новостей для обработки")

            # Шаг 2: Обработка каждой новости
            for news_item in pending_news:
                try:
                    self._process_single_news(news_item)
                    self.stats['processed_news'] += 1

                except Exception as e:
                    logger.error(f"Ошибка обработки новости ID {news_item['id']}: {e}")
                    continue

            logger.info(f"✅ Цикл обработки завершен. Обработано: {self.stats['processed_news']}")

        except Exception as e:
            logger.error(f"Ошибка в цикле обработки: {e}")

    def process_news_by_id(self, news_id: int):
        """Обработка конкретной новости по ID"""
        logger.info(f"[TARGET] Обработка новости ID {news_id}...")
        
        try:
            # Инициализируем компоненты, если не инициализированы
            if not self.telegram_bot:
                self.initialize_components()
            
            # Получаем новость по ID
            news_data = self.telegram_bot.get_news_by_id(news_id)
            if not news_data:
                logger.error(f"[ERROR] Новость ID {news_id} не найдена")
                return False
            
            logger.info(f"[SUCCESS] Найдена новость: {news_data.get('title', '')[:50]}...")
            
            # Обрабатываем новость и получаем результат
            success = self._process_single_news(news_data)
            self.stats['processed_news'] += 1
            
            if success:
                logger.info(f"[SUCCESS] Новость ID {news_id} успешно обработана")
            else:
                logger.warning(f"[WARNING] Новость ID {news_id} была забракована")
            
            return success
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка обработки новости ID {news_id}: {e}")
            return False

    def _process_single_news(self, news_data: Dict) -> bool:
        """Processes a single news item from raw data to a finished video."""
        news_id = news_data['id']
        logger.info(f"🎬 Processing news ID {news_id}: {news_data.get('title', '')[:50]}...")

        try:
            # Step 1: LLM Processing
            llm_result = self.llm_processor.process_news_for_shorts(news_data)
            logger.info(f"🔍 DEBUG: llm_result = {llm_result}")
            if llm_result.get('status') == 'error':
                logger.error(f"  LLM processing failed: {llm_result.get('error')}")
                return False
            video_package = llm_result.get('video_package', {})
            logger.info(f"🔍 DEBUG: video_package = {video_package}")

            # Step 2: Media Processing
            media_data = self._process_media_for_news(news_data)
            if not media_data.get('has_media'):
                logger.warning(f"  ❌ News item {news_id} has no usable media. Rejecting.")
                return False

            # Step 3: Enrich video_package with runtime data
            video_package['media'] = media_data
            video_package['source_info'] = {
                'name': news_data.get('source', ''),
                'username': news_data.get('username', ''),
                'url': news_data.get('url', ''),
                'publish_date': self._parse_publish_date(news_data.get('published', '')),
                'avatar_path': media_data.get('avatar_path')
            }
            
            # Отладка
            logger.info(f"🔍 DEBUG Media data: {media_data}")
            logger.info(f"🔍 DEBUG Source info: {video_package['source_info']}")

            # Step 4: Content Quality Validation
            if not self._validate_content_quality(video_package, news_data):
                logger.warning(f"  ⚠️ Content for news {news_id} failed quality validation. Skipping.")
                return False

            # Step 5: Video Export
            video_path = self._export_video(news_id, video_package)
            if not video_path:
                return False

            # Step 6: YouTube Upload
            self._upload_to_youtube(video_path, video_package)

            # Step 7: Finalize
            self.telegram_bot.mark_news_processed(news_id)
            logger.info(f"  ✓ News item {news_id} marked as processed.")
            return True

        except Exception as e:
            logger.error(f"Critical error processing news {news_id}: {e}", exc_info=True)
            return False

    def _parse_publish_date(self, published_date: str) -> str:
        """Parses various date formats into a consistent string."""
        from datetime import datetime
        if not published_date:
            return datetime.now().strftime('%d.%m.%Y')
        try:
            if 'GMT' in published_date or 'UTC' in published_date:
                date_without_updated = published_date.split(' / Updated')[0]
                date_without_tz = date_without_updated.split(' GMT')[0].split(' UTC')[0]
                dt = datetime.strptime(date_without_tz, '%b. %d, %Y, %I:%M %p')
            elif 'T' in published_date:
                dt = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(published_date, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d.%m.%Y')
        except Exception:
            return datetime.now().strftime('%d.%m.%Y')

    def _process_media_for_news(self, news_data: Dict) -> Dict:
        """Selects a media manager and processes media for the given news item."""
        source = (news_data.get('source') or '').lower()
        # This logic can be expanded to a more robust factory pattern
        if 'politico' in source:
            from engines.politico.politico_media_manager import PoliticoMediaManager
            media_manager = PoliticoMediaManager(self.config)
        elif 'washington' in source:
            from engines.washingtonpost.washingtonpost_media_manager import WashingtonPostMediaManager
            media_manager = WashingtonPostMediaManager(self.config)
        elif 'twitter' in source:
            from engines.twitter.twitter_media_manager import TwitterMediaManager
            media_manager = TwitterMediaManager(self.config)
        elif 'nbc' in source:
            from engines.nbcnews.nbcnews_media_manager import NBCNewsMediaManager
            media_manager = NBCNewsMediaManager(self.config)
        elif 'telegram' in source:
            from engines.telegrampost.telegrampost_media_manager import TelegramPostMediaManager
            media_manager = TelegramPostMediaManager(self.config)
        elif 'financial' in source or 'ft' in source:
            from engines.financialtimes.financialtimes_media_manager import FinancialTimesMediaManager
            media_manager = FinancialTimesMediaManager(self.config)
        elif 'hill' in source:
            from engines.thehill.thehill_media_manager import TheHillMediaManager
            media_manager = TheHillMediaManager(self.config)
        elif 'new york post' in source or 'ny post' in source or 'nypost' in source:
            from engines.nypost.nypost_media_manager import NYPostMediaManager
            media_manager = NYPostMediaManager(self.config)
        # elif 'wsj' in source or 'wall street' in source:
        #     from engines.wsj.wsj_media_manager import WSJMediaManager
        #     media_manager = WSJMediaManager(self.config)
        else:
            from scripts.media_manager import MediaManager
            media_manager = MediaManager(self.config)
        
        return media_manager.process_news_media(news_data)


    def _export_video(self, news_id: int, video_package: Dict) -> Optional[str]:
        """Exports the video and returns the path."""
        logger.info(f"  Exporting video for news {news_id}...")
        output_filename = f"short_{news_id}_{int(time.time())}.mp4"
        output_path = os.path.join(self.config['paths']['outputs_dir'], output_filename)
        
        video_path = self.video_exporter.create_news_short_video(video_package, output_path)
        if not video_path:
            logger.error(f"  Video export failed for news {news_id}")
            self.stats['failed_videos'] += 1
            return None
        
        self.stats['successful_videos'] += 1
        logger.info(f"  ✓ Video created: {video_path}")
        return video_path

    def _upload_to_youtube(self, video_path: str, video_package: Dict):
        """Uploads the video to YouTube if enabled."""
        if not self.youtube_uploader:
            logger.info("  YouTube Uploader is not available, skipping upload.")
            return

        logger.info("  📤 Uploading video to YouTube...")
        seo_package = video_package.get('seo_package', {})
        source_name = video_package.get('source_info', {}).get('name', 'Unknown')

        youtube_metadata = {
            'title': seo_package.get('youtube_title', 'News Update')[:100],
            'description': seo_package.get('youtube_description', ''),
            'tags': seo_package.get('tags', ['news', 'shorts']),
            'category_id': '25',  # News & Politics
            'privacy_status': 'private',
            'source_name': source_name
        }

        video_url = self.youtube_uploader.upload_video_with_metadata(video_path, youtube_metadata)
        if video_url:
            logger.info(f"  ✅ Video uploaded to YouTube: {video_url}")
            self.stats['uploaded_videos'] += 1
        else:
            logger.error("  ❌ YouTube upload failed.")

    def _send_media_rejection_notification(self, news_id: int, news_data: Dict):
        """Отправляет уведомление о браковке видео из-за отсутствия медиа"""
        try:
            title = news_data.get('title', 'Unknown')[:50]
            source = news_data.get('source', 'Unknown')
            url = news_data.get('url', '')
            
            message = f"❌ **Видео забраковано**\n\n"
            message += f"📰 **Новость ID:** {news_id}\n"
            message += f"📝 **Заголовок:** {title}...\n"
            message += f"📡 **Источник:** {source}\n"
            message += f"🔗 **URL:** {url}\n\n"
            message += f"⚠️ **Причина:** Отсутствует медиа для шапки видео\n"
            message += f"📸 **Изображения:** {len(news_data.get('images', []))}\n"
            message += f"🎬 **Видео:** {len(news_data.get('videos', []))}\n\n"
            message += f"💡 **Рекомендация:** Проверьте парсинг медиа или добавьте fallback изображения"
            
            # Отправляем через Telegram Publisher
            if hasattr(self, 'telegram_publisher'):
                self.telegram_publisher.send_message(message)
                logger.info(f"📤 Отправлено уведомление о браковке новости {news_id}")
            else:
                logger.warning(f"⚠️ Telegram Publisher недоступен для отправки уведомления о браковке")
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о браковке: {e}")

            raise

    def _find_source_logo(self, source_name: str) -> Optional[str]:
        """Поиск логотипа источника"""
        # Проверяем, включены ли логотипы в конфигурации
        if not self.config.get('source_logos', {}).get('enabled', False):
            return None

        logo_dir = os.path.join(self.project_path, self.config['source_logos']['logo_dir'])

        if not os.path.exists(logo_dir):
            logger.warning(f"Директория логотипов не найдена: {logo_dir}")
            return None

        # Извлекаем домен из source_name
        domain = self._extract_domain(source_name)
        if not domain:
            return None

        # Ищем логотип по домену
        supported_formats = self.config['source_logos']['supported_formats']

        for ext in supported_formats:
            logo_path = os.path.join(logo_dir, f"{domain}.{ext}")
            if os.path.exists(logo_path):
                logger.info(f"Найден логотип для {domain}: {logo_path}")
                return logo_path

        # Если логотип не найден, возвращаем дефолтный
        default_logo = self.config['source_logos']['default_logo']
        default_path = os.path.join(self.project_path, default_logo)

        if os.path.exists(default_path):
            logger.info(f"Используем дефолтный логотип: {default_path}")
            return default_path

        logger.warning(f"Логотип для источника '{source_name}' не найден")
        return None

    def _extract_domain(self, source_name: str) -> Optional[str]:
        """Извлекает домен из URL или названия источника"""
        import re
        from urllib.parse import urlparse

        if not source_name:
            return None

        # Если это URL, извлекаем домен
        if '://' in source_name:
            try:
                parsed = urlparse(source_name)
                domain = parsed.netloc.lower()
                # Убираем www. если есть
                if domain.startswith('www.'):
                    domain = domain[4:]
                return domain.split('.')[0]  # Возвращаем только основную часть
            except:
                pass

        # Если это просто название, пытаемся найти совпадение
        source_lower = source_name.lower()

        # Известные источники и их домены
        known_sources = {
            'cnn': 'cnn',
            'bbc': 'bbc',
            'reuters': 'reuters',
            'ap': 'ap',
            'nyt': 'nyt',
            'washington post': 'washingtonpost',
            'guardian': 'guardian',
            'fox news': 'foxnews',
            'nbc': 'nbc',
            'abc': 'abc',
            'cbs': 'cbs'
        }

        for name, domain in known_sources.items():
            if name in source_lower:
                return domain

        # Если ничего не нашли, возвращаем очищенное название
        clean_name = re.sub(r'[^\w]', '', source_lower)
        return clean_name if clean_name else None

    def _validate_content_quality(self, video_data: Dict, news_data: Dict) -> bool:
        """Валидация качества контента перед созданием видео"""
        logger.info("🔍 Валидация качества контента...")
        
        # Проверяем основные поля - извлекаем из video_content
        video_content = video_data.get('video_content', {})
        title = video_content.get('title', '').strip()
        summary = video_content.get('summary', '').strip()
        description = video_data.get('description', '').strip()
        
        # Список проблем
        issues = []
        
        # 1. Проверка заголовка
        if not title or len(title) < 10:
            issues.append("Заголовок слишком короткий или отсутствует")
        elif len(title) > 300:  # Увеличиваем лимит для Twitter
            issues.append("Заголовок слишком длинный")
        elif title.lower() in ['breaking news', 'news', 'update', 'breaking']:
            issues.append("Заголовок слишком общий")
        
        # 2. Проверка текста новости
        if not summary or len(summary) < 50:
            issues.append("Текст новости слишком короткий или отсутствует")
        elif len(summary) > 2000:
            issues.append("Текст новости слишком длинный")
        
        # 3. Проверка на CAPTCHA и блокировку
        captcha_indicators = [
            "проверяем, человек ли вы",
            "please verify you are human",
            "checking your browser",
            "captcha",
            "cloudflare",
            "access denied",
            "verification required",
            "human verification",
            "you are blocked",
            "access blocked",
            "request blocked"
        ]
        
        summary_lower = summary.lower()
        for indicator in captcha_indicators:
            if indicator in summary_lower:
                issues.append(f"Обнаружена CAPTCHA/блокировка: '{indicator}'")
                break
        
        # 4. Проверка на заглушки LLM
        llm_placeholders = [
            "please provide the news article",
            "i need the text of the article",
            "i need the news story",
            "please provide the news",
            "i need the content",
            "please provide content",
            "i need more information",
            "please provide more details"
        ]
        
        for placeholder in llm_placeholders:
            if placeholder in summary_lower:
                issues.append(f"Обнаружена заглушка LLM: '{placeholder}'")
                break
        
        # 4. Проверка на повторяющиеся символы
        if len(set(summary)) < 10:  # Менее 10 уникальных символов
            issues.append("Текст содержит слишком мало уникальных символов")
        
        # 5. Проверка на пустые или служебные данные
        # Снижено с 100 до 70 для коротких статей (напр. FT с paywall)
        if not description or description in ['...', '']:
            if len(summary) < 70:  # Если нет описания, текст должен быть длиннее
                issues.append("Недостаточно контента для создания видео")
        
        # 6. Проверка на JSON в заголовке (ошибка LLM)
        if '{' in title and '}' in title:
            issues.append("Заголовок содержит JSON код (ошибка LLM)")
        
        # 7. Проверка на слишком много специальных символов
        special_chars = sum(1 for c in summary if not c.isalnum() and not c.isspace())
        if special_chars > len(summary) * 0.3:  # Более 30% специальных символов
            issues.append("Слишком много специальных символов в тексте")
        
        # 8. Проверка фактов (временно отключена)
        # fact_issues = self._validate_facts(title, summary, description)
        # issues.extend(fact_issues)
        
        # Логируем результат валидации
        if issues:
            logger.warning(f"❌ Контент не прошел валидацию:")
            for issue in issues:
                logger.warning(f"   - {issue}")
            logger.warning(f"📊 Статистика: заголовок={len(title)} символов, текст={len(summary)} символов")
            return False
        else:
            logger.info(f"✅ Контент прошел валидацию: заголовок={len(title)} символов, текст={len(summary)} символов")
            return True

    def run_continuous_mode(self):
        """Запуск в непрерывном режиме"""
        logger.info("🚀 Запуск системы в непрерывном режиме")
        logger.info(f"Интервал обновления: {self.config['news_parser']['update_interval_minutes']} минут")

        # Запуск первого цикла
        self.process_single_news_cycle()

        # Планирование регулярных запусков
        interval = self.config['news_parser']['update_interval_minutes']
        schedule.every(interval).minutes.do(self.process_single_news_cycle)

        # Основной цикл
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Проверка каждую минуту

        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал прерывания")
            self._print_final_stats()
            self.cleanup()

    def run_single_cycle(self):
        """Запуск одного цикла обработки"""
        logger.info("🔄 Запуск одиночного цикла обработки")
        self.process_single_news_cycle()
        self._print_final_stats()
        self.cleanup()

    def _print_final_stats(self):
        """Вывод финальной статистики"""
        runtime = time.time() - self.stats['start_time']
        logger.info("=" * 50)
        logger.info("📊 СТАТИСТИКА РАБОТЫ СИСТЕМЫ")
        logger.info("=" * 50)
        logger.info(f"⏱️  Время работы: {runtime:.1f} сек")
        logger.info(f"📰 Обработано новостей: {self.stats['processed_news']}")
        logger.info(f"🎬 Создано видео: {self.stats['successful_videos']}")
        logger.info(f"❌ Ошибок при создании видео: {self.stats['failed_videos']}")
        logger.info(f"⚠️ Пропущено низкокачественных: {self.stats['skipped_low_quality']}")
        logger.info(f"📸 Пропущено без медиа: {self.stats['skipped_no_media']}")
        logger.info(f"📤 Загружено на YouTube: {self.stats['uploaded_videos']}")

        if self.stats['processed_news'] > 0:
            success_rate = (self.stats['successful_videos'] / self.stats['processed_news']) * 100
            logger.info(f"📈 Успешность обработки: {success_rate:.1f}%")

    def cleanup(self):
        """Очистка ресурсов"""
        logger.info("🧹 Очистка ресурсов...")

        # Закрываем VideoExporter
        if self.video_exporter:
            try:
                self.video_exporter.close()
                logger.info("✓ VideoExporter закрыт")
            except Exception as e:
                logger.warning(f"Ошибка закрытия VideoExporter: {e}")

        # Закрываем другие компоненты
        if hasattr(self, 'telegram_bot') and self.telegram_bot:
            try:
                if hasattr(self.telegram_bot, 'close'):
                    self.telegram_bot.close()
                logger.info("✓ Telegram Bot закрыт")
            except Exception as e:
                logger.warning(f"Ошибка закрытия Telegram Bot: {e}")

        # Принудительная сборка мусора
        try:
            import gc
            gc.collect()
        except:
            pass

        logger.info("✅ Очистка завершена")

def create_env_file():
    """Создание .env файла с примером переменных окружения"""
    env_content = """# YouTube API Configuration
YOUTUBE_CLIENT_SECRET_FILE=config/client_secret.json

# Telegram Bot Configuration
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL=@your_channel

# LLM API Keys
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional: Twitter/X API (if using)
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
"""

    env_path = "config/.env"
    if not os.path.exists(env_path):
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        logger.info(f"Создан файл с примером переменных окружения: {env_path}")

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Shorts News System Orchestrator')
    parser.add_argument('--config', default='../config/config.yaml',
                       help='Путь к конфигурационному файлу')
    parser.add_argument('--mode', choices=['continuous', 'single'],
                       default='single', help='Режим работы')
    parser.add_argument('--create-env', action='store_true',
                       help='Создать пример .env файла')

    args = parser.parse_args()

    if args.create_env:
        create_env_file()
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
        # Создание оркестратора
        orchestrator = ShortsNewsOrchestrator(config_path)

        # Инициализация компонентов
        orchestrator.initialize_components()

        # Запуск в выбранном режиме
        if args.mode == 'continuous':
            orchestrator.run_continuous_mode()
        else:
            # ВРЕМЕННО ОТКЛЮЧЕНО для избежания дублирования с channel_monitor.py
            # orchestrator.run_single_cycle()
            logger.info("📢 Обработка новостей происходит через channel_monitor.py")
            logger.info("📢 Прямой запуск main_orchestrator.py временно отключен")

    except KeyboardInterrupt:
        logger.info("🛑 Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
