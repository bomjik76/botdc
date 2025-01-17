import discord
from discord.ext import commands
from discord import FFmpegPCMAudio, ButtonStyle, PCMVolumeTransformer
import asyncio
import random

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Список звуковых файлов для воспроизведения
sound_files = ["puk.mp3"]

# Переменные для управления воспроизведением звука и радио
is_playing_puk = False
voice_client = None
current_radio = None  # Добавляем переменную для хранения текущей радиостанции

# Добавьте переменную для хранения сообщения
radio_message = None

# Функция для случайного воспроизведения звука
async def play_random_puk(voice_client):
    global is_playing_puk, current_radio
    while is_playing_puk:
        try:
            delay = random.randint(60, 120)
            await asyncio.sleep(delay)

            if not is_playing_puk:
                break

            # Сохраняем URL радио
            radio_url = None
            if voice_client.is_playing():
                try:
                    args = voice_client.source._process.args
                    for arg in args:
                        if 'http' in str(arg):
                            radio_url = arg
                            break
                    voice_client.stop()
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Ошибка сохранения радио: {e}")

            # Воспроизводим 5 пуков
            for _ in range(5):
                if not is_playing_puk or not voice_client.is_connected():
                    break

                try:
                    audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio('puk.mp3'), volume=3.0)
                    voice_client.play(audio_source)
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Ошибка пука: {e}")

            # Возвращаем радио
            if radio_url:
                try:
                    await asyncio.sleep(1)
                    if voice_client.is_connected():
                        voice_client.play(discord.FFmpegPCMAudio(radio_url))
                except Exception as e:
                    print(f"Ошибка возврата радио: {e}")

        except Exception as e:
            print(f"Ошибка в цикле: {e}")
            await asyncio.sleep(1)

    print("Цикл воспроизведения пуков завершен")

# Команда /puk
class PukView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.puk_button = PukButton()
        self.add_item(self.puk_button)
        self.add_item(LeaveButtonPuk(self.puk_button))

class PukButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="💨 Пукать", style=discord.ButtonStyle.primary)
        self.is_playing = False

    async def callback(self, interaction: discord.Interaction):
        global is_playing_puk, voice_client
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.voice:
            await interaction.followup.send("Вы должны находиться в голосовом канале!", ephemeral=True)
            return

        voice_client = interaction.guild.voice_client

        if voice_client is None or not voice_client.is_connected():
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send("Ошибка подключения к каналу.", ephemeral=True)
                return
        elif voice_client.channel != interaction.user.voice.channel:
            await voice_client.move_to(interaction.user.voice.channel)

        is_playing_puk = True
        asyncio.create_task(play_random_puk(voice_client))

class LeaveButtonPuk(discord.ui.Button):
    def __init__(self, puk_button):
        super().__init__(label="Перестать пукать", style=discord.ButtonStyle.danger)
        self.puk_button = puk_button

    async def callback(self, interaction: discord.Interaction):
        global is_playing_puk, voice_client
        await interaction.response.defer(ephemeral=True)

        is_playing_puk = False
        if voice_client and voice_client.is_playing():
            voice_client.stop()

        await interaction.followup.send("Пуки остановлены.", ephemeral=True)

@bot.slash_command(name="puk", description="Запустить случайные пуки в голосовом канале.")
async def puk(ctx):
    view = PukView()
    await ctx.respond("Случайные пуки:", view=view)

# Команда /kick
class KickView(discord.ui.View):
    @discord.ui.button(label="Случайное исключение", style=discord.ButtonStyle.danger)
    async def random_kick(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("Вы должны находиться в голосовом канале.", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        members = [member for member in channel.members if not member.bot]

        # Проверяем, что в канале минимум 2 участника (включая того, кто нажимает кнопку)
        if len(members) < 2:
            await interaction.response.send_message("В голосовом канале должно быть минимум 2 участника для исключения.", ephemeral=True)
            return

        member_to_kick = random.choice(members)
        await member_to_kick.move_to(None)
        await interaction.response.send_message(f"{member_to_kick.name} был исключен из голосового канала.")

@bot.slash_command(name="kick", description="Исключить случайного участника из голосового канала.")
async def kick(ctx):
    view = KickView()
    await ctx.respond("Нажмите, чтобы исключить случайного участника:", view=view)

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

class RadioView(discord.ui.View):
    def __init__(self, radio_urls):
        super().__init__()
        self.radio_urls = radio_urls
        self.add_radio_buttons()

    def add_radio_buttons(self):
        for name in self.radio_urls:
            button = discord.ui.Button(label=name, style=discord.ButtonStyle.primary)
            button.callback = lambda i, n=name: self.play_radio(i, n)
            self.add_item(button)

        pause_resume_button = discord.ui.Button(label="Пауза/Возобновить", style=discord.ButtonStyle.secondary)
        pause_resume_button.callback = self.pause_resume
        self.add_item(pause_resume_button)

        leave_channel_button = discord.ui.Button(label="Покинуть канал", style=discord.ButtonStyle.red)
        leave_channel_button.callback = self.leave_channel
        self.add_item(leave_channel_button)

    async def play_radio(self, interaction: discord.Interaction, radio_name: str):
        global voice_client
        await interaction.response.defer()  # Отложить ответ
        if interaction.user.voice and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
            if not voice_client or not voice_client.is_connected():
                voice_client = await channel.connect()
            
            source = discord.FFmpegPCMAudio(self.radio_urls[radio_name])
            if voice_client.is_playing():
                voice_client.stop()  # Останавливаем текущий поток перед переключением
            voice_client.play(source)
            await interaction.response.send_message(content="Радиостанция переключена.")  # Отправляем подтверждение
        else:
            await interaction.response.send_message("Вы должны находиться в голосовом канале.")

    async def pause_resume(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Отложить ответ
        if voice_client and voice_client.is_playing():
            voice_client.pause()
        elif voice_client and voice_client.is_paused():
            voice_client.resume()
        else:
            await interaction.followup.send("В данный момент ничего не воспроизводится.", ephemeral=True)

    async def leave_channel(self, interaction: discord.Interaction):
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
        else:
            await interaction.response.send_message("Бот не подключен к голосовому каналу.")

async def update_radio_buttons(ctx):
    global radio_message
    while True:
        await asyncio.sleep(300)  # Обновляем каждые 5 минут
        view = RadioView(radio_urls)
        if radio_message:
            await radio_message.edit(content="Обновление кнопок радио:", view=view)
        else:
            radio_message = await ctx.send("Обновление кнопок радио:", view=view)

@bot.slash_command(name="radio", description="Выбрать радиостанцию для воспроизведения в голосовом канале.")
async def radio(ctx):
    global radio_message
    view = RadioView(radio_urls)
    radio_message = await ctx.respond("Выберите радиостанцию:", view=view)
    bot.loop.create_task(update_radio_buttons(ctx))

@bot.slash_command(name="refresh_radio", description="Обновить список радиостанций.")
async def refresh_radio(ctx):
    view = RadioView(radio_urls)
    await ctx.respond("Выберите радиостанцию:", view=view)

@bot.slash_command(name="clear", description="Очистить чат от сообщений бота и команд.")
async def clear(ctx):
    def is_bot_or_command_message(message):
        return message.author == bot.user or message.content.startswith('/')

    deleted = await ctx.channel.purge(limit=100, check=is_bot_or_command_message)
    await ctx.respond(f"Удалено {len(deleted)} сообщений.", ephemeral=True)

# Запуск бота
bot.run('')