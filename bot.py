import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio, ButtonStyle, PCMVolumeTransformer
import asyncio
import random
import datetime
from g4f.client import Client

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Переменные для управления воспроизведением звука и радио
is_playing_shiza = False
voice_client = None
current_radio = None  # Добавляем переменную для хранения текущей радиостанции
# Добавьте переменную для хранения сообщения
radio_message = None

#Переменные
ADMIN_USER_ID = 480402325786329091  # Замените 123456789 на ваш ID
VOICE_CHANNEL_ID = 1334607111694450708  # ID голосового канала для проверки
TEXT_CHANNEL_ID = 1334606129015296010   # ID текстового канала для отправки сообщений

# Команда /radio
radio_urls = {
    'геленджик': 'https://serv39.vintera.tv/radio_gel/radio_stream/icecast.audio',
    'кавказ': 'http://radio.alania.net:8000/kvk',
    'аниме': 'https://pool.anison.fm:9000/AniSonFM(320)?nocache=0.9834540412142996',
    'чил': 'http://node-33.zeno.fm/0r0xa792kwzuv?rj-ttl=5&rj-tok=AAABfMtdjJ4AtC1pGWo1_ohFMw',
    'lofi': 'http://stream.zeno.fm/f3wvbbqmdg8uv',
    'кубань': 'http://stream.pervoe.fm:8000',
    'jazz ': 'http://nashe1.hostingradio.ru/jazz-128.mp3'
}

# ID канала для очистки
CLEAR_CHANNEL_ID = 1329025201681334272

@tasks.loop(hours=24)  # Задача, выполняющаяся раз в 24 часа
async def clear_channel_daily():
    channel = bot.get_channel(CLEAR_CHANNEL_ID)

    if channel:
        deleted = await channel.purge(limit=None)  # Удаляем все сообщения
        print(f"Удалено {len(deleted)} сообщений из канала {CLEAR_CHANNEL_ID}.")

@bot.event
async def on_ready():
    clear_channel_daily.start()  # Запускаем задачу при старте бота

