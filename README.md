# botdc
Вот основные команды для управления ботом через screen в Ubuntu:
Запуск бота:
# Создать новую screen сессию с именем discord-bot
screen -S discord-bot

# После открытия screen, запустить бота
python3 bot.py

# Отключиться от сессии (бот продолжит работать)
# Нажмите Ctrl + A, затем D
Управление запущенным ботом:
# Посмотреть список всех screen сессий
screen -ls

# Подключиться к сессии discord-bot
screen -r discord-bot

# Принудительно подключиться (если сессия "залипла")
screen -d -r discord-bot
Остановка бота:
# 1. Подключитесь к сессии
screen -r discord-bot

# 2. Остановите бота
# Нажмите Ctrl + C

# 3. Закройте screen сессию
# Нажмите Ctrl + D
Принудительное закрытие:
# Убить конкретную screen сессию по имени
screen -X -S discord-bot quit

# Убить все screen сессии
killall screen
Полезные советы:
Если вы забыли отключиться и просто закрыли терминал, сессия останется активной
Используйте screen -ls чтобы увидеть все активные сессии
Если появляется ошибка "Cannot open your terminal", используйте:
script /dev/null
screen -r discord-bot