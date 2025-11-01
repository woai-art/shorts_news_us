# New York Post Engine

Движок для парсинга новостей с сайта New York Post.

## Особенности

- ✅ Полная поддержка парсинга статей NY Post
- ✅ Selenium-based парсинг для динамического контента
- ✅ Извлечение изображений и видео
- ✅ Фильтрация рекламных видео
- ✅ Поддержка авторов и дат публикации
- ✅ Умные fallback изображения по тематикам

## Поддерживаемые домены

- `nypost.com`
- `www.nypost.com`

## Структура парсинга

### Заголовок
Селекторы (в порядке приоритета):
- `h1.single-headline`
- `h1.headline`
- `h1[class*="headline"]`
- `h1.entry-heading`
- `h1`
- `meta[property="og:title"]`

### Описание
Селекторы:
- `h2.subtitle`
- `h2.dek`
- `div.entry-content-description`
- `meta[property="og:description"]`
- `meta[name="description"]`

### Контент
Селекторы:
- `div.entry-content.single-content p`
- `div.single-content p`
- `div.entry-content p`
- `div[class*="article-content"] p`

### Автор
Селекторы:
- `div.author-byline a`
- `p.byline a`
- `span.author`
- `a[rel="author"]`
- `meta[name="author"]`

### Изображения
1. Meta tags (og:image, twitter:image)
2. Изображения из контента статьи
3. Автоматическая фильтрация логотипов и служебных изображений
4. Сортировка по приоритету (размер, релевантность)

### Видео
- Поддержка YouTube и Vimeo
- Автоматическая фильтрация рекламных видео
- Список исключений для ad-доменов

## Конфигурация

### config.yaml
```yaml
news_sources:
  nypost:
    domains: ["nypost.com", "www.nypost.com"]
    logo_file: "new-york-post.png"
    display_name: "New York Post"
```

### Логотип
- Путь: `resources/logos/new-york-post.png`
- Формат: PNG с прозрачным фоном

## Fallback изображения по тематикам

Движок автоматически подбирает fallback изображения на основе ключевых слов в заголовке:

- **Политика**: Капитолий (congress, senate, house, capitol, politics, election)
- **Бизнес**: Офисные здания (business, wall street, economy, market, finance)
- **Криминал**: Полиция (crime, police, arrest, shooting, murder)
- **Нью-Йорк**: Панорама NYC (new york, nyc, manhattan, brooklyn)
- **По умолчанию**: Общие новости

## Валидация контента

Движок проверяет:
1. ✅ Наличие заголовка (минимум 10 символов)
2. ✅ Наличие контента (минимум 50 символов)
3. ✅ Наличие хотя бы одного изображения или видео
4. ✅ Проверка фактов (через ContentValidator)

## Тестирование

### Быстрый тест (без парсинга)
```bash
python test_nypost_quick.py
```

### Полный тест (с парсингом реальной статьи)
```bash
python test_nypost_engine.py
```

## Примеры использования

### Базовое использование
```python
from engines.nypost import NYPostEngine

# Создание экземпляра
config = {}
engine = NYPostEngine(config)

# Проверка URL
url = "https://nypost.com/2025/10/24/business/china-russia-sending-attractive-women/"
if engine.can_handle(url):
    # Парсинг
    result = engine.parse_url(url)
    
    print(f"Заголовок: {result['title']}")
    print(f"Автор: {result['author']}")
    print(f"Изображений: {len(result['images'])}")
    print(f"Видео: {len(result['videos'])}")
```

### Использование через Registry
```python
from engines import registry

# Автоматический выбор движка
config = {}
engine = registry.get_engine_for_url(url, config)

if engine:
    result = engine.parse_url(url)
    # ... обработка результата
```

## Интеграция с системой

Движок автоматически регистрируется в `main_orchestrator.py`:

```python
from engines import NYPostEngine
registry.register_engine('nypost', NYPostEngine)
```

## Известные ограничения

1. **Требуется Selenium**: Для парсинга используется Chrome WebDriver
2. **Время парсинга**: ~3-5 секунд на статью
3. **Реклама**: Автоматически фильтруется, но могут быть исключения
4. **Paywall**: Не поддерживается обход платного контента (если есть)

## Зависимости

- `selenium` - для парсинга динамического контента
- `beautifulsoup4` - для разбора HTML
- `Pillow` - для обработки изображений

## История изменений

### v1.0.0 (2025-10-25)
- ✅ Первый релиз
- ✅ Поддержка основных типов статей
- ✅ Извлечение медиа
- ✅ Фильтрация рекламы
- ✅ Fallback изображения

## Автор

Создано на базе архитектуры engines/base/SourceEngine

## Лицензия

Используется в рамках проекта shorts_news

