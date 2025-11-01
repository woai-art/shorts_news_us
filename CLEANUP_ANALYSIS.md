# 🧹 Анализ проекта для очистки

## 📋 Используемые компоненты

### ✅ Активные точки входа
- `channel_monitor.py` - основной скрипт мониторинга Telegram
- `scripts/main_orchestrator.py` - оркестратор обработки новостей
- `process_news_by_id.py` - ручная обработка новости по ID

### ✅ Активные скрипты (scripts/)
- `llm_processor.py`
- `video_exporter.py`
- `youtube_uploader.py`
- `telegram_bot.py`
- `telegram_publisher.py`
- `media_manager.py`
- `news_processor.py`
- `analytics.py`
- `web_parser.py`
- `video_preprocessor.py`
- `main_orchestrator.py`

### ✅ Активные движки (engines/)
- `politico/` - ✅ используется
- `washingtonpost/` - ✅ используется
- `twitter/` - ✅ используется
- `nbcnews/` - ✅ используется
- `abcnews/` - ✅ используется
- `telegrampost/` - ✅ используется
- `financialtimes/` - ✅ используется
- `thehill/` - ✅ используется
- `nypost/` - ✅ используется
- `base/` - ✅ базовые классы
- `registry.py` - ✅ регистр движков

### ❌ Неиспользуемые движки
- `apnews/` - не импортирован в main_orchestrator
- `cnn/` - не импортирован в main_orchestrator
- `reuters/` - не импортирован в main_orchestrator
- `wsj/` - закомментирован (платный + Cloudflare)

---

## 🗑️ Файлы для удаления

### 1. Тестовые файлы (test_*.py)
```
test_avatar_fix.py
test_avatar_simple.py
test_db_loading.py
test_direct_orchestrator.py
test_fallback_package.py
test_gemini_api.py
test_gemini_correct.py
test_get_news_by_id.py
test_llm_debug.py
test_media_display.py
test_news_333.py
test_news_334.py
test_news_336_content.py
test_news_346_data.py
test_news_347_data.py
test_nypost_engine.py
test_nypost_quick.py
test_system.py
test_template_data.py
test_template_quick.py
test_thehill_engine.py
test_thehill_logo.py
test_thehill_quick.py
test_twitter_avatar.py
test_twitter_full_cycle.py
test_twitter_media_manager.py
test_twitter_simple.py
test_video_generation.py
test_zakka_avatar.py
test_zakka_full_cycle.py
test_zakka_video_generation.py
test_footer.png
```

### 2. Отладочные скрипты (debug_*.py, check_*.py)
```
debug_avatar_urls.py
check_avatars.py
check_db.py
check_env.py
check_politico_db.py
check_table_structure.py
check_urls.py
quick_check.py
monitor_logs.py
gemini_direct.py
verify_models.py
view_analytics.py
```

### 3. Миграционные скрипты (выполнены)
```
add_avatar_url_migration.py
migrate_db.py
cleanup_database.py
fix_nbc_urls.py
update_politico_news.py
```

### 4. Простые тесты ботов (заменены основными)
```
simple_bot.py
minimal_bot.py
bot_launcher.py
start_bot_subprocess.py
```

### 5. Документация разработки (.md файлы)
```
AVATAR_LOGOS_SUMMARY.md
FINANCIAL_TIMES_ENGINE.md
FIX_SOURCE_LOGOS.md
FIX_TELEGRAM_LOCAL_FILES.md
FIX_TELEGRAM_MEDIA_REPROCESSING.md
GITHUB_SETUP.md
NYPOST_ANTIBOT_FIX.md
NYPOST_ANTIBOT_READY.md
NYPOST_ENGINE_INSTALLATION.md
NYPOST_ENGINE_UPDATE.md
NYPOST_READY_TO_TEST.md
TELEGRAM_AVATAR.md
TELEGRAM_POST_ENGINE.md
TELEGRAM_WORKFLOW.md
TEXT_ADAPTIVE_FONT_FIX.md
TEXT_CROP_FIX_FINAL.md
TEXT_CROP_FIX.md
THEHILL_ENGINE_CHECKLIST.md
THEHILL_ENGINE_SUMMARY.md
THEHILL_FINAL_SUMMARY.md
THEHILL_INSTALLATION_COMPLETE.md
THEHILL_LOGO_INTEGRATION.md
THEHILL_VIDEO_FIX.md
TWITTER_AVATAR_SOLUTION.md
VIDEO_GENERATION_GUIDE.md
WSJ_ENGINE_SUMMARY.md
```

### 6. Логи разработки (*.log)
```
avatar_test.log
twitter_avatar_test.log
twitter_full_test.log
twitter_simple_test.log
video_generation_test.log
zakka_avatar_test.log
zakka_full_cycle_test.log
```

### 7. Прочие разовые файлы
```
env_template.txt
promt.txt
selenium_logging_config.py (дублируется с logger_config.py)
start.ps1 (есть start.py и .bat файлы)
```

### 8. Неиспользуемые папки
```
animations/ (если пусто)
assets/logos/ (если не используется)
test_media/ (тестовые медиа)
media/telegram/ (старые тесты)
```

### 9. Неиспользуемые движки
```
engines/apnews/
engines/cnn/
engines/reuters/
engines/wsj/
```

---

## ✅ Сохраняем

### Важные конфиг-файлы
- `config/config.yaml`
- `config/prompts.yaml`
- `config/client_secret.json`
- `config/token.json`
- `.env` (если есть)

### Важные данные
- `data/user_news.db` - основная БД
- `data/analytics.json` - аналитика
- `resources/` - шрифты, музыка, логотипы
- `templates/` - HTML шаблоны
- `outputs/` - готовые видео (можно очистить старые)
- `temp/` - временные файлы (можно очистить)

### Структура и запуск
- `README.md` - основная документация
- `PROJECT_INFO.md` - информация о проекте
- `requirements.txt` - зависимости
- `start.py` - запуск оркестратора
- `start_monitor.bat` / `start_monitor.py` - запуск монитора
- `start_bot.bat` - запуск бота
- `check_status.bat` - проверка статуса

---

## 📊 Итого к удалению

- **Test файлы**: ~30 файлов
- **Debug скрипты**: ~13 файлов
- **Миграции**: ~5 файлов
- **Простые боты**: ~4 файла
- **Документация .md**: ~27 файлов
- **Логи .log**: ~7 файлов
- **Прочее**: ~3 файла
- **Неиспользуемые движки**: 4 папки
- **Неиспользуемые папки**: 3-4 папки

**Всего: ~96 файлов + 7-8 папок**

**Экономия места**: ~несколько МБ + улучшение читаемости проекта

