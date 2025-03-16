import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio, ButtonStyle, PCMVolumeTransformer
import asyncio
import random
import datetime
from g4f.client import Client
import sys
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Добавляем интент для отслеживания участников
intents.guilds = True   # Добавляем интент для отслеживания серверов

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

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id != bot.user.id:  # Проверяем, что канал удалил не сам бот
            try:
                member = await channel.guild.fetch_member(entry.user.id)
                if member:
                    await member.kick(reason="ДАУН")
                    # Отправляем сообщение в первый доступный текстовый канал
                    for ch in channel.guild.text_channels:
                        try:
                            await ch.send(f"Пользователь {entry.user.name} был трахнут за удаление канала {channel.name}")
                            break
                        except:
                            continue
            except discord.Forbidden:
                # Если у бота недостаточно прав для кика
                for ch in channel.guild.text_channels:
                    try:
                        await ch.send(f"Не удалось кикнуть пользователя {entry.user.name} за удаление канала. Недостаточно прав.")
                        break
                    except:
                        continue

@bot.event
async def on_member_remove(member):
    async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
        if entry.user.id != bot.user.id and entry.user.id != ADMIN_USER_ID:  # Проверяем, что кик выполнил не бот и не админ
            try:
                kicker = await member.guild.fetch_member(entry.user.id)
                if kicker:
                    reason = "Кикнул другого пользователя"
                    await kicker.kick(reason=reason)
                    # Отправляем сообщение в первый доступный текстовый канал
                    for channel in member.guild.text_channels:
                        try:
                            await channel.send(f"{kicker.name} был кикнут за кик {member.name}")
                            break
                        except:
                            continue
            except discord.Forbidden:
                # Если у бота недостаточно прав для кика
                for channel in member.guild.text_channels:
                    try:
                        await channel.send(f"Не удалось кикнуть пользователя {entry.user.name} за кик {member.name}. Недостаточно прав.")
                        break
                    except:
                        continue

@bot.event
async def on_member_update(before, after):
    # Проверяем, изменились ли роли
    if before.roles != after.roles:
        # Проверяем журнал аудита на предмет изменения ролей
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            # Проверяем, что изменение ролей произошло только что
            if entry.target.id == before.id:
                # Проверяем, что роли были удалены (а не добавлены)
                removed_roles = set(before.roles) - set(after.roles)
                if removed_roles and entry.user.id != bot.user.id and entry.user.id != ADMIN_USER_ID:
                    try:
                        # Получаем пользователя, который забрал роли
                        remover = await after.guild.fetch_member(entry.user.id)
                        if remover:
                            # Сохраняем список ролей пользователя
                            roles_to_remove = [role for role in remover.roles if role.name != "@everyone"]
                            # Забираем все роли
                            await remover.remove_roles(*roles_to_remove, reason="Забрал роли у другого пользователя")
                            
                            # Отправляем сообщение в первый доступный текстовый канал
                            for channel in after.guild.text_channels:
                                try:
                                    await channel.send(f"У {remover.mention} были забраны роли")
                                    break
                                except:
                                    continue
                    except discord.Forbidden:
                        # Если у бота недостаточно прав
                        for channel in after.guild.text_channels:
                            try:
                                await channel.send(f"Не удалось забрать роли у пользователя {entry.user.name}. Недостаточно прав.")
                                break
                            except:
                                continue

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
        # Устанавливаем timeout=None, чтобы кнопки были активны всегда
        super().__init__(timeout=None)
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
        
        try:
            station = interaction.custom_id.replace("radio_", "")
            url = self.radio_urls[station]

            if not interaction.user.voice:
                await interaction.response.send_message("Вы должны быть в голосовом канале!", ephemeral=True)
                return

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

            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except discord.NotFound:
                # Если взаимодействие истекло, отправляем новое сообщение
                await interaction.channel.send(embed=embed, view=self)
            except Exception as e:
                # Для других ошибок пытаемся отправить новое сообщение
                try:
                    await interaction.channel.send(embed=embed, view=self)
                except:
                    pass

        except Exception as e:
            try:
                await interaction.response.send_message(f"Ошибка воспроизведения: {str(e)}", ephemeral=True)
            except discord.NotFound:
                try:
                    await interaction.channel.send(f"Ошибка воспроизведения: {str(e)}")
                except:
                    pass

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
        
        try:
            if voice_client and voice_client.is_connected():
                voice_client.stop()
                await voice_client.disconnect()
                current_radio = None
                self.is_paused = False
                
                for child in self.children:
                    if child.custom_id == "radio_pause":
                        child.label = "⏸️ Пауза"
                
                embed = discord.Embed(
                    title="🎵 Радио Плеер",
                    description="**Статус:** Остановлено",
                    color=discord.Color.red()
                )
                embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
                
                try:
                    await interaction.response.edit_message(embed=embed, view=self)
                except discord.NotFound:
                    await interaction.channel.send(embed=embed, view=self)
            else:
                await interaction.response.send_message("Радио уже остановлено!", ephemeral=True)
        except Exception as e:
            try:
                await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)
            except discord.NotFound:
                try:
                    await interaction.channel.send(f"Ошибка: {str(e)}")
                except:
                    pass

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
            title="🎪 Шиза Плеер",
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
                title="🎪 Шиза Плеер",
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
        title="🎪 Шиза Плеер",
        description="**Выберите трек:**",
        color=discord.Color.purple()
    )
    embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")
    view = ShizaView()
    await ctx.respond(embed=embed, view=view)

