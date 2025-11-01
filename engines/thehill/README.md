# The Hill News Engine

Движок для парсинга новостей с сайта The Hill (thehill.com).

## Возможности

- ✅ Парсинг заголовков статей
- ✅ Извлечение описаний
- ✅ Получение полного текста статьи
- ✅ Извлечение изображений (og:image, twitter:image, изображения из статьи)
- ✅ Извлечение видео (YouTube, Vimeo, HTML5)
- ✅ Определение даты публикации
- ✅ Валидация контента
- ✅ Fallback изображения по тематике

## Поддерживаемые домены

- `thehill.com`
- `www.thehill.com`

## Технологии

- **Selenium**: для обхода JavaScript и динамической загрузки контента
- **BeautifulSoup4**: для парсинга HTML
- **Chrome headless**: для незаметной работы

## Селекторы

### Заголовок
- `h1.headline__text`
- `h1[class*="headline"]`
- `h1`
- `meta[property="og:title"]` (fallback)

### Описание
- `p.article__dek`
- `div.article__dek p`
- `meta[property="og:description"]` (fallback)
- `meta[name="description"]` (fallback)

### Контент
- `div.article__text`
- `div[class*="article-text"]`
- `div[class*="article-body"]`
- `article div p` (fallback)

### Изображения
- `meta[property="og:image"]` (приоритет)
- `meta[name="twitter:image"]`
- `article img` (изображения из статьи)
- Фильтрация: пропускаем логотипы, иконки, маленькие изображения

### Дата публикации
- `time[datetime]`
- `meta[property="article:published_time"]`
- `span[class*="timestamp"]`

## Валидация

1. **Обязательные поля**:
   - Заголовок (минимум 10 символов)
   - Хотя бы одно изображение или видео
   
2. **Опциональные поля**:
   - Описание (генерируется из заголовка, если отсутствует)
   - Контент

3. **Проверка фактов**: базовая валидация через ContentValidator

## Fallback изображения

Движок предоставляет fallback изображения по тематике новости:

- **Конгресс/Сенат**: Капитолий
- **Президент**: Белый дом
- **Выборы**: Избирательная тематика
- **Общее**: Вашингтон

Все изображения берутся с Unsplash в высоком разрешении (1280x720).

## Пример использования

```python
from engines import registry, TheHillEngine

# Регистрируем движок
registry.register_engine('thehill', TheHillEngine)

# Получаем движок для URL
url = "https://thehill.com/homenews/house/5545981-shutdown-momentum-democrats/"
engine = registry.get_engine_for_url(url, config)

if engine:
    # Парсим URL
    content = engine.parse_url(url)
    
    # Извлекаем медиа
    media = engine.extract_media(url, content)
    
    # Валидируем контент
    if engine.validate_content(content):
        print("✅ Контент валиден!")
        print(f"Заголовок: {content['title']}")
        print(f"Изображений: {len(media['images'])}")
        print(f"Видео: {len(media['videos'])}")
```

## Примеры URL

- https://thehill.com/homenews/house/5545981-shutdown-momentum-democrats/
- https://thehill.com/homenews/senate/
- https://thehill.com/policy/national-security/
- https://thehill.com/policy/healthcare/

## Фильтрация видео

Движок автоматически фильтрует рекламные видео:

### Блокируются:
- ❌ **blob: URLs** - JavaScript временные объекты (нескачиваемые)
- ❌ **flashtalking.com** - рекламная платформа
- ❌ **doubleclick.net** - Google Ads
- ❌ **HTML5 видео** - обычно реклама на The Hill

### Разрешаются:
- ✅ **YouTube** - встроенный контент (если не реклама)
- ✅ **Vimeo** - встроенный контент (если не реклама)

**Примечание**: Большинство новостей The Hill не содержат видео, только изображения. Это нормально.

## Известные ограничения

1. **JavaScript**: требует Selenium, так как контент загружается динамически
2. **Производительность**: парсинг может занимать 3-5 секунд из-за ожидания загрузки
3. **Rate limiting**: сайт может ограничивать частоту запросов
4. **Видео**: HTML5 видео не извлекаются (обычно реклама)

## Troubleshooting

### Проблема: Пустой контент
- **Причина**: Недостаточное время ожидания загрузки JavaScript
- **Решение**: Увеличить `time.sleep()` в методе `_parse_thehill_selenium()`

### Проблема: Нет изображений
- **Причина**: Изображения могут загружаться через lazy-loading
- **Решение**: Проверить атрибуты `data-src`, `data-lazy-src`, `srcset`

### Проблема: Блокировка по User-Agent
- **Причина**: Сайт распознает автоматизацию
- **Решение**: Обновить User-Agent на более свежий

## Версия

- **Версия движка**: 1.0.0
- **Дата создания**: 2025-10-09
- **Автор**: shorts_news engine system

