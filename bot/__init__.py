"""
bot/
~~~

Telegram bot package.

Modules:
    config     — загрузка настроек из .env
    logging    — настройка логов
    prefs      — пользовательские настройки (per-chat FSM)
    semaphores — анти-спам (per-user и global)
    fsm        — состояния FSM
    pipeline   — основной конвейер обработки видео
    handlers   — хендлеры aiogram
    texts      — тексты и подписи для сообщений
    formatters — форматирование (время, байты, экранирование)
    main       — точка входа (run / polling)
"""
