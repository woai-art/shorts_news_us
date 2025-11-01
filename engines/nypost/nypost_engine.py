"""
New York Post news source engine
"""

from typing import Dict, Any, List
import logging
from urllib.parse import urljoin
import re
from ..base import SourceEngine, MediaExtractor, ContentValidator

logger = logging.getLogger(__name__)


class NYPostMediaExtractor(MediaExtractor):
    """Извлекатель медиа для NY Post"""
    
    def extract_images(self, url: str, content: Dict[str, Any]) -> List[str]:
        """Извлекает изображения из контента NY Post"""
        images = []
        
        if 'images' in content:
            for img_url in content['images']:
                if self.validate_image_url(img_url):
                    images.append(img_url)
        
        return images
    
    def extract_videos(self, url: str, content: Dict[str, Any]) -> List[str]:
        """Извлекает видео из контента NY Post"""
        videos = []
        
        if 'videos' in content:
            for vid_url in content['videos']:
                if self.validate_video_url(vid_url):
                    videos.append(vid_url)
        
        return videos
    
    def get_fallback_images(self, title: str) -> List[str]:
        """Возвращает fallback изображения для NY Post"""
        title_lower = title.lower()
        
        # Политические темы
        if any(word in title_lower for word in ['congress', 'senate', 'house', 'capitol', 'politics', 'election']):
            return ['https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=1280&h=720&fit=crop']
        
        # Бизнес темы
        elif any(word in title_lower for word in ['business', 'wall street', 'economy', 'market', 'finance']):
            return ['https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1280&h=720&fit=crop']
        
        # Криминал
        elif any(word in title_lower for word in ['crime', 'police', 'arrest', 'shooting', 'murder']):
            return ['https://images.unsplash.com/photo-1532292994-3c4e6e3ab3b9?w=1280&h=720&fit=crop']
        
        # Нью-Йорк
        elif any(word in title_lower for word in ['new york', 'nyc', 'manhattan', 'brooklyn']):
            return ['https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?w=1280&h=720&fit=crop']
        
        # Общая тематика
        else:
            return ['https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1280&h=720&fit=crop']


class NYPostContentValidator(ContentValidator):
    """Валидатор контента для NY Post"""
    
    def validate_quality(self, content: Dict[str, Any]) -> bool:
        """Валидирует качество контента NY Post"""
        errors = self.get_validation_errors(content)
        
        if errors:
            logger.warning(f"Контент NY Post не прошел валидацию: {', '.join(errors)}")
            return False
        
        return True


