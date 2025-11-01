#!/bin/bash
# Скрипт для просмотра логов Shorts News бота

LOG_DIR="logs"
SERVICE_NAME="shorts-news.service"

show_help() {
    echo "📋 Команды для просмотра логов:"
    echo "  ./view_logs.sh live      - Логи в реальном времени (systemd)"
    echo "  ./view_logs.sh file      - Логи из файла logs/channel_monitor.log"
    echo "  ./view_logs.sh errors    - Только ошибки из файлов"
    echo "  ./view_logs.sh today     - Логи за сегодня"
    echo "  ./view_logs.sh last      - Последние 100 строк"
    echo "  ./view_logs.sh grep PATTERN - Поиск по паттерну"
    echo ""
}

case "$1" in
    "live")
        echo "📺 Логи в реальном времени (Ctrl+C для выхода):"
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    "file")
        echo "📄 Логи из файла (Ctrl+C для выхода):"
        tail -f $LOG_DIR/channel_monitor.log 2>/dev/null || echo "Файл логов не найден"
        ;;
    "errors")
        echo "🚨 Ошибки из логов:"
        grep -i "error\|exception\|failed" $LOG_DIR/*.log 2>/dev/null || echo "Ошибок не найдено"
        ;;
    "today")
        echo "📅 Логи за сегодня:"
        TODAY=$(date +%Y-%m-%d)
        grep "$TODAY" $LOG_DIR/channel_monitor.log 2>/dev/null || echo "Логов за сегодня не найдено"
        ;;
    "last")
        echo "📜 Последние 100 строк:"
        tail -n 100 $LOG_DIR/channel_monitor.log 2>/dev/null || echo "Лог файл не найден"
        ;;
    "grep")
        if [ -z "$2" ]; then
            echo "❌ Укажите паттерн для поиска"
            exit 1
        fi
        echo "🔍 Поиск '$2' в логах:"
        grep -i "$2" $LOG_DIR/*.log 2>/dev/null || echo "Совпадений не найдено"
        ;;
    *)
        show_help
        ;;
esac

