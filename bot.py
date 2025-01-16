import discord
from discord.ext import commands
from discord import FFmpegPCMAudio, ButtonStyle, PCMVolumeTransformer
from discord.ui import Button, View
import random
import os
import asyncio

TOKEN = ''

# Создаем бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Словарь с радиостанциями
RADIO_STATIONS = {
    'геленджик': 'https://serv39.vintera.tv/radio_gel/radio_stream/icecast.audio',
    'кавказ': 'http://radio.alania.net:8000/kvk',
    'аниме': 'https://pool.anison.fm:9000/AniSonFM(320)?nocache=0.9834540412142996',
    'чил': 'http://node-33.zeno.fm/0r0xa792kwzuv?rj-ttl=5&rj-tok=AAABfMtdjJ4AtC1pGWo1_ohFMw',
    'lofi': 'http://stream.zeno.fm/f3wvbbqmdg8uv',
    'кубань': 'http://stream.pervoe.fm:8000',
    'jazz ': 'http://nashe1.hostingradio.ru/jazz-128.mp3'
}

class RadioButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        for station in RADIO_STATIONS.keys():
            self.add_item(RadioButton(station))
        self.add_item(PauseButton())
        self.add_item(LeaveButton())

class RadioButton(Button):
    def __init__(self, station):
        super().__init__(label=station, style=ButtonStyle.primary)
        self.station = station
    

    async def callback(self, interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.user.voice:
                await interaction.followup.send("Вы должны находиться в голосовом канале!", ephemeral=True)
                return

            voice_client = interaction.guild.voice_client
            
            # Проверяем состояние подключения
            try:
                if voice_client and not voice_client.is_connected():
                    await voice_client.disconnect()
                    voice_client = None
            except:
                voice_client = None

            # Создаем новое подключение если нужно
            if voice_client is None:
                try:
                    voice_client = await interaction.user.voice.channel.connect()
                except Exception as e:
                    await interaction.followup.send("Ошибка подключения к каналу. Попробуйте еще раз.", ephemeral=True)
                    return
            elif voice_client.channel != interaction.user.voice.channel:
                await voice_client.move_to(interaction.user.voice.channel)

            # Останавливаем и начинаем воспроизведение
            try:
                if voice_client.is_playing():
                    voice_client.stop()
                voice_client.play(FFmpegPCMAudio(RADIO_STATIONS[self.station]))
            except Exception as e:
                await interaction.followup.send("Ошибка воспроизведения. Попробуйте переподключить бота командой !leave и затем !radio", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"Произошла ошибка: {str(e)}", ephemeral=True)

class PauseButton(Button):
    def __init__(self):
        super().__init__(label="⏯️ Пауза", style=ButtonStyle.secondary)
        
    async def callback(self, interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            voice_client = interaction.guild.voice_client
            
            if not voice_client:
                await interaction.followup.send("Бот не находится в голосовом канале!", ephemeral=True)
                return
                
            if voice_client.is_playing():
                voice_client.pause()
            elif voice_client.is_paused():
                voice_client.resume()
            else:
                await interaction.followup.send("Нечего приостанавливать!", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"Произошла ошибка: {str(e)}", ephemeral=True)

class LeaveButton(Button):
    def __init__(self):
        super().__init__(label="Выход", style=ButtonStyle.danger)
        
    async def callback(self, interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            voice_client = interaction.guild.voice_client
            
            if voice_client:
                await voice_client.disconnect()
            else:
                await interaction.followup.send("Бот не находится в голосовом канале!", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"Произошла ошибка: {str(e)}", ephemeral=True)

class KickRandomButton(Button):
    def __init__(self):
        super().__init__(label="🎲 Исключить случайного", style=ButtonStyle.danger)
        
    async def callback(self, interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.user.voice:
                await interaction.followup.send("Вы должны находиться в голосовом канале!", ephemeral=True)
                return
                
            voice_channel = interaction.user.voice.channel
            members = voice_channel.members
            
            # Исключаем ботов из списка
            real_members = [m for m in members if not m.bot]
            
            if len(real_members) >= 2:
                await interaction.followup.send("В канале недостаточно участников!", ephemeral=True)
                return
                
            # Используем random.choice для выбора случайного участника
            victim = random.choice(real_members)
            
            try:
                await victim.move_to(None)
                await interaction.followup.send(f"🎲 Случайный выбор пал на {victim.display_name}!", ephemeral=False)
            except discord.Forbidden:
                await interaction.followup.send("У меня недостаточно прав для исключения участников!", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"Произошла ошибка: {str(e)}", ephemeral=True)

class PukButton(Button):
    def __init__(self):
        super().__init__(label="💨 Пукать", style=ButtonStyle.primary)
        self.is_playing = False
        
    async def play_random_puk(self, voice_client):
        while self.is_playing:
            try:
                delay = random.randint(60, 120)
                await asyncio.sleep(delay)
                
                if not self.is_playing:
                    break
                
                # Сохраняем URL радио
                radio_url = None
                if voice_client.is_playing():
                    try:
                        # Более надежный способ получения URL
                        args = voice_client.source._process.args
                        for arg in args:
                            if 'http' in str(arg):
                                radio_url = arg
                                break
                        print(f"Сохранен URL радио: {radio_url}")  # Для отладки
                        voice_client.stop()
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"Ошибка сохранения радио: {e}")
                
                # Воспроизводим 5 пуков
                for _ in range(5):
                    if not self.is_playing or not voice_client.is_connected():
                        break
                    
                    try:
                        # Увеличиваем громкость в 3 раза
                        audio_source = PCMVolumeTransformer(FFmpegPCMAudio('puk.mp3'), volume=3.0)
                        voice_client.play(audio_source)
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"Ошибка пука: {e}")
                
                # Возвращаем радио
                if radio_url:
                    try:
                        print(f"Попытка возврата радио: {radio_url}")  # Для отладки
                        await asyncio.sleep(1)
                        if voice_client.is_connected():
                            voice_client.play(FFmpegPCMAudio(radio_url))
                            print("Радио возобновлено")  # Для отладки
                    except Exception as e:
                        print(f"Ошибка возврата радио: {e}")
                        
            except Exception as e:
                print(f"Ошибка в цикле: {e}")
                await asyncio.sleep(1)
                
        print("Цикл воспроизведения пуков завершен")

    async def callback(self, interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.user.voice:
                await interaction.followup.send("Вы должны находиться в голосовом канале!", ephemeral=True)
                return

            voice_client = interaction.guild.voice_client
            
            # Проверяем состояние подключения
            try:
                if voice_client and not voice_client.is_connected():
                    await voice_client.disconnect()
                    voice_client = None
            except:
                voice_client = None

            # Создаем новое подключение если нужно
            if voice_client is None:
                try:
                    voice_client = await interaction.user.voice.channel.connect()
                except Exception as e:
                    await interaction.followup.send("Ошибка подключения к каналу.", ephemeral=True)
                    return
            elif voice_client.channel != interaction.user.voice.channel:
                await voice_client.move_to(interaction.user.voice.channel)

            # Включаем режим случайного воспроизведения
            self.is_playing = True         
            # Запускаем бесконечный цикл случайных пуков
            asyncio.create_task(self.play_random_puk(voice_client))
                
        except Exception as e:
            await interaction.followup.send(f"Произошла ошибка: {str(e)}", ephemeral=True)

class LeaveButtonPuk(Button):
    def __init__(self, puk_button):
        super().__init__(label="Перестать пукать", style=ButtonStyle.danger)
        self.puk_button = puk_button
        
    async def callback(self, interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            voice_client = interaction.guild.voice_client
            
            # Сохраняем URL радио до остановки пуков
            radio_url = None
            if voice_client and voice_client.is_playing():
                try:
                    args = voice_client.source._process.args
                    for arg in args:
                        if 'http' in str(arg):
                            radio_url = arg
                            break
                except Exception as e:
                    print(f"Ошибка сохранения URL радио: {e}")
            
            # Останавливаем случайные пуки
            self.puk_button.is_playing = False
            
            # Останавливаем текущее воспроизведение
            if voice_client and voice_client.is_playing():
                voice_client.stop()
            
            # Ждем немного и восстанавливаем радио
            if radio_url:
                await asyncio.sleep(0.1)
                try:
                    if voice_client and voice_client.is_connected():
                        voice_client.play(FFmpegPCMAudio(radio_url))
                        print(f"Радио восстановлено: {radio_url}")
                except Exception as e:
                    print(f"Ошибка восстановления радио: {e}")
                    
        except Exception as e:
            await interaction.followup.send(f"Произошла ошибка: {str(e)}", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Бот {bot.user} готов к работе!')

@bot.command(help="Присоединиться к голосовому каналу")
async def join(ctx):
    """Присоединиться к голосовому каналу"""
    await ctx.author.voice.channel.connect()

@bot.command(help="Покинуть голосовой канал")
async def leave(ctx):
    """Покинуть голосовой канал"""
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
    else:
        await ctx.send("Бот не находится в голосовом канале!")

@bot.command(help="Поставить на паузу")
async def pause(ctx):
    """Поставить на паузу"""
    voice_client = ctx.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
    else:
        await ctx.send("В данный момент ничего не воспроизводится!")

@bot.command(help="Продолжить воспроизведение")
async def resume(ctx):
    """Продолжить воспроизведение"""
    voice_client = ctx.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send("Воспроизведение не на паузе!")

@bot.command(help="Остановить воспроизведение")
async def stop(ctx):
    """Остановить воспроизведение"""
    voice_client = ctx.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
    else:
        await ctx.send("В данный момент ничего не воспроизводится!")

@bot.command(help="Воспроизвести радио")
async def radio(ctx, station=None):
    """Воспроизвести радио"""
    if station is None:
        view = RadioButtons()
        await ctx.send('Радио 🎵', view=view)
        return

    if station not in RADIO_STATIONS:
        await ctx.send('Такой радиостанции нет в списке!')
        return

    try:
        voice_client = ctx.voice_client
        if voice_client is None:
            voice_client = await ctx.author.voice.channel.connect()
        elif voice_client.channel != ctx.author.voice.channel:
            await voice_client.move_to(ctx.author.voice.channel)

        if voice_client.is_playing():
            voice_client.stop()

        voice_client.play(FFmpegPCMAudio(RADIO_STATIONS[station]))
    except Exception as e:
        await ctx.send(f"Произошла ошибка при воспроизведении: {str(e)}")

@bot.event
async def on_voice_state_update(member, before, after):
    """Обработчик изменений в голосовом канале"""
    if member == bot.user:
        if after.channel is None:  # Бот был отключен
            for guild in bot.guilds:
                voice_client = guild.voice_client
                if voice_client:
                    try:
                        await voice_client.disconnect()
                    except:
                        pass
        elif before.channel != after.channel:  # Бот был перемещен
            voice_client = member.guild.voice_client
            if voice_client and voice_client.is_playing():
                try:
                    # Сохраняем текущий источник
                    current_source = voice_client.source._process.args[-1]
                    voice_client.pause()
                    await asyncio.sleep(0.5)
                    # Восстанавливаем воспроизведение
                    voice_client.play(FFmpegPCMAudio(current_source))
                except Exception as e:
                    print(f"Ошибка восстановления аудио после перемещения: {e}")

@bot.command(help="Показать кнопку для исключения случайного участника")
async def kick(ctx):
    """Показать кнопку для исключения случайного участника"""
    view = View()
    view.add_item(KickRandomButton())
    await ctx.send("Нажмите кнопку, чтобы исключить случайного участника:", view=view)

@bot.command(help="Показать кнопки для пука")
async def puk(ctx):
    """Показать кнопки для пука"""
    puk_button = PukButton()
    view = View()
    view.add_item(puk_button)
    view.add_item(LeaveButtonPuk(puk_button))
    await ctx.send("Случайные пуки:", view=view)

@bot.command(help="Очистить все сообщения бота в канале")
async def clear(ctx):
    """Очистить все сообщения бота в канале"""
    def is_bot_message(message):
        return message.author == bot.user

    deleted = await ctx.channel.purge(limit=100, check=is_bot_message)
    await ctx.send(f"Удалено {len(deleted)} сообщений бота.", delete_after=5)

# Замените 'YOUR_TOKEN' на переменную TOKEN
bot.run(TOKEN)

