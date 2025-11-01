#!/usr/bin/env python3
"""
Модуль экспорта анимаций в видео для shorts_news
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
import yaml
from datetime import datetime
import base64

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from moviepy import (
    ColorClip, CompositeVideoClip, ImageClip, VideoFileClip, AudioFileClip,
    concatenate_audioclips
)
import cv2  # OpenCV все еще нужен для Selenium-версии

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import io
import subprocess

import tempfile
import shutil

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Импорт нашего модуля для логотипов
try:
    from logo_manager import LogoManager
except ImportError:
    LogoManager = None
    logger.warning("LogoManager не доступен")


class VideoExporter:
    """Класс для экспорта анимаций в видео (старый метод через Selenium)"""

    def __init__(self, video_config: Dict, paths_config: Dict):
        self.video_config = video_config
        self.paths_config = paths_config
        self.driver = None

        self._setup_selenium()

    def _setup_selenium(self):
        """Настройка Selenium WebDriver для headless режима"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(f"--window-size={self.video_config['width']},{self.video_config['height']}")
            chrome_options.add_argument("--hide-scrollbars")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            # Отключаем GCM, уведомления и фоновые процессы для чистых логов
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-features=TranslateUI,VizDisplayCompositor")
            chrome_options.add_argument("--disable-component-extensions-with-background-pages")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--gcm-registration-ticket=")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
            chrome_options.add_experimental_option('prefs', {
                'gcm.channel_status': False,
                'profile.default_content_setting_values.notifications': 2
            })
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Selenium WebDriver успешно инициализирован")

        except Exception as e:
            logger.error(f"Ошибка инициализации Selenium: {e}")
            raise

    def generate_html_from_template(self, animation_data: Dict, logo_path: Optional[str] = None) -> str:
        """Генерация HTML файла из шаблона с данными анимации"""

        template_path = os.path.join(
            self.paths_config['templates_dir'],
            'animation_template.html'
        )

        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()

        js_data = {
            'header': animation_data.get('animation_content', {}).get('header', {}),
            'body': animation_data.get('animation_content', {}).get('body', {}),
            'footer': animation_data.get('animation_content', {}).get('footer', {}),
            'style': animation_data.get('animation_content', {}).get('style', {}),
            'logo_url': logo_path or ''
        }

        js_data_json = json.dumps(js_data, ensure_ascii=False, indent=2)
        html_content = template.replace('{{ANIMATION_DATA}}', js_data_json)
        return html_content

    def render_animation_to_video(self, animation_data: Dict, output_path: str,
                               logo_path: Optional[str] = None) -> str:
        """Рендеринг анимации в видео файл"""
        try:
            html_content = self.generate_html_from_template(animation_data, logo_path)
            temp_html_path = os.path.join(
                self.paths_config['temp_dir'],
                f"temp_animation_{int(time.time())}.html"
            )

            with open(temp_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Преобразуем относительный путь в абсолютный для file URI
            absolute_path = os.path.abspath(temp_html_path)
            file_url = Path(absolute_path).as_uri()
            self.driver.get(file_url)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "container"))
            )

            video_path = self._record_animation_stream(output_path)

            os.remove(temp_html_path)

            logger.info(f"Видео успешно создано: {video_path}")
            return video_path
        except Exception as e:
            logger.error(f"Ошибка при рендеринге видео: {e}")
            raise

    def _capture_animation_frames(self) -> list:
        """Захват кадров анимации с синхронизацией через DevTools (fallback на старый метод)."""
        fps = self.video_config.get('fps', 20)  # Снижен с 24 до 20 для ускорения захвата
        duration = self.video_config.get('duration_seconds', 6)  # 6 секунд видео
        num_frames = int(duration * fps)
        logger.info(f"Захватываем {num_frames} кадров за {duration} секунд с FPS {fps} с синхронизацией видео.")

        try:
            video_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "newsCardVideo"))
            )

            container_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "container"))
            )

            metrics = self.driver.execute_script(
                """
                const container = arguments[0];
                if (!container) { return null; }
                const rect = container.getBoundingClientRect();
                return {
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    dpr: window.devicePixelRatio || 1
                };
                """,
                container_element
            )

            if not metrics or metrics.get('width', 0) == 0 or metrics.get('height', 0) == 0:
                raise ValueError("Не удалось определить область видео для скриншота")

            dpr = metrics['dpr']
            clip = {
                "x": metrics['x'] * dpr,
                "y": metrics['y'] * dpr,
                "width": metrics['width'] * dpr,
                "height": metrics['height'] * dpr,
                "scale": 1
            }

            self.driver.execute_script("arguments[0].pause();", video_element)
            # Включаем DevTools Page API (идемпотентно)
            try:
                self.driver.execute_cdp_cmd("Page.enable", {})
            except Exception:
                pass

            frames: List[np.ndarray] = []

            for i in range(num_frames):
                current_time = i / fps

                # Быстрая установка времени без явного ожидания seek
                self.driver.execute_script(
                    """
                    const video = arguments[0];
                    video.currentTime = arguments[1];
                    """,
                    video_element, current_time
                )

                # Небольшая пауза только для первого кадра, остальные без задержки
                if i == 0:
                    time.sleep(0.1)

                screenshot_data = self.driver.execute_cdp_cmd(
                    "Page.captureScreenshot",
                    {
                        "format": "jpeg",
                        "quality": 90,
                        "clip": clip
                    }
                )

                jpeg_bytes = base64.b64decode(screenshot_data['data'])
                frame_bgr = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
                if frame_bgr is None:
                    raise ValueError("cv2.imdecode вернул None")

                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                if (frame_rgb.shape[1], frame_rgb.shape[0]) != (self.video_config['width'], self.video_config['height']):
                    frame_rgb = cv2.resize(
                        frame_rgb,
                        (self.video_config['width'], self.video_config['height']),
                        interpolation=cv2.INTER_AREA
                    )

                frames.append(frame_rgb)

            logger.info(f"Захвачено {len(frames)} кадров с точной видеосинхронизацией (DevTools).")
            return frames

        except Exception as e:
            logger.warning(f"DevTools скриншоты недоступны, возвращаемся к headless-снимкам: {e}")
            return self._capture_frames_via_screenshot(num_frames, fps)

    def _capture_frames_via_screenshot(self, num_frames: int, fps: int) -> List[np.ndarray]:
        """Резервный метод захвата кадров c полным скриншотом окна."""
        frames: List[np.ndarray] = []

        for i in range(num_frames):
            current_time = i / fps
            self.driver.execute_script(
                """
                const video = document.getElementById('newsCardVideo');
                if (video) {
                    video.currentTime = arguments[0];
                }
                """,
                current_time
            )
            time.sleep(1 / max(fps * 2, 1))

            screenshot = self.driver.get_screenshot_as_png()
            image = Image.open(io.BytesIO(screenshot))
            if image.size != (self.video_config['width'], self.video_config['height']):
                image = image.resize((self.video_config['width'], self.video_config['height']))
            frames.append(np.array(image))

        logger.info(f"Захвачено {len(frames)} кадров с точной видеосинхронизацией (fallback).")
        return frames

    def _create_video_from_frames(self, frames: list, output_path: str) -> str:
        """Создание видео файла из кадров"""
        height, width, _ = cv2.cvtColor(np.array(frames[0]), cv2.COLOR_RGB2BGR).shape
        # Используем кодек avc1 (H.264), он более совместим, чем mp4v
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        video_writer = cv2.VideoWriter(output_path, fourcc, self.video_config['fps'], (width, height))

        for frame in frames:
            video_writer.write(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))

        video_writer.release()
        return output_path
    
    def _cleanup_temp_frames(self, video_path: str):
        pass

    def export_animation(self, animation_data: Dict, news_id: int,
                       logo_path: Optional[str] = None) -> Optional[str]:
        """Экспорт анимации в видео файл"""
        try:
            output_dir = self.paths_config['outputs_dir']
            output_filename = f"short_{news_id}_{int(time.time())}.mp4"
            output_path = os.path.join(output_dir, output_filename)

            video_path = self.render_animation_to_video(
                animation_data,
                output_path,
                logo_path
            )

            logger.info(f"Анимация успешно экспортирована: {video_path}")
            return video_path
        except Exception as e:
            logger.error(f"Ошибка экспорта анимации для новости {news_id}: {e}")
            return None

    def close(self):
        """Закрытие WebDriver"""
        if self.driver:
            self.driver.quit()
            logger.info("Selenium WebDriver закрыт")

    def __del__(self):
        """Деструктор для автоматического закрытия"""
        self.close()

    def create_news_short_video(self, video_package: Dict, output_path: str) -> Optional[str]:
        """Creates a news short video from a complete video package."""
        try:
            temp_html_path = self._create_news_short_html(video_package)
            if not temp_html_path:
                return None
            
            temp_html_uri = Path(os.path.abspath(temp_html_path)).as_uri()
            self.driver.get(temp_html_uri)
            time.sleep(3) # Wait for resources to load

            frames = self._capture_animation_frames()
            music_path = self._get_background_music()
            fps = self.video_config.get('fps', 30)

            self._export_frames_to_video_fallback(frames, output_path, fps, music_path)

            if os.path.exists(temp_html_path):
                os.remove(temp_html_path)

            logger.info(f"News short video created: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating news short: {e}", exc_info=True)
            return None

    def _create_news_short_html(self, video_package: Dict) -> Optional[str]:
        """Creates the HTML file for the news short, pre-processing video with ffmpeg if needed."""
        try:
            sandbox_enabled = self.video_config.get('sandbox_mode', {}).get('enabled', False)
            template_name = 'news_short_template_sandbox.html' if sandbox_enabled else 'news_short_template.html'
            logger.info(f"🔍 DEBUG Template selection: sandbox_enabled={sandbox_enabled}, template_name={template_name}")
            template_path = os.path.join(self.paths_config['templates_dir'], template_name)

            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            content = video_package.get('video_content', {})
            source_info = video_package.get('source_info', {})
            media = video_package.get('media', {})

            # --- CORRECTED: FFMPEG LOCAL VIDEO PROCESSING ---
            source_local_video_path = media.get('local_video_path')
            video_offset = media.get('video_offset')

            if source_local_video_path and video_offset is not None and Path(source_local_video_path).exists():
                logger.info(f"Trimming local video {source_local_video_path} with offset {video_offset}s.")
                try:
                    temp_dir = Path(self.paths_config.get('temp_dir', 'temp'))
                    temp_dir.mkdir(exist_ok=True)
                    trimmed_video_filename = f"trimmed_{Path(source_local_video_path).stem}_{int(time.time())}.mp4"
                    trimmed_video_path = temp_dir / trimmed_video_filename
                    
                    ffmpeg_path = 'ffmpeg' # Assuming ffmpeg is in PATH or venv

                    command = [
                        ffmpeg_path,
                        '-ss', str(video_offset),
                        '-i', str(source_local_video_path),
                        '-t', '59',
                        '-c', 'copy',
                        '-y',
                        str(trimmed_video_path)
                    ]
                    
                    logger.info(f"Executing ffmpeg command: {' '.join(command)}")
                    result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    logger.info("ffmpeg stdout: " + result.stdout)
                    logger.warning("ffmpeg stderr: " + result.stderr)

                    logger.info(f"Video successfully trimmed to {trimmed_video_path}")
                    # Update the media dictionary to use the new local, trimmed video
                    media['local_video_path'] = str(trimmed_video_path)

                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.error(f"Failed to trim video with ffmpeg: {e}")
                    if isinstance(e, subprocess.CalledProcessError):
                        logger.error(f"FFMPEG Error Output: {e.stderr}")
                    # If trimming fails, try to use the original video anyway
                    media['local_video_path'] = source_local_video_path
            # --- END OF CORRECTED LOGIC ---

            # Определяем тип источника
            source_name_lower = source_info.get('name', '').lower()
            avatar_path = source_info.get('avatar_path', '')
            
            # Определяем, какой тип отображения использовать
            is_twitter = 'twitter' in source_name_lower or 'x.com' in source_name_lower
            is_telegram = 'telegram' in source_name_lower
            
            # Для Twitter и Telegram - используем аватар пользователя/иконку
            if is_twitter or is_telegram:
                twitter_avatar_path = avatar_path if avatar_path else self._get_default_logo(source_info.get('name', 'News'))
                # Для Twitter показываем username, для Telegram - "Telegram Post"
                if is_twitter:
                    display_source_name = source_info.get('username', source_info.get('name', 'News'))
                    if '@' not in display_source_name and source_info.get('username'):
                        display_source_name = f"@{display_source_name}"
                else:
                    display_source_name = source_info.get('name', 'Telegram Post')
            else:
                # Для остальных источников - логотип источника
                # Используем TWITTER_AVATAR для совместимости с шаблоном
                # Если есть avatar_path, используем его, иначе ищем по имени источника
                if avatar_path:
                    twitter_avatar_path = avatar_path
                else:
                    twitter_avatar_path = self._get_source_logo_path(source_info.get('name', 'News'))
                display_source_name = source_info.get('name', 'News')

            def to_relative_path(path):
                if not path:
                    return ''
                
                if os.path.isabs(path) and ':' in path:
                    try:
                        temp_dir = Path("temp")
                        temp_dir.mkdir(exist_ok=True)
                        
                        import shutil
                        filename = Path(path).name
                        local_path = temp_dir / filename
                        shutil.copy2(path, local_path)
                        
                        logger.info(f"Copied temporary file: {path} -> {local_path}")
                        return f"../{local_path.as_posix()}"
                    except Exception as e:
                        logger.error(f"Error copying file {path}: {e}")
                        return ''
                
                return '../' + path.replace('\\', '/')
            
            news_image_path = ''
            news_video_path = ''
            
            if media.get('has_video') and media.get('local_video_path'):
                news_video_path = to_relative_path(media.get('local_video_path'))
                news_image_path = ''
            elif media.get('has_images') and media.get('local_image_path'):
                news_image_path = to_relative_path(media.get('local_image_path'))
                news_video_path = ''
            else:
                news_image_path = to_relative_path(media.get('local_image_path', media.get('image_path', '../resources/default_backgrounds/news_default.jpg')))
                news_video_path = to_relative_path(media.get('local_video_path', media.get('video_path', '')))
            
            replacements = {
                '{{NEWS_IMAGE}}': news_image_path,
                '{{NEWS_VIDEO}}': news_video_path,
                '{{SOURCE_LOGO}}': '',  # Не используется, оставлено для совместимости
                '{{TWITTER_AVATAR}}': to_relative_path(twitter_avatar_path),
                '{{SOURCE_NAME}}': display_source_name,
                '{{NEWS_TITLE}}': content.get('title', 'News Title'),
                '{{NEWS_BRIEF}}': content.get('summary', 'News summary not available.'),
                '{{PUBLISH_DATE}}': source_info.get('publish_date', 'Today'),
                '{{BACKGROUND_MUSIC}}': self._get_background_music()
            }
            
            logger.info(f"🔍 DEBUG Template replacements:")
            logger.info(f"  NEWS_IMAGE: {replacements['{{NEWS_IMAGE}}']}")
            logger.info(f"  NEWS_VIDEO: {replacements['{{NEWS_VIDEO}}']}")
            logger.info(f"  TWITTER_AVATAR: {replacements['{{TWITTER_AVATAR}}']}")
            logger.info(f"  Media data: {media}")
            
            html_content = template_content
            for placeholder, value in replacements.items():
                html_content = html_content.replace(placeholder, str(value or ''))
            
            temp_html_path = os.path.join(self.paths_config.get('temp_dir', 'temp'), f"news_short_{int(time.time())}.html")
            with open(temp_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return temp_html_path
            
        except Exception as e:
            logger.error(f"Error creating HTML for short: {e}", exc_info=True)
            return None

    def _extract_source_name(self, url: str) -> str:
        """Извлекает имя источника из URL"""
        if 'cnn.com' in url.lower():
            return 'CNN'
        elif 'foxnews.com' in url.lower():
            return 'FoxNews'
        elif 'nytimes.com' in url.lower():
            return 'NYTimes'
        elif 'washingtonpost.com' in url.lower():
            return 'WashingtonPost'
        elif 'reuters.com' in url.lower():
            return 'Reuters'
        elif 'ap.org' in url.lower() or 'apnews.com' in url.lower():
            return 'AssociatedPress'
        elif 'wsj.com' in url.lower():
            return 'WSJ'
        elif 'cnbc.com' in url.lower():
            return 'CNBC'
        elif 'aljazeera.com' in url.lower():
            return 'ALJAZEERA'
        elif 'abc' in url.lower():
            return 'ABC'
        elif 'nbcnews.com' in url.lower():
            return 'NBCNEWS'
        else:
            return 'News'

    def _get_source_logo_path(self, source_name: str) -> str:
        """
        Получает путь к логотипу источника по имени
        """
        if not source_name:
            return ''
        
        # Маппинг известных источников на их логотипы (только существующие файлы)
        logo_mapping = {
            'nbc news': 'resources/logos/NBCNews.png',
            'nbcnews': 'resources/logos/NBCNews.png',
            'abc news': 'resources/logos/abc.png',
            'abcnews': 'resources/logos/abc.png',
            'reuters': 'resources/logos/Reuters.png',
            'cnn': 'resources/logos/cnn.png',
            'fox news': 'resources/logos/FoxNews.png',
            'foxnews': 'resources/logos/FoxNews.png',
            'washington post': 'resources/logos/WashingtonPost.png',
            'washingtonpost': 'resources/logos/WashingtonPost.png',
            'wall street journal': 'resources/logos/WSJ.png',
            'wsj': 'resources/logos/WSJ.png',
            'cnbc': 'resources/logos/CNBC.png',
            'al jazeera': 'resources/logos/ALJAZEERA.png',
            'aljazeera': 'resources/logos/ALJAZEERA.png',
            'associated press': 'resources/logos/AssociatedPress.png',
            'ap': 'resources/logos/AssociatedPress.png',
            'financial times': 'resources/logos/Financial_Times_corporate_logo_(no_background).svg',
            'ft': 'resources/logos/Financial_Times_corporate_logo_(no_background).svg',
            'the hill': 'resources/logos/thehill.png',
            'thehill': 'resources/logos/thehill.png',
            'politico': 'resources/logos/politico.png',
        }
        
        source_lower = source_name.lower().strip()
        
        # Проверяем точное совпадение
        if source_lower in logo_mapping:
            logo_path = logo_mapping[source_lower]
            if Path(logo_path).exists():
                logger.info(f"✅ Найден логотип для {source_name}: {logo_path}")
                return logo_path
        
        # Проверяем частичное совпадение
        for key, logo_path in logo_mapping.items():
            if key in source_lower or source_lower in key:
                if Path(logo_path).exists():
                    logger.info(f"✅ Найден логотип для {source_name} (частичное совпадение): {logo_path}")
                    return logo_path
        
        # Пробуем найти файл по шаблону
        potential_paths = [
            f"resources/logos/{source_name}.png",
            f"resources/logos/{source_name.replace(' ', '')}.png",
            f"resources/logos/{source_name.upper()}.png",
            f"resources/logos/{source_name.lower().replace(' ', '')}.png",
        ]
        
        for path in potential_paths:
            if Path(path).exists():
                logger.info(f"✅ Найден логотип для {source_name}: {path}")
                return path
        
        logger.warning(f"⚠️ Логотип для источника '{source_name}' не найден, используем дефолтный")
        return ''
    
    def _get_default_logo(self, source_name: str) -> str:
        """
        Возвращает дефолтный логотип для источника
        """
        # Для Twitter/X
        if 'twitter' in source_name.lower() or 'x.com' in source_name.lower():
            return 'resources/logos/X.png'
        
        # Дефолтный логотип
        return ''
    
    def _get_twitter_avatar_path(self, news_data: Dict[str, Any]) -> str:
        """
        Получает путь к аватару Twitter. Предполагается, что аватар уже скачан
        на предыдущем этапе в media_manager.
        """
        try:
            # Путь к аватару должен быть уже в news_data после работы media_manager
            avatar_path = news_data.get('avatar_path')
            if avatar_path and Path(avatar_path).exists():
                logger.info(f"✅ Используем аватар из news_data: {avatar_path}")
                # Путь должен быть относительным для HTML
                return f"../{avatar_path}"
            
            # Fallback на случай, если в news_data нет пути, но файл есть по стандартному имени
            username = news_data.get('username', '').lstrip('@')
            if username:
                logos_avatar = f"resources/logos/avatar_{username}.png"
                if os.path.exists(logos_avatar):
                    logger.info(f"✅ Найден аватар по стандартному пути: {logos_avatar}")
                    return f"../{logos_avatar}"

            logger.warning(f"⚠️ Аватар для @{username} не найден в данных новости или по стандартному пути.")
            return ''
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения пути к аватару Twitter: {e}")
            return ''
    
    def _get_news_image(self, news_data: Dict) -> str:
        """Получает изображение новости"""
        # Проверяем, есть ли локальный путь к изображению
        if 'local_image_path' in news_data and news_data['local_image_path']:
            local_path = news_data['local_image_path']
            if os.path.exists(local_path):
                return f"../{local_path}"
        
        # Проверяем старый формат
        if 'image_path' in news_data and os.path.exists(news_data['image_path']):
            return f"../{news_data['image_path']}"
        
        # Если есть URL изображения, попробуем использовать медиа-менеджер
        if 'images' in news_data and news_data['images']:
            try:
                from scripts.media_manager import MediaManager
                # Создаем конфигурацию для MediaManager из имеющихся данных
                config_path = 'config/config.yaml'
                media_manager = MediaManager(config_path)
                media_result = media_manager.process_news_media(news_data)
                
                if media_result.get('local_image_path'):
                    return f"../{media_result['local_image_path']}"
            except Exception as e:
                logger.warning(f"Не удалось обработать изображение через MediaManager: {e}")
        
        # Возвращаем дефолтное изображение
        return "../resources/default_backgrounds/news_default.jpg"

    def _get_news_video(self, news_data: Dict) -> str:
        """Получает видео новости"""
        # Проверяем, есть ли локальный путь к видео
        if 'local_video_path' in news_data and news_data['local_video_path']:
            local_path = news_data['local_video_path']
            if os.path.exists(local_path):
                return f"../{local_path}"
        
        # Проверяем, есть ли URL видео в данных
        if 'video_url' in news_data and news_data['video_url']:
            # В будущем здесь можно добавить загрузку видео
            # Пока возвращаем пустую строку
            pass
        
        # Если видео нет, возвращаем пустую строку
        return ""

    def _get_background_music(self) -> str:
        """Получает путь к фоновой музыке"""
        try:
            from scripts.media_manager import MediaManager
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yaml')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            media_manager = MediaManager(config)
            music_path = media_manager.get_background_music()
            
            if music_path:
                return f"../{music_path}"
            else:
                return ""
                
        except Exception as e:
            logger.warning(f"Ошибка получения фоновой музыки через MediaManager: {e}")
            
            # Fallback к старому методу
            music_dir = "resources/music"
            
            if not os.path.exists(music_dir):
                logger.info(f"Папка с музыкой не найдена: {music_dir}")
                return ""
                
            audio_extensions = ['.mp3', '.wav', '.ogg', '.m4a']
            
            # Собираем все аудиофайлы
            music_files = []
            for file in os.listdir(music_dir):
                if any(file.lower().endswith(ext) for ext in audio_extensions):
                    music_files.append(file)
            
            if music_files:
                # Выбираем случайный файл
                import random
                selected_file = random.choice(music_files)
                music_path = os.path.join(music_dir, selected_file)
                logger.info(f"Найдена фоновая музыка: {selected_file}")
                return f"../{music_path}"
                    
            logger.info("Фоновая музыка не найдена в папке resources/music")
            return ""

    def _export_frames_to_video_fallback(self, frames: List[np.ndarray], output_path: str, fps: int, music_path: Optional[str] = None):
        """Резервный метод экспорта кадров в видео с помощью OpenCV и FFMPEG для аудио"""
        if not frames:
            logger.error("Нет кадров для экспорта в видео.")
            return

        height, width, layers = frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        # Если есть музыка, сначала создаем видео без звука
        silent_video_path = output_path
        if music_path and os.path.exists(music_path.replace('../', '')):
            silent_video_path = os.path.join(os.path.dirname(output_path), f"silent_{os.path.basename(output_path)}")

        video = cv2.VideoWriter(silent_video_path, fourcc, fps, (width, height))
        for frame in frames:
            video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        video.release()

        logger.info(f"Видео без звука создано: {silent_video_path}")

        # Добавляем аудио дорожку с помощью FFMPEG
        actual_music_path = music_path.replace('../', '')
        if music_path and os.path.exists(actual_music_path):
            logger.info(f"🎵 Добавляем аудиодорожку '{actual_music_path}' с помощью FFMPEG...")
            command = [
                'ffmpeg',
                '-y',  # Перезаписывать выходной файл без запроса
                '-i', silent_video_path,
                '-i', actual_music_path,
                '-c:v', 'copy',  # Копировать видеопоток без перекодирования
                '-c:a', 'aac',   # Кодировать аудио в AAC
                '-shortest',     # Длительность видео будет равна самому короткому потоку
                '-loglevel', 'error', # Скрыть лишние логи
                output_path
            ]
            
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                logger.info(f"✅ Аудиодорожка успешно добавлена в '{output_path}'")
                # Удаляем временное видео без звука
                os.remove(silent_video_path)
            except FileNotFoundError:
                logger.error("❌ FFMPEG не найден. Убедитесь, что он установлен и доступен в PATH.")
                # Если FFMPEG нет, оставляем видео без звука
                if silent_video_path != output_path:
                    os.rename(silent_video_path, output_path)
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Ошибка FFMPEG при добавлении аудио: {e.stderr}")
                # Если FFMPEG выдал ошибку, оставляем видео без звука
                if silent_video_path != output_path:
                    os.rename(silent_video_path, output_path)
        else:
            if not music_path:
                logger.info("🎶 Музыка не выбрана, видео будет без звука.")
            else:
                logger.warning(f"⚠️ Файл музыки не найден: '{actual_music_path}', видео будет без звука.")
        
    def create_short_from_html(self, news_data: Dict) -> Optional[str]:
        """Создает видео-шорт из HTML-шаблона, полагаясь на пред-обработанное видео."""
        try:
            temp_html_path = self._create_news_short_html(news_data)
            if not temp_html_path:
                logger.error("Не удалось создать временный HTML-файл.")
                return None

            self.driver.get(f"file:///{os.path.abspath(temp_html_path)}")
            
            # Даем странице время на полную загрузку всех ресурсов (шрифты, изображения)
            time.sleep(3) 

            frames = []
            duration_seconds = self.video_config.get('duration_seconds', 59)
            fps = self.video_config.get('fps', 30)
            num_frames = int(duration_seconds * fps)
            
            logger.info(f"Захватываем {num_frames} кадров за {duration_seconds} секунд с FPS {fps}")

            for i in range(num_frames):
                screenshot = self.driver.get_screenshot_as_png()
                img = Image.open(io.BytesIO(screenshot))
                frames.append(np.array(img))
                
                # Задержка между кадрами не нужна, т.к. анимации теперь внутри видео

            logger.info(f"Захвачено {len(frames)} кадров.")
            
            output_filename = f"short_{news_data.get('id', 'temp')}_{int(time.time())}.mp4"
            output_path = os.path.join(self.paths_config.get('outputs_dir', 'outputs'), output_filename)

            music_path = self._get_background_music()

            self._export_frames_to_video_fallback(frames, output_path, fps, music_path)

            os.remove(temp_html_path)
            logger.info(f"News short видео создано: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Ошибка при создании видео из HTML: {e}", exc_info=True)
            return None


def main():
    """Тестовая функция"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

    try:
        # Загрузка конфигурации
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Тестовые данные
        test_animation_data = {
            'animation_content': {
                'header': {
                    'text': 'BBC News',
                    'animation': 'fadeIn',
                    'duration': 1.5
                },
                'body': {
                    'text': 'Президент объявил о новых реформах в экономике страны',
                    'animation': 'typewriter',
                    'duration': 2.5
                },
                'footer': {
                    'date': '30.08.2025',
                    'animation': 'slideUp',
                    'duration': 1.0
                },
                'style': {
                    'theme': 'dark',
                    'accent_color': '#FF6B35'
                }
            }
        }

        # Попытка использовать основной экспортер
        try:
            exporter = VideoExporter(config['video'], config['paths'])
            output_path = os.path.join(
                os.path.dirname(__file__), '..', 'outputs', 'test_video.mp4'
            )
            # Для теста нужно передать news_data
            test_news_data = {
                'summary': 'Это тестовый текст новости для проверки генерации видео. Он должен быть достаточно длинным, чтобы переноситься на несколько строк.',
                'local_image_path': 'resources/media/news/Test_Trump_Tariffs_N_086fd1c7.jpg',
                'url': 'https://www.bcs.com/test-news',
                'publish_date': '13.09.2025'
            }
            result = exporter.create_news_short_video(test_news_data, output_path)
            print(f"Видео создано: {result}")

        except Exception as e:
            print(f"Основной экспортер не доступен: {e}")
            print("Используем резервный экспортер...")
            # Тут можно будет протестировать SeleniumVideoExporter если нужно
            # fallback_exporter = SeleniumVideoExporter(config['video'], config['paths'])
            # ...

    except Exception as e:
        logger.error(f"Ошибка в тестовой функции: {e}", exc_info=True)


if __name__ == "__main__":
    main()