# Команда /kick
class KickView(discord.ui.View):
    @discord.ui.button(label="Случайное исключение", style=discord.ButtonStyle.danger)
    async def random_kick(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("Вы должны находиться в голосовом канале.", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        members = [member for member in channel.members if not member.bot]

        # Проверяем, что в канале только 1 участник (включая того, кто нажимает кнопку)
        if len(members) > 1:
            member_to_kick = random.choice(members)
            await member_to_kick.move_to(None)
            await interaction.response.send_message(f"{member_to_kick.name} был исключен из голосового канала.")
        else:
            await interaction.response.send_message("В голосовом канале должно быть минимум 2 участника для исключения.", ephemeral=True)

@bot.slash_command(name="kick", description="Исключить случайного участника из голосового канала.")
async def kick(ctx):
    view = KickView()
    await ctx.respond("Нажмите, чтобы исключить случайного участника:", view=view)

class RadioView(discord.ui.View):
    def __init__(self, radio_urls):
        super().__init__()
        self.radio_urls = radio_urls
        self.volume = 1.0
        self.is_paused = False
        self.add_radio_buttons()
        self.add_control_buttons()

    def add_radio_buttons(self):
        for name in self.radio_urls:
            button = discord.ui.Button(label=name.title(), style=ButtonStyle.primary, custom_id=f"radio_{name}")
            button.callback = self.radio_button_callback
            self.add_item(button)

    def add_control_buttons(self):
        # Stop button
        stop_button = discord.ui.Button(label="⏹️ Стоп", style=ButtonStyle.danger, custom_id="radio_stop")
        stop_button.callback = self.stop_callback
        self.add_item(stop_button)

        # Pause/Resume button
        pause_button = discord.ui.Button(label="⏸️ Пауза", style=ButtonStyle.secondary, custom_id="radio_pause")
        pause_button.callback = self.pause_callback
        self.add_item(pause_button)

        # Volume down button
        volume_down = discord.ui.Button(label="🔉", style=ButtonStyle.secondary, custom_id="volume_down")
        volume_down.callback = self.volume_down_callback
        self.add_item(volume_down)

        # Volume up button
        volume_up = discord.ui.Button(label="🔊", style=ButtonStyle.secondary, custom_id="volume_up")
        volume_up.callback = self.volume_up_callback
        self.add_item(volume_up)

    async def radio_button_callback(self, interaction: discord.Interaction):
        global voice_client, current_radio, radio_message
        
        station = interaction.custom_id.replace("radio_", "")
        url = self.radio_urls[station]

        if not interaction.user.voice:
            await interaction.response.send_message("Вы должны быть в голосовом канале!", ephemeral=True)
            return

        try:
            if voice_client and voice_client.is_connected():
                if voice_client.channel != interaction.user.voice.channel:
                    await voice_client.move_to(interaction.user.voice.channel)
                voice_client.stop()
            else:
                voice_client = await interaction.user.voice.channel.connect()

            current_radio = station
            self.is_paused = False
            audio_source = PCMVolumeTransformer(FFmpegPCMAudio(url), volume=self.volume)
            voice_client.play(audio_source)

            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {station.title()}\n**Громкость:** {int(self.volume * 100)}%\n**Статус:** Играет",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)

    async def pause_callback(self, interaction: discord.Interaction):
        global voice_client
        
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message("Радио не играет!", ephemeral=True)
            return

        try:
            if voice_client.is_playing():
                voice_client.pause()
                self.is_paused = True
                status = "На паузе"
                button_label = "▶️ Продолжить"
            elif voice_client.is_paused():
                voice_client.resume()
                self.is_paused = False
                status = "Играет"
                button_label = "⏸️ Пауза"
            else:
                await interaction.response.send_message("Радио не играет!", ephemeral=True)
                return

            # Update the pause button label
            for child in self.children:
                if child.custom_id == "radio_pause":
                    child.label = button_label

            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {current_radio.title() if current_radio else 'Ничего'}\n**Громкость:** {int(self.volume * 100)}%\n**Статус:** {status}",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
            
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)

    async def stop_callback(self, interaction: discord.Interaction):
        global voice_client, current_radio
        
        if voice_client and voice_client.is_connected():
            voice_client.stop()
            await voice_client.disconnect()
            current_radio = None
            self.is_paused = False
            
            # Reset pause button label
            for child in self.children:
                if child.custom_id == "radio_pause":
                    child.label = "⏸️ Пауза"
            
            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description="**Статус:** Остановлено",
                color=discord.Color.red()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Радио уже остановлено!", ephemeral=True)

    async def volume_up_callback(self, interaction: discord.Interaction):
        global voice_client
        
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            self.volume = min(2.0, self.volume + 0.1)
            if hasattr(voice_client.source, 'volume'):
                voice_client.source.volume = self.volume
            
            status = "На паузе" if self.is_paused else "Играет"
            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {current_radio.title() if current_radio else 'Ничего'}\n**Громкость:** {int(self.volume * 100)}%\n**Статус:** {status}",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Сначала включите радио!", ephemeral=True)

    async def volume_down_callback(self, interaction: discord.Interaction):
        global voice_client
        
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            self.volume = max(0.0, self.volume - 0.1)
            if hasattr(voice_client.source, 'volume'):
                voice_client.source.volume = self.volume
            
            status = "На паузе" if self.is_paused else "Играет"
            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {current_radio.title() if current_radio else 'Ничего'}\n**Громкость:** {int(self.volume * 100)}%\n**Статус:** {status}",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Сначала включите радио!", ephemeral=True)

@bot.slash_command(name="radio", description="Включить радио")
async def radio(ctx):
    embed = discord.Embed(
        title="🎵 Радио Плеер",
        description="**Выберите радиостанцию:**",
        color=discord.Color.blue()
    )
    embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
    view = RadioView(radio_urls)
    await ctx.respond(embed=embed, view=view)

class ShizaView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(ShizaButton("🎵 Литвин", "/home/bot/litvin.mp3"))
        self.add_item(ShizaButton("💫 Сигма", "/home/bot/sigma.mp3"))
        self.add_item(StopShizaButton())

