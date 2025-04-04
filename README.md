# БОТЯРА
  <img src="https://media1.tenor.com/m/EqFmLAryG_MAAAAd/%D0%B7%D0%B0%D0%B9%D1%87%D0%B8%D0%BA.gif" width="600"/>
</div>

## Описание бота
Этот бот Discord предназначен для управления воспроизведением музыки и радиостанций, а также для выполнения различных команд, таких как кик участников, очистка чата и генерация текстов с помощью GPT. Бот использует библиотеку `discord.py` и поддерживает команды через интерфейс Slash.

### Основные функции:
- **Воспроизведение радио**: Бот может воспроизводить различные радиостанции по запросу.
- **Управление голосовым каналом**: Возможность исключать случайных участников из голосового канала.
- **Генерация текста**: Использует GPT для генерации текстов по запросу.
- **Очистка чата**: Удаление сообщений из чата, включая сообщения бота и упоминания.
- **Управление воспроизведением**: Возможность ставить на паузу, останавливать и регулировать громкость воспроизведения.

### Команды:
- `/radio`: Включить радио и выбрать радиостанцию.
- `/kick`: Исключить случайного участника из голосового канала.
- `/shiza`: Включить зацикленное воспроизведение песен.
- `/gpt`: Сгенерировать текст с помощью GPT.
- `/image`: Генерация изображения по запросу.
- `/clear`: Очистить чат от сообщений бота и команд.
- `/clearall`: Очистить чат от всех сообщений (только для администратора).
- `/restart`: Перезапустить бота (только для администратора).
- `/spam`: Удалить сообщения с упоминаниями.

## Запуск бота
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
