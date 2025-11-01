"""
The Hill news source engine
"""

from typing import Dict, Any, List
import logging
from urllib.parse import urljoin, urlparse
import re
from ..base import SourceEngine, MediaExtractor, ContentValidator

logger = logging.getLogger(__name__)


class TheHillMediaExtractor(MediaExtractor):
    """Извлекатель медиа для The Hill"""
    
    def extract_images(self, url: str, content: Dict[str, Any]) -> List[str]:
        """Извлекает изображения из контента The Hill"""
        images = []
        
        if 'images' in content:
            for img_url in content['images']:
                if self.validate_image_url(img_url):
                    images.append(img_url)
        
        return images
    
    def extract_videos(self, url: str, content: Dict[str, Any]) -> List[str]:
        """Извлекает видео из контента The Hill"""
        videos = []
        
        if 'videos' in content:
            for vid_url in content['videos']:
                if self.validate_video_url(vid_url):
                    videos.append(vid_url)
        
        return videos
    
    def get_fallback_images(self, title: str) -> List[str]:
        """Возвращает fallback изображения для The Hill"""
        title_lower = title.lower()
        
        # Политические темы - Капитолий
        if any(word in title_lower for word in ['congress', 'senate', 'house', 'capitol', 'representative', 'senator']):
            return ['https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=1280&h=720&fit=crop']
        
        # Президентские темы
        elif any(word in title_lower for word in ['president', 'biden', 'trump', 'white house']):
            return ['https://images.unsplash.com/photo-1551524164-6cf2ac5313f4?w=1280&h=720&fit=crop']
        
        # Выборы
        elif any(word in title_lower for word in ['election', 'campaign', 'vote', 'ballot']):
            return ['https://images.unsplash.com/photo-1541872703-74c3ee0f25b1?w=1280&h=720&fit=crop']
        
        # Общая тематика - Вашингтон
        else:
            return ['https://images.unsplash.com/photo-1555596000-aa02ca55b2e8?w=1280&h=720&fit=crop']


class TheHillContentValidator(ContentValidator):
    """Валидатор контента для The Hill"""
    
    def validate_quality(self, content: Dict[str, Any]) -> bool:
        """Валидирует качество контента The Hill"""
        errors = self.get_validation_errors(content)
        
        if errors:
            logger.warning(f"Контент The Hill не прошел валидацию: {', '.join(errors)}")
            return False
        
        return True