@bot.slash_command(name="gpt", description="Сгенерировать текст с помощью GPT.")
async def gpt(ctx, *, prompt: str):
    client = Client()
    models = ["gpt-4o-mini"]  # Список моделей для перебора
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
            
            # Проверяем структуру ответа и получаем содержимое
            if hasattr(response.choices[0], 'message'):
                content = response.choices[0].message.content
            else:
                content = response.choices[0].content
                
            await ctx.followup.send(content)
            return  # Выход из функции, если запрос успешен
        except Exception as e:
            print(f"Ошибка при использовании модели {model}: {e}")  # Отладочное сообщение

    # Если все модели не сработали, отправляем сообщение об ошибке
    await ctx.followup.send("Извините, произошла ошибка при обработке запроса. Попробуйте позже.")

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

@bot.slash_command(name="restart", description="Перезапустить бота (только для администратора)")
async def restart(ctx):
    if ctx.author.id != ADMIN_USER_ID:
        await ctx.respond("У вас нет прав на выполнение этой команды.", ephemeral=True)
        return

    await ctx.respond("Перезапуск бота...", ephemeral=True)
    
    try:
        # Отключаемся от всех голосовых каналов перед перезапуском
        for vc in bot.voice_clients:
            await vc.disconnect()
        
        # Останавливаем задачи
        clear_channel_daily.stop()
        
        # Перезапускаем бота
        python = sys.executable
        os.execl(python, python, *sys.argv)
        
    except Exception as e:
        await ctx.respond(f"Ошибка при перезапуске: {str(e)}", ephemeral=True)

@bot.slash_command(name="spam", description="Удалить сообщения с упоминаниями.")
async def spam(ctx, count: int = None):
    try:
        # Сразу отвечаем на взаимодействие
        await ctx.respond("Удаление сообщений...", ephemeral=True)

        def is_mention(message):
            # Проверяем наличие упоминаний пользователей, ролей или everyone/here
            has_mentions = len(message.mentions) > 0 or len(message.role_mentions) > 0
            has_everyone = message.mention_everyone
            return has_mentions or has_everyone

        if count is None:
            # Удаляем все сообщения с упоминаниями
            deleted = await ctx.channel.purge(limit=1000, check=is_mention)
            try:
                await ctx.edit(content=f"Удалено {len(deleted)} сообщений с упоминаниями.")
            except:
                pass
            return

        if count < 1:
            try:
                await ctx.edit(content="Количество должно быть больше 0.")
            except:
                pass
            return

        # Удаляем указанное количество сообщений с упоминаниями
        deleted_count = 0
        batch_size = 100  # Размер пакета сообщений для проверки за раз
        
        while deleted_count < count:
            # Получаем следующую партию сообщений
            messages_to_delete = []
            async for message in ctx.channel.history(limit=batch_size):
                if is_mention(message):
                    messages_to_delete.append(message)
                    deleted_count += 1
                    if deleted_count >= count:
                        break
            
            if not messages_to_delete:
                # Если больше нет сообщений с упоминаниями
                try:
                    await ctx.edit(content=f"Найдено только {deleted_count} сообщений с упоминаниями.")
                except:
                    pass
                break
                
            # Удаляем найденные сообщения
            if len(messages_to_delete) > 1:
                await ctx.channel.delete_messages(messages_to_delete)
            elif messages_to_delete:
                await messages_to_delete[0].delete()

        # Отправляем финальное сообщение только если удалили все запрошенные сообщения
        if deleted_count == count:
            try:
                await ctx.edit(content=f"Удалено {deleted_count} сообщений с упоминаниями.")
            except:
                pass

    except discord.Forbidden:
        try:
            await ctx.edit(content="У меня нет прав на удаление сообщений.")
        except:
            pass
    except Exception as e:
        try:
            await ctx.edit(content=f"Произошла ошибка: {str(e)}")
        except:
            pass

# Запуск бота
bot.run('')