class ShizaButton(discord.ui.Button):
    def __init__(self, label: str, file_path: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.file_path = file_path

    async def callback(self, interaction: discord.Interaction):
        global voice_client, is_playing_shiza
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("Вы должны находиться в голосовом канале!", ephemeral=True)
            return

        voice_client = interaction.guild.voice_client

        if voice_client is None:
            voice_client = await interaction.user.voice.channel.connect()
        elif voice_client.channel != interaction.user.voice.channel:
            await voice_client.move_to(interaction.user.voice.channel)

        if voice_client.is_playing():
            voice_client.stop()

        is_playing_shiza = True
        asyncio.create_task(play_shiza_loop(voice_client, self.file_path))

        # Create embed message
        embed = discord.Embed(
            title="🎮 Шиза Плеер",
            description=f"**Сейчас играет:** {self.label}\n**Статус:** Играет",
            color=discord.Color.purple()
        )
        embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")

        # Get the original message to edit
        message = interaction.message
        await message.edit(embed=embed, view=self.view)

class StopShizaButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⏹️ Остановить", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        global is_playing_shiza, voice_client

        await interaction.response.defer()

        if voice_client and voice_client.is_connected():
            is_playing_shiza = False
            voice_client.stop()
            await voice_client.disconnect()  # Добавляем отключение от голосового канала
            
            # Create embed message for stopped state
            embed = discord.Embed(
                title="🎮 Шиза Плеер",
                description="**Статус:** Остановлено",
                color=discord.Color.red()
            )
            embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")
            
            # Get the original message to edit
            message = interaction.message
            await message.edit(embed=embed, view=self.view)
        else:
            await interaction.followup.send("Сейчас ничего не воспроизводится!", ephemeral=True)

async def play_shiza_loop(voice_client, file_path):
    global is_playing_shiza

    while is_playing_shiza and voice_client and voice_client.is_connected():
        try:
            audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(file_path), volume=1.0)
            voice_client.play(audio_source)
            
            # Ждем, пока текущее воспроизведение не закончится
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
                if not is_playing_shiza:
                    voice_client.stop()
                    return
                    
            # Небольшая пауза перед следующим воспроизведением
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")
            break

@bot.slash_command(name="shiza", description="Включить зацикленное воспроизведение песен")
async def shiza(ctx):
    embed = discord.Embed(
        title="🎮 Шиза Плеер",
        description="**Выберите трек:**",
        color=discord.Color.purple()
    )
    embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")
    view = ShizaView()
    await ctx.respond(embed=embed, view=view)

@bot.slash_command(name="gpt", description="Сгенерировать текст с помощью GPT.")
async def gpt(ctx, *, prompt: str):
    client = Client()
    models = ["gpt-4o"]  # Список моделей для перебора
    await ctx.respond("Обработка запроса...")  # Уведомляем пользователя о начале обработки

    loop = asyncio.get_event_loop()  # Получаем текущий цикл событий

    for model in models:
        try:
            # Обертка для вызова функции с аргументами
            def create_completion():
                return client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    web_search=False
                )

            # Используем run_in_executor для выполнения синхронного метода в отдельном потоке
            response = await loop.run_in_executor(None, create_completion)
            await ctx.followup.send(response.choices[0].message.content)
            return  # Выход из функции, если запрос успешен
        except Exception as e:
            print(f"Ошибка при использовании модели {model}: {e}")  # Отладочное сообщение

    # Если все модели не сработали, проверяем, существует ли взаимодействие
    try:
        await ctx.followup.send("Все попытки генерации текста завершились неудачей.")
    except Exception as e:
        print(f"Ошибка при отправке сообщения об ошибке: {e}")  # Отладочное сообщение

@bot.slash_command(name="image", description="Генерация изображения по запросу")
async def image(ctx, *, prompt: str):
    await ctx.defer()  # Defer the response since image generation might take time
    
    try:
        client = Client()
        response = await client.images.async_generate(
            model="flux",
            prompt=prompt,
            response_format="url"
        )
        
        if response and hasattr(response, 'data') and len(response.data) > 0:
            image_url = response.data[0].url
            
            # Create embed with the image
            embed = discord.Embed(title="Сгенерированное изображение", description=f"Запрос: {prompt}")
            embed.set_image(url=image_url)
            
            await ctx.followup.send(embed=embed)
        else:
            await ctx.followup.send("Не удалось сгенерировать изображение. Попробуйте другой запрос.")
            
    except Exception as e:
        await ctx.followup.send(f"Произошла ошибка при генерации изображения: {str(e)}")

@bot.slash_command(name="clear", description="Очистить чат от сообщений бота и команд.")
async def clear(ctx):
    def is_bot_or_command_message(message):
        return message.author == bot.user or message.content.startswith('/')

    deleted = await ctx.channel.purge(limit=100, check=is_bot_or_command_message)
    await ctx.respond(f"Удалено {len(deleted)} сообщений.", ephemeral=True)

@bot.slash_command(name="clearall", description="Очистить чат от всех сообщений.")
async def clearall(ctx):
    if ctx.author.id != ADMIN_USER_ID:  # Проверка на права
        await ctx.respond("У вас нет прав на выполнение этой команды.", ephemeral=True)
        return

    deleted = await ctx.channel.purge(limit=None)  # Удаляем все сообщения
    await ctx.respond(f"Удалено {len(deleted)} сообщений.", ephemeral=True)

# Запуск бота
bot.run('')