class TheHillEngine(SourceEngine):
    """
    Движок для обработки новостей The Hill
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Инициализация движка The Hill"""
        super().__init__(config)
        self.media_extractor = TheHillMediaExtractor(config)
        self.content_validator = TheHillContentValidator(config)
    
    def _get_source_name(self) -> str:
        """Возвращает название источника"""
        return "The Hill"
    
    def _get_supported_domains(self) -> List[str]:
        """Возвращает поддерживаемые домены"""
        return ['thehill.com', 'www.thehill.com']
    
    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        return any(domain in url.lower() for domain in self.supported_domains)
    
    def parse_url(self, url: str, driver=None) -> Dict[str, Any]:
        """
        Парсит URL The Hill используя Selenium
        """
        logger.info(f"🔍 Парсинг The Hill URL: {url[:50]}...")
        
        try:
            # Используем Selenium для получения контента
            logger.info("🔍 Selenium парсинг для получения заголовка и контента...")
            selenium_result = self._parse_thehill_selenium(url)
            logger.info(f"🔍 Selenium результат: {selenium_result}")
            
            if selenium_result and selenium_result.get('title'):
                logger.info(f"✅ Selenium парсинг успешен: {selenium_result['title'][:50]}...")
                logger.info(f"📄 Selenium контент: {len(selenium_result.get('content', ''))} символов")
                
                return {
                    'title': selenium_result.get('title', ''),
                    'description': selenium_result.get('description', ''),
                    'content': selenium_result.get('content', ''),
                    'images': selenium_result.get('images', []),
                    'videos': selenium_result.get('videos', []),
                    'published': selenium_result.get('published', ''),
                    'source': 'The Hill',
                    'content_type': 'news_article'
                }
            else:
                logger.warning("❌ Selenium парсинг не удался")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга The Hill URL: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {}
    
    def _parse_thehill_selenium(self, url: str) -> Dict[str, Any]:
        """Selenium парсинг The Hill"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from bs4 import BeautifulSoup
            import time
            
            # Настройка Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                driver.get(url)
                time.sleep(3)  # Ждем загрузки
                
                # Получаем HTML
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                logger.info(f"📄 HTML длина: {len(html)} символов")
                
                # Извлекаем заголовок
                title = ""
                title_selectors = [
                    'h1.headline__text',
                    'h1[class*="headline"]',
                    'h1',
                    'meta[property="og:title"]'
                ]
                
                for selector in title_selectors:
                    try:
                        if 'meta' in selector:
                            title_elem = soup.select_one(selector)
                            if title_elem:
                                title = title_elem.get('content', '').strip()
                        else:
                            title_elem = soup.select_one(selector)
                            if title_elem:
                                title = title_elem.get_text().strip()
                        
                        if title:
                            logger.info(f"✅ Заголовок найден через '{selector}': {title[:50]}...")
                            break
                    except:
                        pass

                # Очистка заголовка от служебных хвостов
                if title:
                    cleanup_patterns = [
                        r"\s*\|\s*The Hill\s*$",
                        r"\s*-\s*The Hill\s*$",
                        r"\s*–\s*The Hill\s*$",
                    ]
                    for pat in cleanup_patterns:
                        title = re.sub(pat, "", title, flags=re.IGNORECASE)
                
                # Извлекаем описание
                description = ""
                desc_selectors = [
                    'p.article__dek',
                    'div.article__dek p',
                    'meta[property="og:description"]',
                    'meta[name="description"]'
                ]
                
                for selector in desc_selectors:
                    try:
                        if 'meta' in selector:
                            desc_elem = soup.select_one(selector)
                            if desc_elem:
                                description = desc_elem.get('content', '').strip()
                        else:
                            desc_elem = soup.select_one(selector)
                            if desc_elem:
                                description = desc_elem.get_text().strip()
                        
                        if description:
                            logger.info(f"✅ Описание найдено через '{selector}'")
                            break
                    except:
                        pass
                
                # Извлекаем дату публикации
                published = ""
                date_selectors = [
                    'time[datetime]',
                    'meta[property="article:published_time"]',
                    'span[class*="timestamp"]'
                ]
                
                for selector in date_selectors:
                    try:
                        date_elem = soup.select_one(selector)
                        if date_elem:
                            if selector.startswith('meta'):
                                published = date_elem.get('content', '').strip()
                            elif selector == 'time[datetime]':
                                published = date_elem.get('datetime', '').strip()
                            else:
                                published = date_elem.get_text().strip()
                            
                            if published:
                                logger.info(f"✅ Дата найдена через '{selector}': {published}")
                                break
                    except:
                        pass
                
                # Если дата не найдена, используем текущую
                if not published:
                    from datetime import datetime
                    published = datetime.now().isoformat()
                
                # Извлекаем полный текст статьи
                article_text = ""
                
                # Пробуем разные селекторы для контента The Hill
                content_selectors = [
                    'div.article__text',
                    'div[class*="article-text"]',
                    'div[class*="article-body"]',
                    'article div p'
                ]
                
                article_paragraphs = []
                
                for selector in content_selectors:
                    try:
                        content_elem = soup.select_one(selector)
                        if content_elem:
                            paragraphs = content_elem.find_all('p')
                            for p in paragraphs:
                                text = p.get_text().strip()
                                # Исключаем служебные тексты
                                if (text and 
                                    len(text) > 20 and
                                    not any(skip in text.lower() for skip in ['advertisement', 'subscribe', 'newsletter'])):
                                    article_paragraphs.append(text)
                            
                            if len(article_paragraphs) > 3:
                                logger.info(f"✅ Контент найден через '{selector}': {len(article_paragraphs)} параграфов")
                                break
                    except:
                        pass
                
                # Если специфичные селекторы не дали результата, собираем все параграфы
                if not article_paragraphs:
                    logger.info("⚠️ Специфичные селекторы не дали результата, собираем все параграфы")
                    paragraphs = soup.find_all('p')
                    for p in paragraphs:
                        text = p.get_text().strip()
                        if (text and 
                            len(text) > 20 and
                            not any(skip in text.lower() for skip in ['advertisement', 'subscribe', 'newsletter', 'cookie', 'privacy'])):
                            article_paragraphs.append(text)
                
                article_text = ' '.join(article_paragraphs)
                logger.info(f"📄 Собрано {len(article_paragraphs)} параграфов, общая длина: {len(article_text)} символов")
                
                # Извлекаем изображения
                images: List[str] = []

                def add_image(u: str):
                    if not u:
                        return
                    full = urljoin(url, u)
                    if full not in images:
                        images.append(full)

                # Сначала meta tags
                og_img = soup.select_one('meta[property="og:image"]')
                if og_img and og_img.get('content'):
                    add_image(og_img.get('content').strip())
                
                tw_img = soup.select_one('meta[name="twitter:image"], meta[name="twitter:image:src"]')
                if tw_img and tw_img.get('content'):
                    add_image(tw_img.get('content').strip())

                # Изображения из статьи
                article_el = soup.select_one('article') or soup
                for img in article_el.select('img')[:5]:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
                    if not src and img.get('srcset'):
                        # Берем последнее (обычно самое большое)
                        parts = [p.strip() for p in img.get('srcset').split(',') if p.strip()]
                        if parts:
                            src = parts[-1].split()[0]
                    
                    # Фильтруем маленькие и служебные изображения
                    if src:
                        src_lower = src.lower()
                        if any(skip in src_lower for skip in ['logo', 'icon', 'avatar', 'favicon', 'sprite']):
                            continue
                        add_image(src)

                # Сортируем изображения по приоритету
                def score_image(u: str) -> int:
                    s = u.lower()
                    score = 0
                    if any(size in s for size in ['1200', '1920', '2000', 'large']):
                        score += 100
                    if 'thehill.com' in s:
                        score += 40
                    if any(kw in s for kw in ['feature', 'hero', 'main']):
                        score += 30
                    if any(skip in s for skip in ['logo', 'icon', 'favicon', 'sprite', 'thumbnail']):
                        score -= 80
                    if s.endswith('.jpg') or '.jpg' in s:
                        score += 5
                    return score

                images = sorted(list(dict.fromkeys(images)), key=score_image, reverse=True)
                
                logger.info(f"📸 Найдено {len(images)} изображений")
                for i, img in enumerate(images[:3], 1):
                    logger.info(f"  📸 Изображение {i}: {img[:100]}...")

                # Извлекаем видео
                videos: List[str] = []
                
                # Список рекламных доменов для фильтрации
                ad_domains = [
                    'blob:',  # JavaScript blob URLs - не скачиваемые
                    'flashtalking.com',  # Реклама
                    'doubleclick.net',  # Google Ads
                    'googlesyndication.com',  # Google Ads
                    'googleadservices.com',  # Google Ads
                    'amazon-adsystem.com',  # Amazon Ads
                    'ads.yahoo.com',  # Yahoo Ads
                    'advertising.com',  # AOL Ads
                    'adnxs.com',  # AppNexus
                    'outbrain.com',  # Outbrain
                    'taboola.com',  # Taboola
                ]
                
                def is_ad_video(video_url: str) -> bool:
                    """Проверяет, является ли URL рекламным видео"""
                    url_lower = video_url.lower()
                    return any(ad_domain in url_lower for ad_domain in ad_domains)
                
                # Ищем видео YouTube, Vimeo (обычно встроенный контент, не реклама)
                for iframe in soup.find_all('iframe'):
                    src = iframe.get('src', '')
                    if src and any(vid in src for vid in ['youtube', 'vimeo', 'jwplayer']):
                        if not is_ad_video(src):
                            videos.append(src)
                        else:
                            logger.info(f"🚫 Пропускаем рекламное видео: {src[:80]}...")
                
                # HTML5 видео НЕ ИЗВЛЕКАЕМ с The Hill - обычно это реклама
                # Если нужны HTML5 видео, раскомментируйте код ниже
                # for video in soup.find_all('video'):
                #     src = video.get('src', '')
                #     if src and not is_ad_video(src):
                #         videos.append(urljoin(url, src))
                #     for source in video.find_all('source'):
                #         src = source.get('src', '')
                #         if src and not is_ad_video(src):
                #             videos.append(urljoin(url, src))

                logger.info(f"🎬 Найдено {len(videos)} видео (после фильтрации рекламы)")

                return {
                    'title': title,
                    'description': description,
                    'content': article_text,
                    'published': published,
                    'images': images,
                    'videos': videos
                }
                
            finally:
                driver.quit()
            
        except Exception as e:
            logger.error(f"❌ Ошибка Selenium парсинга The Hill: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {}
    
    def extract_media(self, url: str, content: Dict[str, Any]) -> Dict[str, List[str]]:
        """Возвращает медиа из контента"""
        images = content.get('images', []) or []
        videos = content.get('videos', []) or []
        logger.info(f"📸 The Hill media for this URL: images={len(images)}, videos={len(videos)}")
        return {'images': images, 'videos': videos}
    
    def validate_content(self, content: Dict[str, Any]) -> bool:
        """Валидирует контент"""
        # Сначала проверяем факты
        if not self.content_validator.validate_facts(content):
            logger.warning("Контент не прошел проверку фактов")
            return False
        
        # Проверяем наличие медиа
        images = content.get('images', [])
        videos = content.get('videos', [])
        
        if not images and not videos:
            logger.warning("❌ The Hill контент не имеет медиа - бракуем")
            return False
        
        logger.info(f"✅ The Hill контент имеет медиа: {len(images)} изображений, {len(videos)} видео")
        
        # Проверяем заголовок
        title = content.get('title', '')
        if not self.content_validator.validate_title(title):
            logger.warning("Контент не прошел валидацию: Невалидный заголовок")
            return False
        
        # Если описание пустое, генерируем его из заголовка
        description = content.get('description', '').strip()
        if not description:
            logger.info("📝 Описание пустое, генерируем из заголовка")
            content['description'] = f"Новость: {title}"
        
        return True
    
    def get_fallback_media(self, title: str) -> Dict[str, List[str]]:
        """Возвращает fallback медиа"""
        images = self.media_extractor.get_fallback_images(title)
        return {
            'images': images,
            'videos': []
        }

