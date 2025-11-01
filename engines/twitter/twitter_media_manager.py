"""
Twitter Media Manager для обработки медиа из Twitter/X
"""

import logging
import re
from typing import Dict, List, Any
from pathlib import Path
from bs4 import BeautifulSoup

# Настройка логирования для подавления предупреждений
try:
    from selenium_logging_config import configure_selenium_logging
    configure_selenium_logging()
except ImportError:
    pass
from scripts.media_manager import MediaManager
from scripts.video_preprocessor import VideoPreprocessor

logger = logging.getLogger(__name__)


class TwitterMediaManager(MediaManager):
    """Специализированный медиа-менеджер для Twitter"""
    
    def process_news_media(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает медиа для Twitter новостей
        
        Args:
            news_data: Данные новости с изображениями и видео
            
        Returns:
            Словарь с результатами обработки медиа
        """
        logger.info("🐦 Обработка Twitter медиа...")
        
        # Получаем изображения и видео
        images = news_data.get('images', [])
        videos = news_data.get('videos', [])
        tweet_url = news_data.get('url', '')
        
        # В Twitter видео добавляются в images, разделяем их
        video_images = []
        regular_images = []
        
        for img in images:
            if any(ext in img.lower() for ext in ['.mp4', 'video', 'amplify_video']):
                video_images.append(img)
            else:
                regular_images.append(img)
        
        # Обновляем списки
        images = regular_images
        # Добавляем видео из images к существующим videos
        videos = videos + video_images
        
        # Также проверяем videos на наличие локальных файлов
        url_videos = []
        local_videos = []
        
        logger.info(f"🔍 DEBUG: Обрабатываем {len(videos)} видео элементов:")
        for i, vid in enumerate(videos):
            logger.info(f"  [{i}] {vid}")
            if vid.startswith('http'):
                url_videos.append(vid)
                logger.info(f"    → URL видео")
            elif vid.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                local_videos.append(vid)
                logger.info(f"    → Локальный файл")
            else:
                url_videos.append(vid)  # Оставляем как есть для дальнейшей обработки
                logger.info(f"    → Неизвестный тип, добавляем как URL")
        
        # Объединяем URL видео и локальные видео
        videos = url_videos + local_videos
        logger.info(f"🔍 DEBUG: Итого видео: {len(videos)} (URL: {len(url_videos)}, локальные: {len(local_videos)})")
        
        logger.info(f"📸 Найдено {len(images)} изображений, {len(videos)} видео")
        
        
        # Фильтруем изображения для Twitter
        if images:
            filtered_images = self._filter_twitter_images(images)
            if filtered_images:
                images = filtered_images
                logger.info(f"✅ Отфильтровано {len(images)} Twitter изображений")
            else:
                logger.warning("❌ Twitter: нет подходящих изображений")
                images = []
        
        # Фильтруем видео для Twitter
        if videos:
            filtered_videos = self._filter_twitter_videos(videos)
            if filtered_videos:
                videos = filtered_videos
                logger.info(f"✅ Отфильтровано {len(videos)} Twitter видео")
            else:
                logger.warning("❌ Twitter: нет подходящих видео")
                videos = []
        
        # Обновляем данные новости
        news_data['images'] = images
        news_data['videos'] = videos
        
        # Получаем данные пользователя
        username = news_data.get('username', '')
        avatar_url = news_data.get('avatar_url', '')
        
        # Скачиваем аватар пользователя для Twitter
        avatar_path = None
        if avatar_url:
            logger.info(f"👤 Скачиваем аватар для @{username} по URL: {avatar_url}")
            avatar_path = self._download_twitter_avatar(avatar_url, username)
            if avatar_path:
                logger.info(f"✅ Аватар скачан: {avatar_path}")
            else:
                logger.warning(f"❌ Не удалось скачать аватар для @{username}")
        
        # Обрабатываем медиа самостоятельно для Twitter
        result = self._process_twitter_media_directly(news_data, avatar_path)
        
        logger.info(f"🐦 Twitter медиа обработано: has_media={result.get('has_media', False)}")
        
        return result
    
    def _process_twitter_media_directly(self, news_data: Dict, avatar_path: str = None) -> Dict:
        """
        Прямая обработка медиа для Twitter без использования базового класса
        
        Args:
            news_data: Данные новости
            
        Returns:
            Результат обработки медиа
        """
        result = {
            'primary_image': None,
            'video_url': None,
            'thumbnail': None,
            'local_image_path': None,
            'local_video_path': None,
            'avatar_path': None,
            'has_media': False,
            'has_video': False,
            'has_images': False,
            'video_offset': None
        }
        
        try:
            images = news_data.get('images', [])
            videos = news_data.get('videos', [])
            username = news_data.get('username', '')
            avatar_url = news_data.get('avatar_url', '')
            video_offset = news_data.get('video_start_seconds')

            if video_offset not in (None, ''):
                try:
                    video_offset = float(video_offset)
                    if video_offset < 0:
                        logger.warning(f"⚠️ Игнорируем отрицательный video_offset={video_offset} для Twitter видео")
                        video_offset = None
                except (TypeError, ValueError):
                    logger.warning(f"⚠️ Неверный формат video_offset={video_offset} для Twitter видео")
                    video_offset = None
            else:
                video_offset = None

            # Обрабатываем изображения
            if images:
                image_url = images[0]
                logger.info(f"🖼️ Скачиваем Twitter изображение: {image_url[:50]}...")
                local_image_path = self._download_image_direct(image_url, news_data.get('title', 'Twitter Image'))
                if local_image_path:
                    result.update({
                        'primary_image': image_url,
                        'local_image_path': local_image_path,
                        'thumbnail': local_image_path,
                        'has_media': True,
                        'has_images': True
                    })
                    logger.info(f"✅ Twitter изображение скачано: {local_image_path}")
            
            # Обрабатываем видео - сначала ищем локальные файлы
            if videos:
                local_video_path = None
                tweet_url = news_data.get('url', '')
                
                # Сначала ищем локальные видео файлы
                for video_item in videos:
                    if video_item.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                        # Проверяем что файл существует
                        if Path(video_item).exists():
                            local_video_path = video_item
                            logger.info(f"🎬 Найден существующий локальный видео файл: {local_video_path}")
                            break
                
                # Если нашли локальный файл, устанавливаем результат
                if local_video_path:
                    result.update({
                        'primary_video': local_video_path,
                        'local_video_path': local_video_path,
                        'has_media': True,
                        'has_videos': True,
                        'video_offset': video_offset
                    })
                    logger.info(f"✅ Используем существующий локальный видео файл: {local_video_path}")
                
                # Если локального файла нет, скачиваем
                if not local_video_path:
                    video_url = None
                    # Берем первый URL видео (не thumbnail)
                    for video_item in videos:
                        if video_item.startswith('http') and not any(thumb in video_item.lower() for thumb in ['thumb', 'preview', 'poster']):
                            video_url = video_item
                            break
                    
                    # Если не нашли подходящий URL, берем первый URL элемент
                    if not video_url:
                        for video_item in videos:
                            if video_item.startswith('http'):
                                video_url = video_item
                                break
                    
                    if video_url:
                        # Для Twitter видео сначала пробуем yt-dlp с URL твита
                        if tweet_url and ('twitter.com' in tweet_url or 'x.com' in tweet_url):
                            logger.info(f"🎬 Скачиваем Twitter видео через yt-dlp: {tweet_url[:50]}...")
                            local_video_path = self._download_twitter_video_with_ytdlp(tweet_url, news_data.get('title', 'Twitter Video'))
                            
                            # Если yt-dlp не сработал, пробуем Selenium с URL твита
                            if not local_video_path:
                                logger.info(f"🔄 yt-dlp не сработал, пробуем Selenium с URL твита: {tweet_url[:50]}...")
                                local_video_path = self._download_twitter_video_selenium(tweet_url, news_data.get('title', 'Twitter Video'))
                        else:
                            logger.info(f"🎬 Скачиваем Twitter видео напрямую: {video_url[:50]}...")
                            local_video_path = self._download_twitter_video_direct(video_url, news_data.get('title', 'Twitter Video'))
                        
                        # Если все еще не получилось, пробуем прямую загрузку только если это не thumbnail
                        if not local_video_path and video_url and not any(thumb in video_url.lower() for thumb in ['thumb', 'preview', 'poster']):
                            local_video_path = self._download_twitter_video_direct(video_url, news_data.get('title', 'Twitter Video'))
                
                # Если ничего не сработало, пробуем скачать из videos массива
                if not local_video_path and videos:
                    for video in videos:
                        if not any(thumb in video.lower() for thumb in ['thumb', 'preview', 'poster']):
                            logger.info(f"🔄 Пробуем скачать видео из videos массива: {video[:50]}...")
                            local_video_path = self._download_twitter_video_direct(video, news_data.get('title', 'Twitter Video'))
                            if local_video_path:
                                break
                
                # Проверяем .part файлы в папке media/news
                if not local_video_path:
                    logger.info("🔍 Проверяем .part файлы в папке media/news...")
                    part_files = list(self.media_dir.glob("*.part"))
                    if part_files:
                        # Берем самый новый .part файл
                        latest_part = max(part_files, key=lambda x: x.stat().st_mtime)
                        logger.info(f"🔄 Найден .part файл: {latest_part.name}")
                        
                        # Переименовываем .part в .mp4
                        mp4_path = latest_part.with_suffix('')
                        try:
                            latest_part.rename(mp4_path)
                            logger.info(f"✅ .part файл переименован: {mp4_path.name}")
                            local_video_path = str(mp4_path)
                        except Exception as e:
                            logger.warning(f"❌ Ошибка переименования .part файла: {e}")
                
                if local_video_path:
                    # Предобработка видео (обрезка и преобразование в GIF)
                    processed_video_path = self._preprocess_video(local_video_path)
                    
                    result.update({
                        'video_url': video_url if 'video_url' in locals() else None,
                        'local_video_path': processed_video_path or local_video_path,  # Используем обработанное видео или оригинал
                        'thumbnail': processed_video_path or local_video_path,
                        'has_media': True,
                        'has_video': True,
                        'video_offset': video_offset
                    })
                    logger.info(f"✅ Twitter видео скачано: {local_video_path}")
                    if processed_video_path:
                        logger.info(f"✅ Видео предобработано: {processed_video_path}")
                else:
                    logger.warning("❌ Не удалось скачать Twitter видео")
            
            # Добавляем аватар в результат
            logger.info(f"🔍 DEBUG Avatar path: {avatar_path}")
            if avatar_path:
                result['avatar_path'] = avatar_path
                logger.info(f"🔍 DEBUG Avatar added to result: {result.get('avatar_path')}")
            else:
                logger.warning("🔍 DEBUG Avatar path is None, not adding to result")
            
            logger.info(f"🔍 DEBUG Final result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки Twitter медиа: {e}")
            return result
    
    def _download_image_direct(self, image_url: str, news_title: str) -> str:
        """
        Прямое скачивание изображения с попытками очистки URL
        """
        import requests
        from pathlib import Path

        logger.info(f"📥 Скачиваем изображение: {image_url[:80]}...")

        # List of URLs to try
        urls_to_try = [image_url]
        if 'pbs.twimg.com' in image_url:
            base_url = image_url.split('?')[0]
            # Add variations
            urls_to_try.append(f"{base_url}?format=jpg&name=large")
            urls_to_try.append(f"{base_url}?format=png&name=large")
            urls_to_try.append(base_url) # Try without any params

        # Remove duplicates
        urls_to_try = list(dict.fromkeys(urls_to_try))

        for i, url in enumerate(urls_to_try):
            try:
                logger.info(f"🔄 Попытка {i+1}/{len(urls_to_try)}: скачиваем {url[:80]}...")
                
                response = requests.get(url, stream=True, timeout=15)
                response.raise_for_status()
                
                safe_title = "".join(c for c in news_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title[:50]
                
                # Determine file extension
                content_type = response.headers.get('content-type')
                if content_type and 'image' in content_type:
                    ext = content_type.split('/')[1].split(';')[0]
                    if ext not in ['jpeg', 'png', 'gif', 'webp']:
                        ext = 'jpg'
                else:
                    ext = 'jpg'

                output_path = self.media_dir / f"{safe_title}_{hash(url) % 1000000}.{ext}"

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = output_path.stat().st_size
                if file_size < 2048:  # Increase threshold to 2KB
                    output_path.unlink()
                    raise ValueError(f"File too small ({file_size} bytes), likely an error page.")
                
                logger.info(f"✅ Изображение скачано (попытка {i+1}): {output_path} (размер: {file_size / 1024:.1f}KB)")
                return str(output_path)

            except Exception as e:
                logger.warning(f"⚠️ Попытка {i+1} не удалась: {e}")
                continue # Try next URL

        logger.error(f"❌ Не удалось скачать изображение после {len(urls_to_try)} попыток.")
        return None
    
    def _filter_twitter_images(self, images: List[str]) -> List[str]:
        """
        Фильтрует изображения для Twitter
        
        Args:
            images: Список URL изображений
            
        Returns:
            Отфильтрованный список изображений
        """
        if not images:
            return []
        
        def normalize(url_or_obj):
            if isinstance(url_or_obj, dict):
                return url_or_obj.get('url') or url_or_obj.get('src') or ''
            return url_or_obj or ''
        
        # Разрешенные домены для Twitter
        allowed_substrings = [
            'pbs.twimg.com',  # Twitter CDN для изображений
            'abs.twimg.com',  # Twitter CDN
            'video.twimg.com',  # Twitter CDN для видео
            'ton.twimg.com',  # Twitter CDN
            'x.com',  # X.com
            'twitter.com'  # Twitter.com
        ]
        
        filtered_images = []
        for img in images:
            url = normalize(img).lower()
            if any(sub in url for sub in allowed_substrings):
                # Исключаем аватары и служебные изображения
                if not any(exclude in url for exclude in ['profile_images', 'emoji', 'sprite', 'icon']):
                    filtered_images.append(img)
        
        return filtered_images
    
    def _filter_twitter_videos(self, videos: List[str]) -> List[str]:
        """
        Фильтрует видео для Twitter
        
        Args:
            videos: Список URL видео
            
        Returns:
            Отфильтрованный список видео
        """
        if not videos:
            return []
        
        def normalize(url_or_obj):
            if isinstance(url_or_obj, dict):
                return url_or_obj.get('url') or url_or_obj.get('src') or ''
            return url_or_obj or ''
        
        # Разрешенные домены для Twitter видео
        allowed_substrings = [
            'pbs.twimg.com',  # Twitter CDN для видео (основной)
            'video.twimg.com',  # Twitter CDN для видео
            'abs.twimg.com',  # Twitter CDN
            'x.com',  # X.com
            'twitter.com'  # Twitter.com
        ]
        
        filtered_videos = []
        for video in videos:
            # Проверяем, является ли это локальным файлом
            if video.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                # Это локальный файл, добавляем без фильтрации
                filtered_videos.append(video)
            else:
                # Это URL, применяем фильтрацию
                url = normalize(video).lower()
                if any(sub in url for sub in allowed_substrings):
                    filtered_videos.append(video)
        
        return filtered_videos
    
    def _download_twitter_video_with_ytdlp(self, video_url: str, news_title: str) -> str:
        """
        Скачивание Twitter видео через yt-dlp
        
        Args:
            video_url: URL твита
            news_title: Заголовок новости
            
        Returns:
            Путь к скачанному видео или None
        """
        try:
            import subprocess
            import json
            from pathlib import Path
            
            # Создаем безопасное имя файла
            safe_title = "".join(c for c in news_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50]  # Ограничиваем длину
            
            output_path = self.media_dir / f"{safe_title}_{hash(video_url) % 1000000}.mp4"
            part_path = output_path.with_suffix(output_path.suffix + '.part')
            
            # Проверяем, есть ли уже .part файл от предыдущей попытки
            if part_path.exists():
                logger.info(f"🔄 Найден существующий .part файл, ждем его завершения...")
                import time
                start_time = time.time()
                last_size = 0
                stable_count = 0
                
                while part_path.exists() and (time.time() - start_time) < 60:
                    current_size = part_path.stat().st_size
                    if current_size == last_size:
                        stable_count += 1
                        if stable_count >= 5:
                            logger.info(f"✅ Размер файла стабилизировался, переименовываем .part файл")
                            break
                    else:
                        stable_count = 0
                        last_size = current_size
                        logger.info(f"📊 Размер .part файла: {current_size / 1024 / 1024:.1f}MB")
                    
                    time.sleep(1)
                
                # Переименовываем .part файл в финальный
                if part_path.exists():
                    part_path.rename(output_path)
                    logger.info(f"✅ .part файл переименован в финальный")
                
                # Проверяем финальный файл
                if output_path.exists():
                    try:
                        from moviepy.editor import VideoFileClip
                        with VideoFileClip(str(output_path)) as clip:
                            duration = clip.duration
                            if duration > 600:  # 10 минут для Twitter видео
                                logger.warning(f"⚠️ Видео слишком длинное ({duration:.1f}с), удаляем")
                                output_path.unlink()
                                return None
                            
                            logger.info(f"✅ Twitter видео загружено через yt-dlp: {output_path} (длительность: {duration:.1f}с)")
                            return str(output_path)
                    except ImportError:
                        logger.info(f"✅ Twitter видео загружено через yt-dlp: {output_path}")
                        return str(output_path)
            
            # Команда yt-dlp с упрощенными настройками для Twitter
            cmd = [
                'yt-dlp',
                '--format', 'best',  # Простой выбор лучшего качества
                '--output', str(output_path),
                '--no-playlist',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--socket-timeout', '60',  # Уменьшаем таймаут
                '--retries', '2',  # Меньше попыток
                '--no-check-certificate',  # Игнорируем SSL ошибки
                video_url
            ]
            
            logger.info(f"🔄 Пробуем yt-dlp для Twitter видео: {video_url[:50]}...")
            
            # Сначала проверяем доступность видео
            logger.info(f"🔍 Проверяем доступность видео...")
            check_cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-playlist',
                '--extractor-args', 'twitter:api=syndication',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                video_url
            ]
            
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=30)
            
            if check_result.returncode != 0:
                logger.warning(f"⚠️ Видео недоступно: {check_result.stderr}")
                return None
            
            try:
                video_info = json.loads(check_result.stdout)
                duration = video_info.get('duration', 0)
                
                if duration > 600:  # 10 минут для Twitter видео
                    logger.warning(f"⚠️ Видео слишком длинное ({duration:.1f}с), пропускаем")
                    return None
                
                logger.info(f"📊 Видео доступно, длительность: {duration:.1f}с")
                
            except json.JSONDecodeError:
                logger.warning("⚠️ Не удалось получить информацию о видео, пробуем загрузить...")
            
            # Запускаем yt-dlp с увеличенным таймаутом
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            # Проверяем, что файл скачался (включая .part файлы)
            final_path = output_path
            part_path = output_path.with_suffix(output_path.suffix + '.part')
            
            # Если есть .part файл, ждем его завершения
            if part_path.exists():
                logger.info(f"⏳ Найден .part файл, ждем завершения скачивания...")
                import time
                start_time = time.time()
                last_size = 0
                stable_count = 0
                
                while part_path.exists() and (time.time() - start_time) < 60:  # Ждем до 60 секунд
                    current_size = part_path.stat().st_size
                    if current_size == last_size:
                        stable_count += 1
                        if stable_count >= 5:  # Размер не менялся 5 секунд
                            logger.info(f"✅ Размер файла стабилизировался, переименовываем .part файл")
                            break
                    else:
                        stable_count = 0
                        last_size = current_size
                        logger.info(f"📊 Размер .part файла: {current_size / 1024 / 1024:.1f}MB")
                    
                    time.sleep(1)
                
                # Переименовываем .part файл в финальный
                if part_path.exists():
                    part_path.rename(output_path)
                    final_path = output_path
                    logger.info(f"✅ .part файл переименован в финальный")
                elif output_path.exists():
                    final_path = output_path
                    logger.info(f"✅ .part файл обработан, используем финальный файл")
            
            # Проверяем наличие файла независимо от кода возврата yt-dlp
            logger.info(f"🔍 Проверяем файл: {final_path} (существует: {final_path.exists()})")
            if part_path.exists():
                logger.info(f"🔍 .part файл: {part_path} (существует: {part_path.exists()})")
            
            if final_path.exists():
                # Проверяем размер и длительность файла
                try:
                    from moviepy.editor import VideoFileClip
                    with VideoFileClip(str(final_path)) as clip:
                        duration = clip.duration
                        if duration > 600:  # 10 минут для Twitter видео
                            logger.warning(f"⚠️ Видео слишком длинное ({duration:.1f}с), удаляем")
                            final_path.unlink()
                            return None
                        
                        logger.info(f"✅ Twitter видео загружено через yt-dlp: {final_path} (длительность: {duration:.1f}с)")
                        return str(final_path)
                except ImportError:
                    logger.info(f"✅ Twitter видео загружено через yt-dlp: {final_path}")
                    return str(final_path)
            else:
                logger.warning(f"⚠️ yt-dlp не смог загрузить видео: {result.stderr}")
                # Очищаем .part файл если он остался
                if part_path.exists():
                    part_path.unlink()
                return None
                
        except FileNotFoundError:
            logger.warning("⚠️ yt-dlp не установлен. Установите: pip install yt-dlp")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка yt-dlp для Twitter видео: {e}")
            return None
    
    def _download_twitter_video_direct(self, video_url: str, news_title: str) -> str:
        """
        Прямая загрузка Twitter видео с pbs.twimg.com
        
        Args:
            video_url: URL твита
            news_title: Заголовок новости
            
        Returns:
            Путь к скачанному видео или None
        """
        try:
            import requests
            from pathlib import Path
            
            # Создаем безопасное имя файла
            safe_title = "".join(c for c in news_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50]  # Ограничиваем длину
            
            output_path = self.media_dir / f"{safe_title}_{hash(video_url) % 1000000}.mp4"
            
            # Заголовки для обхода блокировок
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'video/mp4,video/*,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            logger.info(f"🔄 Прямая загрузка Twitter видео: {video_url[:50]}...")
            
            # Загружаем видео
            response = requests.get(video_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Сохраняем видео
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Проверяем размер файла
            file_size = output_path.stat().st_size
            if file_size > 100 * 1024 * 1024:  # 100MB
                logger.warning(f"⚠️ Видео слишком большое ({file_size / 1024 / 1024:.1f}MB), удаляем")
                output_path.unlink()
                return None
            
            logger.info(f"✅ Twitter видео загружено напрямую: {output_path} (размер: {file_size / 1024 / 1024:.1f}MB)")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ Ошибка прямой загрузки Twitter видео: {e}")
            return None
    
    def _download_twitter_video_selenium(self, video_url: str, news_title: str) -> str:
        """
        Альтернативный метод скачивания Twitter видео через Selenium
        
        Args:
            video_url: URL твита
            news_title: Заголовок новости
            
        Returns:
            Путь к скачанному видео или None
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import requests
            from pathlib import Path
            import time
            
            # Создаем безопасное имя файла
            safe_title = "".join(c for c in news_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50]
            
            output_path = self.media_dir / f"{safe_title}_{hash(video_url) % 1000000}.mp4"
            
            logger.info(f"🌐 Selenium скачивание Twitter видео: {video_url[:50]}...")
            
            # Настройки Chrome
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-gpu-sandbox')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-webgl')
            chrome_options.add_argument('--disable-webgl2')
            chrome_options.add_argument('--disable-3d-apis')
            chrome_options.add_argument('--disable-accelerated-2d-canvas')
            chrome_options.add_argument('--disable-accelerated-jpeg-decoding')
            chrome_options.add_argument('--disable-accelerated-mjpeg-decode')
            chrome_options.add_argument('--disable-accelerated-video-decode')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--log-level=3')  # Только критические ошибки
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # Открываем страницу твита
                driver.get(video_url)
                time.sleep(10)  # Увеличиваем время ожидания
                
                # Ждем загрузки видео
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "video"))
                    )
                    logger.info("✅ Видео элемент загружен")
                except:
                    logger.warning("⚠️ Видео элемент не загрузился за 15 секунд")
                
                # Ищем видео элементы разными способами
                video_elements = driver.find_elements(By.TAG_NAME, "video")
                
                # Если не нашли video теги, ищем в data-атрибутах
                if not video_elements:
                    video_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='videoPlayer'] video")
                
                if not video_elements:
                    video_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweet'] video")
                
                if not video_elements:
                    video_elements = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='videoComponent'] video")
                
                if video_elements:
                    logger.info(f"🎥 Найдено {len(video_elements)} видео элементов")
                    
                    for i, video_element in enumerate(video_elements):
                        logger.info(f"🔍 Анализируем видео элемент {i+1}...")
                        
                        # Пробуем кликнуть на видео для активации
                        try:
                            driver.execute_script("arguments[0].click();", video_element)
                            time.sleep(2)
                            logger.info(f"🖱️ Кликнули на видео {i+1}")
                        except:
                            pass
                        
                        # Пробуем разные атрибуты
                        video_src = (video_element.get_attribute("src") or 
                                   video_element.get_attribute("data-src") or
                                   video_element.get_attribute("data-video-url") or
                                   video_element.get_attribute("poster") or
                                   video_element.get_attribute("data-poster"))
                        
                        # Если нет src, пробуем получить из currentSrc
                        if not video_src:
                            try:
                                video_src = driver.execute_script("return arguments[0].currentSrc;", video_element)
                            except:
                                pass
                        
                        # Если все еще нет src, пробуем получить из всех атрибутов
                        if not video_src:
                            all_attrs = driver.execute_script("""
                                var attrs = {};
                                for (var i = 0; i < arguments[0].attributes.length; i++) {
                                    var attr = arguments[0].attributes[i];
                                    attrs[attr.name] = attr.value;
                                }
                                return attrs;
                            """, video_element)
                            
                            for attr_name, attr_value in all_attrs.items():
                                if isinstance(attr_value, str) and ('mp4' in attr_value or 'video' in attr_value) and attr_value.startswith('http'):
                                    video_src = attr_value
                                    logger.info(f"🔍 Найден URL в атрибуте {attr_name}: {video_src[:50]}...")
                                    break
                        
                        if video_src and video_src.startswith('http'):
                            # Исключаем thumbnail URLs
                            if any(thumb in video_src.lower() for thumb in ['thumb', 'preview', 'poster', 'static']):
                                logger.warning(f"⚠️ Пропускаем thumbnail: {video_src[:50]}...")
                                continue
                                
                            logger.info(f"🎥 Найдено видео {i+1}: {video_src[:50]}...")
                            
                            try:
                                # Скачиваем видео
                                response = requests.get(video_src, stream=True, timeout=60)
                                response.raise_for_status()
                                
                                with open(output_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                
                                file_size = output_path.stat().st_size
                                # Проверяем, что файл достаточно большой (не thumbnail)
                                if file_size < 1024 * 1024:  # Меньше 1MB - вероятно thumbnail
                                    logger.warning(f"⚠️ Скачанный файл слишком маленький ({file_size} байт), возможно это thumbnail")
                                    output_path.unlink()
                                    continue
                                
                                logger.info(f"✅ Twitter видео скачано через Selenium: {output_path} (размер: {file_size / 1024 / 1024:.1f}MB)")
                                return str(output_path)
                                
                            except Exception as e:
                                logger.warning(f"❌ Ошибка скачивания видео {i+1}: {e}")
                                continue
                        else:
                            logger.warning(f"❌ Видео {i+1} не имеет валидного src. Атрибуты: {video_element.get_attribute('outerHTML')[:200]}...")
                else:
                    logger.warning("❌ Видео элементы не найдены на странице")
                    # Попробуем найти прямые ссылки на видео в HTML
                    page_source = driver.page_source
                    import re
                    video_urls = re.findall(r'https://[^"\s]*\.mp4[^"\s]*', page_source)
                    if video_urls:
                        logger.info(f"🔍 Найдено {len(video_urls)} прямых ссылок на видео в HTML")
                        for video_url in video_urls[:3]:  # Берем первые 3
                            try:
                                logger.info(f"🎥 Пробуем скачать: {video_url[:50]}...")
                                response = requests.get(video_url, stream=True, timeout=60)
                                response.raise_for_status()
                                
                                with open(output_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                
                                file_size = output_path.stat().st_size
                                if file_size > 1024:  # Больше 1KB - успех
                                    logger.info(f"✅ Twitter видео скачано через HTML поиск: {output_path} (размер: {file_size / 1024 / 1024:.1f}MB)")
                                    return str(output_path)
                                
                            except Exception as e:
                                logger.warning(f"❌ Ошибка скачивания HTML видео: {e}")
                                continue
                    
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка Selenium скачивания Twitter видео: {e}")
            return None
    
    def _download_twitter_avatar(self, avatar_url: str, username: str) -> str:
        """
        Скачивает аватар пользователя Twitter по прямому URL.

        Args:
            avatar_url: Прямой URL аватара.
            username: Имя пользователя для сохранения файла.

        Returns:
            Путь к скачанному аватару или None.
        """
        import requests

        if not avatar_url:
            logger.warning("⚠️ URL аватара не предоставлен.")
            return None

        try:
            safe_username = "".join(c for c in username if c.isalnum() or c in ('_', '-')).rstrip()
            logos_dir = Path("resources/logos")
            logos_dir.mkdir(parents=True, exist_ok=True)
            output_path = logos_dir / f"avatar_{safe_username}.png"

            if output_path.exists():
                logger.info(f"✅ Аватар для @{username} уже существует: {output_path}")
                return str(output_path)

            logger.info(f"👤 Скачиваем аватар для @{username}...")

            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            response = session.get(avatar_url, stream=True, timeout=30)
            response.raise_for_status()

            temp_path = output_path.with_suffix('.tmp')
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            if self._optimize_avatar_image(temp_path, output_path):
                logger.info(f"✅ Аватар для @{username} успешно скачан и сохранен: {output_path}")
                return str(output_path)
            else:
                logger.error(f"❌ Ошибка оптимизации аватара для @{username}")
                if temp_path.exists():
                    temp_path.unlink()
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка скачивания аватара для @{username} с URL {avatar_url}: {e}")
            return None

    def _optimize_avatar_image(self, input_path: Path, output_path: Path) -> bool:
        """
        Оптимизирует аватар (конвертация в PNG, изменение размера).
        """
        try:
            from PIL import Image
            with Image.open(input_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                max_size = (200, 200)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                img.save(output_path, 'PNG', optimize=True)
            
            if input_path.exists():
                input_path.unlink()

            return True
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации аватара {input_path}: {e}")
            return False
    
    def _preprocess_video(self, video_path: str) -> str:
        """
        Предобработка видео: обрезка до 6 секунд и преобразование в MP4.
        
        Args:
            video_path: Путь к исходному видео
            
        Returns:
            Путь к обработанному MP4 или None при ошибке
        """
        try:
            # Проверяем, не обработано ли уже видео
            if '_processed_' in video_path:
                logger.info(f"Видео уже обработано, пропускаем: {video_path}")
                return None
                
            # Проверяем, включена ли предобработка
            video_config = self.config.get('video', {})
            preprocessing_config = video_config.get('preprocessing', {})
            
            if not preprocessing_config.get('enabled', False):
                logger.info("Предобработка видео отключена в конфигурации")
                return None
                
            if not self.video_preprocessor:
                logger.warning("VideoPreprocessor не инициализирован")
                return None
            
            # Получаем параметры из конфигурации
            offset_seconds = preprocessing_config.get('offset_seconds', 0)
            target_duration = preprocessing_config.get('target_duration', 6)
            output_fps = preprocessing_config.get('output_fps', 12)
            convert_to_gif = preprocessing_config.get('convert_to_gif', True)
            
            logger.info(f"🎬 Предобработка видео: {video_path}")
            logger.info(f"Параметры: смещение={offset_seconds}с, длительность={target_duration}с, FPS={output_fps}")
            
            # Обрабатываем видео
            processed_path = self.video_preprocessor.preprocess_video(
                video_path,
                offset_seconds=offset_seconds,
                target_duration=target_duration
                # fps берется из конфигурации автоматически
            )
            
            if processed_path:
                logger.info(f"✅ Видео успешно предобработано: {processed_path}")
                return processed_path
            else:
                logger.warning("❌ Предобработка видео не удалась, используем оригинал")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка предобработки видео {video_path}: {e}")
            return None
