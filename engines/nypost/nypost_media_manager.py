#!/usr/bin/env python3
"""
Специализированный MediaManager для источника New York Post
"""

from typing import Dict, Any, List
import os

from scripts.media_manager import MediaManager
from logger_config import logger


class NYPostMediaManager(MediaManager):
    """NY Post-специфичная обработка медиа.
    
    Фильтрует изображения: допускаются только URL с доменов NY Post
    и их CDN. Устанавливает правильный путь к логотипу NY Post.
    """

    def process_news_media(self, news_data: Dict) -> Dict[str, str]:
        source_name = (news_data.get('source') or '').lower()
        if 'new york post' not in source_name and 'ny post' not in source_name and 'nypost' not in source_name:
            # Если передали не NY Post, используем базовую логику
            return super().process_news_media(news_data)

        images = news_data.get('images', []) or []
        videos = news_data.get('videos', []) or []

        # Фильтруем изображения только на домены NY Post
        def normalize(item: Any) -> str:
            if isinstance(item, dict):
                return item.get('url') or item.get('src') or ''
            return item or ''

        # Разрешаем изображения с доменов NY Post и их CDN
        allowed_substrings = [
            'nypost.com',
            'www.nypost.com',
            'pagesix.com',  # Часть NY Post
            'wp-content/uploads',  # WordPress uploads
            'cdn.nypost.com',
            'thenypost.files.wordpress.com',
        ]
        
        filtered_images: List[Any] = []
        for it in images:
            u = normalize(it).lower()
            if any(sub in u for sub in allowed_substrings):
                filtered_images.append(it)

        if filtered_images:
            news_data = {**news_data, 'images': filtered_images}
        else:
            # Если нет валидных изображений, сбрасываем
            logger.warning("NY Post: нет валидных изображений с домена источника")
            news_data = {**news_data, 'images': []}

        # Используем базовую загрузку/обработку
        result = super().process_news_media(news_data)
        
        # Устанавливаем путь к логотипу NY Post
        avatar_path = 'resources/logos/avatar_nypost.png'
        
        # Проверяем существование файла
        if os.path.exists(avatar_path):
            result['avatar_path'] = avatar_path
            logger.info(f"✅ NY Post логотип установлен: {avatar_path}")
        else:
            logger.warning(f"⚠️ NY Post логотип не найден по пути: {avatar_path}")
            result['avatar_path'] = avatar_path  # Все равно устанавливаем, может быть относительный путь
        
        return result