class NYPostEngine(SourceEngine):
    """
    Движок для обработки новостей New York Post
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Инициализация движка NY Post"""
        super().__init__(config)
        self.media_extractor = NYPostMediaExtractor(config)
        self.content_validator = NYPostContentValidator(config)
    
    def _get_source_name(self) -> str:
        """Возвращает название источника"""
        return "New York Post"
    
    def _get_supported_domains(self) -> List[str]:
        """Возвращает поддерживаемые домены"""
        return ['nypost.com', 'www.nypost.com']
    
    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        return any(domain in url.lower() for domain in self.supported_domains)
    
    def parse_url(self, url: str, driver=None) -> Dict[str, Any]:
        """
        Парсит URL NY Post используя Selenium
        """
        logger.info(f"🔍 Парсинг NY Post URL: {url[:50]}...")
        
        try:
            # Используем Selenium для получения контента
            logger.info("🔍 Selenium парсинг для получения заголовка и контента...")
            selenium_result = self._parse_nypost_selenium(url)
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
                    'author': selenium_result.get('author', ''),
                    'source': 'New York Post',
                    'content_type': 'news_article'
                }
            else:
                logger.warning("❌ Selenium парсинг не удался")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга NY Post URL: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {}
    
    def _parse_nypost_selenium(self, url: str) -> Dict[str, Any]:
        """Selenium парсинг NY Post"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from bs4 import BeautifulSoup
            import time
            
            # Настройка Chrome для обхода антибот защиты
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-webgl')
            chrome_options.add_argument('--disable-webgl2')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            
            # Ускорение загрузки
            chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # Отключаем загрузку изображений
            chrome_options.add_argument('--disable-javascript-harmony')
            
            # Реалистичный User-Agent (свежий Chrome)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
            
            # Отключаем признаки автоматизации
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Добавляем реалистичные настройки браузера
            chrome_options.add_experimental_option('prefs', {
                'profile.default_content_setting_values': {
                    'notifications': 2,
                    'geolocation': 2,
                    'images': 2,  # Блокируем изображения
                }
            })
            
            # Стратегия загрузки: eager (не ждем полной загрузки всех ресурсов)
            chrome_options.page_load_strategy = 'eager'
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # Увеличенные таймауты для NY Post (сайт может быть медленным)
                driver.set_page_load_timeout(60)  # Увеличен до 60 секунд
                driver.set_script_timeout(20)
                
                # Скрываем признаки WebDriver
                driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en']
                        });
                    '''
                })
                
                # Retry механизм для загрузки страницы
                max_retries = 2
                retry_count = 0
                page_loaded = False
                
                while retry_count < max_retries and not page_loaded:
                    try:
                        # Загружаем страницу
                        if retry_count > 0:
                            logger.info(f"🔄 Повторная попытка загрузки ({retry_count + 1}/{max_retries})...")
                        else:
                            logger.info(f"🌐 Загружаем страницу: {url[:60]}...")
                        
                        # Пробуем загрузить страницу с принудительной остановкой
                        try:
                            driver.get(url)
                        except Exception as timeout_error:
                            # Если таймаут, пытаемся остановить загрузку и использовать то, что есть
                            if 'timeout' in str(timeout_error).lower():
                                logger.warning("⏰ Таймаут загрузки - останавливаем и используем загруженное...")
                                try:
                                    driver.execute_script("window.stop();")
                                except:
                                    pass
                            else:
                                raise
                        
                        page_loaded = True
                        
                        # Ждем загрузки контента
                        logger.info("⏳ Ожидаем загрузки контента...")
                        time.sleep(5)  # Даем время на рендеринг JavaScript
                        
                    except Exception as load_error:
                        retry_count += 1
                        if retry_count >= max_retries:
                            logger.error(f"❌ Не удалось загрузить страницу после {max_retries} попыток: {str(load_error)[:200]}")
                            raise
                        else:
                            logger.warning(f"⚠️ Ошибка загрузки, пробуем снова... ({retry_count}/{max_retries})")
                            time.sleep(2)
                
                # Получаем данные из браузера ДО того, как он может крашнуться
                # Получаем title СРАЗУ, пока браузер жив
                page_title = driver.title
                logger.info(f"📋 Page title: {page_title[:60]}...")
                
                # Проверяем, не получили ли мы страницу ошибки Chrome
                if 'не удается' in page_title.lower() or 'site can' in page_title.lower() or 'this site' in page_title.lower():
                    logger.error(f"❌ Получена страница ошибки браузера: {page_title}")
                    logger.error("❌ NY Post заблокировал доступ или сайт недоступен")
                    return {}
                
                # Получаем HTML
                html = driver.page_source
                logger.info(f"📄 HTML длина: {len(html)} символов")
                
            finally:
                # Закрываем браузер СРАЗУ после получения HTML
                try:
                    driver.quit()
                    logger.info("✅ Браузер закрыт")
                except:
                    pass
            
            # Теперь обрабатываем HTML БЕЗ открытого браузера
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлекаем заголовок
            title = ""
            title_selectors = [
                'h1.single-headline',
                'h1.headline',
                'h1[class*="headline"]',
                'h1.entry-heading',
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
                    r"\s*\|\s*New York Post\s*$",
                    r"\s*-\s*New York Post\s*$",
                    r"\s*–\s*New York Post\s*$",
                    r"\s*\|\s*NY Post\s*$",
                    r"\s*-\s*NY Post\s*$",
                ]
                for pat in cleanup_patterns:
                    title = re.sub(pat, "", title, flags=re.IGNORECASE)
            
            # Извлекаем описание
            description = ""
            desc_selectors = [
                'h2.subtitle',
                'h2.dek',
                'div.entry-content-description',
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
                        logger.info(f"✅ Описание найден через '{selector}'")
                        break
                except:
                    pass
            
            # Извлекаем автора
            author = ""
            author_selectors = [
                'div.author-byline a',
                'p.byline a',
                'span.author',
                'a[rel="author"]',
                'meta[name="author"]'
            ]
            
            for selector in author_selectors:
                try:
                    if 'meta' in selector:
                        author_elem = soup.select_one(selector)
                        if author_elem:
                            author = author_elem.get('content', '').strip()
                    else:
                        author_elem = soup.select_one(selector)
                        if author_elem:
                            author = author_elem.get_text().strip()
                    
                    if author:
                        # Очистка от "By "
                        author = re.sub(r'^By\s+', '', author, flags=re.IGNORECASE)
                        logger.info(f"✅ Автор найден через '{selector}': {author}")
                        break
                except:
                    pass
                
            # Извлекаем дату публикации
            published = ""
            date_selectors = [
                'time[datetime]',
                'meta[property="article:published_time"]',
                'p.byline time',
                'span.timestamp'
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
            
            # Пробуем разные селекторы для контента NY Post
            content_selectors = [
                'div.entry-content.single-content p',
                'div.single-content p',
                'div.entry-content p',
                'div[class*="article-content"] p',
                'div[class*="entry-content"] p',
                'article p'
            ]
            
            article_paragraphs = []
            
            for selector in content_selectors:
                try:
                    content_elem = soup.select_one(selector.split(' p')[0])
                    if content_elem:
                        paragraphs = content_elem.find_all('p')
                        for p in paragraphs:
                            text = p.get_text().strip()
                            # Исключаем служебные тексты
                            if (text and 
                                len(text) > 20 and
                                not any(skip in text.lower() for skip in [
                                    'advertisement', 'subscribe', 'newsletter', 
                                    'filed under', 'read next', 'explore more',
                                    'recommended', 'trending', 'share this',
                                    'facebook', 'twitter', 'instagram'
                                ])):
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
                        not any(skip in text.lower() for skip in [
                            'advertisement', 'subscribe', 'newsletter', 
                            'cookie', 'privacy', 'filed under',
                            'read next', 'explore more', 'recommended'
                        ])):
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
            article_el = soup.select_one('article') or soup.select_one('div.entry-content') or soup
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
                    if any(skip in src_lower for skip in ['logo', 'icon', 'avatar', 'favicon', 'sprite', 'tracking']):
                        continue
                    add_image(src)

            # Сортируем изображения по приоритету
            def score_image(u: str) -> int:
                s = u.lower()
                score = 0
                if any(size in s for size in ['1200', '1920', '2000', 'large', '1024']):
                    score += 100
                if 'nypost.com' in s:
                    score += 40
                if any(kw in s for kw in ['feature', 'hero', 'main']):
                    score += 30
                if any(skip in s for skip in ['logo', 'icon', 'favicon', 'sprite', 'thumbnail', 'tracking']):
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

            logger.info(f"🎬 Найдено {len(videos)} видео (после фильтрации рекламы)")

            return {
                'title': title,
                'description': description,
                'content': article_text,
                'published': published,
                'author': author,
                'images': images,
                'videos': videos
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка Selenium парсинга NY Post: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {}
    
    def extract_media(self, url: str, content: Dict[str, Any]) -> Dict[str, List[str]]:
        """Возвращает медиа из контента"""
        images = content.get('images', []) or []
        videos = content.get('videos', []) or []
        logger.info(f"📸 NY Post media for this URL: images={len(images)}, videos={len(videos)}")
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
            logger.warning("❌ NY Post контент не имеет медиа - бракуем")
            return False
        
        logger.info(f"✅ NY Post контент имеет медиа: {len(images)} изображений, {len(videos)} видео")
        
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

