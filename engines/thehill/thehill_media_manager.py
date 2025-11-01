#!/usr/bin/env python3
"""
Специализированный MediaManager для источника The Hill
"""

from typing import Dict, Any, List

from scripts.media_manager import MediaManager
from logger_config import logger


class TheHillMediaManager(MediaManager):
    """The Hill-специфичная обработка медиа.

    Жестко фильтрует изображения: допускаются только URL с доменов The Hill
    и их CDN. Никаких стоков/unsplash и внешних картинок.
    """

    def process_news_media(self, news_data: Dict) -> Dict[str, str]:
        source_name = (news_data.get('source') or '').lower()
        if 'hill' not in source_name:
            # На всякий случай: если передали не The Hill, используем базовую логику
            return super().process_news_media(news_data)

        images = news_data.get('images', []) or []
        videos = news_data.get('videos', []) or []

        # Фильтруем изображения только на домены The Hill
        def normalize(item: Any) -> str:
            if isinstance(item, dict):
                return item.get('url') or item.get('src') or ''
            return item or ''

        # Разрешаем изображения с доменов The Hill и их CDN
        allowed_substrings = [
            'thehill.com',
            'www.thehill.com',
            'wp-content/uploads',  # WordPress uploads
            'cdn.thehill.com',
        ]
        
        filtered_images: List[Any] = []
        for it in images:
            u = normalize(it).lower()
            if any(sub in u for sub in allowed_substrings):
                filtered_images.append(it)

        if filtered_images:
            news_data = {**news_data, 'images': filtered_images}
        else:
            # Если нет валидных изображений, сбрасываем, чтобы верхний уровень забраковал новость
            logger.warning("The Hill: нет валидных изображений с домена источника — отклоняем медиа")
            news_data = {**news_data, 'images': []}

        # Дальше используем базовую загрузку/обработку
        result = super().process_news_media(news_data)
        
        # Устанавливаем путь к логотипу The Hill
        result['avatar_path'] = 'resources/logos/thehill.png'
        
        return result

