#!/usr/bin/env python3
"""
ABC News Engine
Парсинг новостей с abcnews.go.com
"""

import logging
import re
from typing import Dict, List, Any
from urllib.parse import urlparse, urljoin, parse_qs
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from ..base.source_engine import SourceEngine

logger = logging.getLogger(__name__)

class ABCNewsEngine(SourceEngine):
    """Движок для парсинга ABC News"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
    
    def _get_supported_domains(self) -> List[str]:
        """Возвращает поддерживаемые домены"""
        return [
            "abcnews.go.com",
            "www.abcnews.go.com"
        ]
    
    def _get_source_name(self) -> str:
        """Возвращает название источника"""
        return "ABC News"
    
    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        # Проверяем домен
        if not any(domain in url.lower() for domain in self.supported_domains):
            return False
        
        # Проверяем наличие entryId - если есть, это ссылка на конкретную запись
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        has_entry_id = 'entryId' in query_params or 'entryid' in query_params
        
        # Если есть entryId, обрабатываем даже live-updates
        if has_entry_id:
            logger.info(f"✅ ABC News: URL содержит entryId, обрабатываем как отдельную запись")
            return True
        
        # Фильтруем типы URL без entryId, которые не подходят для обработки
        excluded_patterns = [
            '/live-updates/',  # Live updates без entryId - динамически обновляемые страницы
        ]
        
        for pattern in excluded_patterns:
            if pattern in url.lower():
                logger.info(f"⏭️ ABC News: URL содержит исключенный паттерн '{pattern}' без entryId, пропускаем")
                return False
        
        return True
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Возвращает информацию о движке"""
        return {
            'name': self.source_name,
            'supported_domains': self.supported_domains,
            'version': '1.0.0'
        }
    
    def parse_url(self, url: str, driver=None) -> Dict[str, Any]:
        """
        Парсинг URL ABC News
        
        Args:
            url: URL для парсинга
            driver: Selenium WebDriver (опционально)
            
        Returns:
            Словарь с данными новости или None
        """
        try:
            logger.info(f"🔍 Парсинг ABC News URL: {url}")
            
            # Валидация URL
            if not self._is_valid_url(url):
                logger.warning(f"❌ Неподдерживаемый URL: {url}")
                return None
            
            # Парсинг через Selenium для динамического контента
            if driver:
                return self._parse_with_selenium(url, driver)
            else:
                # Создаем драйвер для парсинга
                return self._parse_with_selenium(url, None)
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга ABC News URL {url}: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None
    
    def _parse_with_selenium(self, url: str, driver=None) -> Dict[str, Any]:
        """Парсинг через Selenium"""
        driver_created = False
        try:
            # Если драйвер не передан, создаем его
            if driver is None:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                
                chrome_options = Options()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                driver = webdriver.Chrome(options=chrome_options)
                driver_created = True
            
            logger.info(f"🔍 Selenium парсинг для получения контента...")
            
            # Проверяем, это live-updates?
            is_live_update = '/live-updates/' in url.lower()
            
            # Загружаем страницу
            driver.get(url)
            
            # Ждем загрузки основного контента
            import time
            time.sleep(5 if is_live_update else 3)  # Больше времени для live-updates
            
            # Извлекаем данные
            title = self._extract_title(driver)
            content = self._extract_content(driver)
            description = self._extract_description(driver, content)
            author = self._extract_author(driver)
            publish_date = self._extract_publish_date(driver)
            images = self._extract_images(driver, url)
            videos = self._extract_videos(driver)
            
            # Валидация контента
            if not self._validate_parsed_content({'title': title, 'content': content}):
                logger.warning("❌ Контент не прошел валидацию")
                return None
            
            result = {
                'title': title,
                'description': description,
                'content': content,
                'author': author,
                'published': publish_date,
                'source': self.source_name,
                'url': url,
                'images': images,
                'videos': videos,
                'content_type': 'article'
            }
            
            logger.info(f"📝 ABC News парсинг: заголовок='{title[:50]}...', контент={len(content)} символов, изображения={len(images)}, видео={len(videos)}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка Selenium парсинга: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None
        finally:
            # Закрываем драйвер, если создали его сами
            if driver_created and driver:
                try:
                    driver.quit()
                except Exception:
                    pass
    
    def _extract_title(self, driver) -> str:
        """Извлечение заголовка"""
        try:
            # Пробуем разные селекторы для заголовка
            title_selectors = [
                'h1[data-testid="headline"]',
                'h1.Article__Headline',
                'h1.headline',
                'h1[class*="headline"]',
                'h1[class*="title"]',
                'h1[class*="Headline"]',
                # Селекторы для live-updates
                '.LiveBlogPost__Headline h1',
                '.LiveBlogPost__Headline h2',
                '.LiveBlogPost h1',
                '.LiveBlogPost h2',
                '[class*="LiveBlog"] h1',
                '[class*="LiveBlog"] h2',
                'h1',
                'h2',
                '.article-header h1',
                '[data-testid="article-headline"] h1',
                'header h1',
                'article h1'
            ]
            
            for selector in title_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    title = element.text.strip()
                    if title and len(title) > 10:  # Минимальная длина заголовка
                        logger.info(f"✅ Заголовок найден через '{selector}': {title[:50]}...")
                        return title
                except NoSuchElementException:
                    continue
            
            # Пробуем извлечь из meta тегов
            try:
                meta_title = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:title"]')
                title = meta_title.get_attribute('content').strip()
                if title and len(title) > 10:
                    logger.info(f"✅ Заголовок найден из og:title: {title[:50]}...")
                    return title
            except NoSuchElementException:
                pass
            
            logger.warning("⚠️ Заголовок не найден")
            return "ABC News Article"
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения заголовка: {e}")
            return "ABC News Article"
    
    def _extract_description(self, driver, content: str) -> str:
        """Извлечение описания"""
        try:
            # Пробуем разные селекторы для описания/резюме
            desc_selectors = [
                'meta[property="og:description"]',
                'meta[name="description"]',
                'p.Article__Description',
                'p.summary',
                '.article-description',
                '[data-testid="article-description"]'
            ]
            
            for selector in desc_selectors:
                try:
                    if selector.startswith('meta'):
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        description = element.get_attribute('content').strip()
                    else:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        description = element.text.strip()
                    
                    if description and len(description) > 20:
                        logger.info(f"✅ Описание найдено: {description[:50]}...")
                        return description
                except NoSuchElementException:
                    continue
            
            # Если описание не найдено, берем первые 500 символов контента
            if content and len(content) > 50:
                description = content[:500] + '...' if len(content) > 500 else content
                logger.info(f"✅ Описание создано из контента: {description[:50]}...")
                return description
            
            logger.warning("⚠️ Описание не найдено")
            return ""
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения описания: {e}")
            return ""
    
    def _extract_content(self, driver) -> str:
        """Извлечение основного контента"""
        try:
            content_parts = []
            
            # Селекторы для основного контента
            content_selectors = [
                '.Article__Content p',
                '.article-body p',
                '.article-content p',
                '[data-testid="article-body"] p',
                '.Article__Body p',
                'article .Article__Content p',
                # Селекторы для live-updates
                '.LiveBlogPost__Content p',
                '.LiveBlogPost__Body p',
                '[class*="LiveBlogPost"] p',
                '[class*="LiveBlog"] p',
                # Более широкие селекторы для разных типов статей
                'main article p',
                'main p',
                '[role="main"] p',
                'div[class*="Article"] p',
                'div[class*="Story"] p',
                'section[class*="body"] p',
                'article p',
                '.story-body p',
                # Самый общий селектор (последний)
                'body p'
            ]
            
            for selector in content_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"✅ Найдено {len(elements)} параграфов через селектор '{selector}'")
                        for element in elements:
                            text = element.text.strip()
                            if text and len(text) > 20:  # Минимальная длина абзаца
                                # Фильтруем служебные тексты
                                if not self._is_service_text(text):
                                    content_parts.append(text)
                        break  # Если нашли контент, выходим
                except NoSuchElementException:
                    continue
            
            # Если не нашли через селекторы, пробуем найти все параграфы в статье
            if not content_parts:
                try:
                    article = driver.find_element(By.TAG_NAME, "article")
                    paragraphs = article.find_elements(By.TAG_NAME, "p")
                    logger.info(f"✅ Найдено {len(paragraphs)} параграфов в article")
                    for p in paragraphs:
                        text = p.text.strip()
                        if text and len(text) > 20:
                            if not self._is_service_text(text):
                                content_parts.append(text)
                except NoSuchElementException:
                    pass
            
            content = ' '.join(content_parts)
            
            if content:
                logger.info(f"✅ Контент извлечен: {len(content)} символов из {len(content_parts)} параграфов")
                return content
            else:
                logger.warning("⚠️ Контент не найден")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения контента: {e}")
            return ""
    
    def _is_service_text(self, text: str) -> bool:
        """Проверка, является ли текст служебным"""
        service_keywords = [
            'subscribe',
            'newsletter',
            'advertisement',
            'click here',
            'read more',
            'related:',
            'follow us',
            'sign up',
            'trending',
            'sponsored',
            'editor\'s note',
            'popular reads',
            'sponsored content',
            'by taboola',
            'watch live',
            'stream on',
            'shop',
            'interest successfully added',
            'turn on desktop notifications',
            'we\'ll notify you',
            'related topics',
            'abc news network',
            'privacy policy',
            'terms of use',
            'contact us',
            '© 20',  # Copyright
            'all rights reserved'
        ]
        
        text_lower = text.lower()
        
        # Проверяем ключевые слова
        if any(keyword in text_lower for keyword in service_keywords):
            return True
        
        # Слишком короткие тексты (меньше 30 символов) - вероятно меню/ссылки
        if len(text) < 30:
            return True
        
        # Тексты, состоящие только из цифр и символов
        if text.replace(' ', '').replace(',', '').replace('.', '').replace(':', '').isdigit():
            return True
            
        return False
    
    def _extract_author(self, driver) -> str:
        """Извлечение автора"""
        try:
            author_selectors = [
                '[data-testid="byline"]',
                '.byline',
                '.article-byline',
                '.author',
                '[class*="byline"]',
                '[class*="author"]',
                '.Article__Author',
                'meta[name="author"]'
            ]
            
            for selector in author_selectors:
                try:
                    if selector.startswith('meta'):
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        author = element.get_attribute('content').strip()
                    else:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        author = element.text.strip()
                    
                    if author and len(author) > 2:
                        # Очищаем от лишнего ("By ", "ABC News" и т.д.)
                        author = re.sub(r'^By\s+', '', author, flags=re.IGNORECASE)
                        logger.info(f"✅ Автор найден: {author}")
                        return author
                except NoSuchElementException:
                    continue
            
            return "ABC News"
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения автора: {e}")
            return "ABC News"
    
    def _extract_publish_date(self, driver) -> str:
        """Извлечение даты публикации"""
        try:
            date_selectors = [
                '[data-testid="timestamp"]',
                '.timestamp',
                '.article-timestamp',
                'time[datetime]',
                '[class*="timestamp"]',
                '[class*="date"]',
                '.Article__Date',
                'meta[property="article:published_time"]'
            ]
            
            for selector in date_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if selector.startswith('meta'):
                        date_text = element.get_attribute('content').strip()
                    elif selector == 'time[datetime]':
                        date_text = element.get_attribute('datetime').strip()
                    else:
                        date_text = element.text.strip()
                    
                    if date_text:
                        logger.info(f"✅ Дата найдена: {date_text}")
                        return date_text
                except NoSuchElementException:
                    continue
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения даты: {e}")
            return ""
    
    def _extract_images(self, driver, url: str) -> List[str]:
        """Извлечение изображений"""
        try:
            images = []
            
            # Сначала пробуем получить главное изображение из meta тегов
            meta_img_selectors = [
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
                'meta[property="twitter:image"]'
            ]
            
            for selector in meta_img_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    img_url = element.get_attribute('content')
                    if img_url and self._is_valid_image_url(img_url):
                        full_url = urljoin(url, img_url)
                        if full_url not in images:
                            images.append(full_url)
                            logger.debug(f"📸 Добавлено изображение из meta: {full_url}")
                except NoSuchElementException:
                    continue
            
            # Селекторы для изображений в контенте
            img_selectors = [
                '.Article__Content img',
                '.article-body img',
                '.article-content img',
                '[data-testid="article-body"] img',
                'article img',
                '.Article__Hero img',
                'figure img',
                '.image-container img',
                '.media img',
                'picture img'
            ]
            
            for selector in img_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for img in elements:
                        # Пробуем разные атрибуты
                        src = img.get_attribute('src')
                        data_src = img.get_attribute('data-src')
                        data_lazy = img.get_attribute('data-lazy')
                        
                        # Проверяем все возможные источники
                        for img_url in [src, data_src, data_lazy]:
                            if img_url and self._is_valid_image_url(img_url):
                                # Делаем URL полным
                                full_url = urljoin(url, img_url)
                                if full_url not in images:
                                    images.append(full_url)
                                    logger.debug(f"📸 Добавлено изображение: {full_url}")
                except NoSuchElementException:
                    continue
            
            logger.info(f"📸 Найдено {len(images)} изображений")
            return images
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения изображений: {e}")
            return []
    
    def _extract_videos(self, driver) -> List[str]:
        """Извлечение видео"""
        try:
            videos = []
            
            # Селекторы для видео
            video_selectors = [
                '.Article__Content video',
                '.article-body video',
                '.article-content video',
                '[data-testid="article-body"] video',
                'article video',
                'iframe[src*="youtube"]',
                'iframe[src*="vimeo"]',
                'iframe[src*="abcnews"]',
                'video source',
                '.video-container video',
                '.media video',
                '.Article__Video video'
            ]
            
            for selector in video_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for video in elements:
                        # Пробуем разные атрибуты
                        src = video.get_attribute('src')
                        data_src = video.get_attribute('data-src')
                        
                        # Для source элементов
                        if video.tag_name == 'source':
                            src = video.get_attribute('src')
                        
                        # Проверяем все возможные источники
                        for video_url in [src, data_src]:
                            if video_url and self._is_valid_video_url(video_url):
                                # Проверяем, что URL полный
                                if video_url.startswith('http'):
                                    if video_url not in videos:
                                        videos.append(video_url)
                                        logger.debug(f"🎬 Добавлено видео: {video_url}")
                                else:
                                    # Пробуем сделать URL полным
                                    full_url = urljoin(driver.current_url, video_url)
                                    if self._is_valid_video_url(full_url):
                                        if full_url not in videos:
                                            videos.append(full_url)
                                            logger.debug(f"🎬 Добавлено видео (полный URL): {full_url}")
                except NoSuchElementException:
                    continue
            
            logger.info(f"🎬 Найдено {len(videos)} видео")
            return videos
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения видео: {e}")
            return []
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Проверка валидности URL изображения"""
        if not url:
            return False
        
        # Исключаем blob и data URLs
        if url.startswith('blob:') or url.startswith('data:'):
            return False
        
        # Исключаем слишком маленькие изображения
        if any(x in url.lower() for x in ['1x1', 'spacer', 'pixel', 'blank']):
            return False
        
        # Проверяем, что это изображение по расширению
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if any(url.lower().endswith(ext) for ext in image_extensions):
            return True
        
        # Проверяем домены ABC News
        abc_domains = ['abcnews.go.com', 's.abcnews.com', 'img.abcnews.com', 'cdn.abcnews.com']
        parsed_url = urlparse(url)
        if any(domain in parsed_url.netloc for domain in abc_domains):
            return True
        
        # Проверяем, что URL содержит параметры изображения
        if 'image' in url.lower() or 'photo' in url.lower() or 'img' in url.lower():
            return True
        
        return False
    
    def _is_valid_video_url(self, url: str) -> bool:
        """Проверка валидности URL видео"""
        if not url:
            return False
        
        # Исключаем blob и data URLs
        if url.startswith('blob:') or url.startswith('data:'):
            return False
        
        # Проверяем видео расширения
        video_extensions = ['.mp4', '.webm', '.ogg', '.mov', '.m3u8', '.ts']
        if any(url.lower().endswith(ext) for ext in video_extensions):
            return True
        
        # Проверяем видео платформы
        video_platforms = ['youtube.com', 'youtu.be', 'vimeo.com', 'abcnews.go.com']
        parsed_url = urlparse(url)
        if any(platform in parsed_url.netloc for platform in video_platforms):
            return True
        
        # Проверяем, что URL содержит параметры видео
        if 'video' in url.lower() or 'stream' in url.lower():
            return True
        
        return False
    
    def _validate_parsed_content(self, content: Dict[str, Any]) -> bool:
        """Валидация парсенного контента"""
        title = content.get('title', '')
        text_content = content.get('content', '')
        
        # Проверяем заголовок
        if not title or len(title) < 10 or title == "ABC News Article":
            logger.warning("❌ Слишком короткий или дефолтный заголовок")
            return False
        
        # Проверяем контент
        if not text_content or len(text_content) < 50:
            logger.warning("❌ Слишком короткий контент")
            return False
        
        logger.info(f"✅ ABC News контент валиден: title={bool(title)}, content={len(text_content)} символов")
        return True
    
    def extract_media(self, url: str, content: Dict[str, Any]) -> Dict[str, List[str]]:
        """Извлекает медиа файлы из контента"""
        return {
            'images': content.get('images', []),
            'videos': content.get('videos', [])
        }
    
    def validate_content(self, content: Dict[str, Any]) -> bool:
        """Валидирует качество контента"""
        # Базовая валидация
        if not self._validate_parsed_content(content):
            return False
        
        # Проверяем наличие медиа
        images = content.get('images', [])
        videos = content.get('videos', [])
        
        if not images and not videos:
            logger.warning("⚠️ ABC News: контент не имеет медиа, но это допустимо")
            # Для ABC News медиа опциональны, не бракуем контент
        
        return True
    
    def _is_valid_url(self, url: str) -> bool:
        """Проверка валидности URL"""
        if not url:
            return False
        
        parsed = urlparse(url)
        
        if not parsed.netloc:
            return False
        
        # Проверяем, что домен поддерживается
        if not any(domain in parsed.netloc for domain in self.supported_domains):
            return False
        
        # Проверяем наличие entryId - если есть, это валидный URL даже для live-updates
        query_params = parse_qs(parsed.query)
        has_entry_id = 'entryId' in query_params or 'entryid' in query_params
        
        if has_entry_id:
            return True
        
        # Проверяем, что URL не содержит исключенные паттерны (только если нет entryId)
        excluded_patterns = [
            '/live-updates/',
        ]
        
        for pattern in excluded_patterns:
            if pattern in url.lower():
                return False
        
        return True

