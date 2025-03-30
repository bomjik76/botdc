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
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Словари для хранения состояния каждого сервера
server_states = {}
server_voice_clients = {}
server_kick_limits = {}
server_radio_messages = {}

# Переменные для управления воспроизведением звука и радио
is_playing_shiza = False
voice_client = None
current_radio = None
radio_message = None

#Переменные
ADMIN_USER_ID = 480402325786329091
VOICE_CHANNEL_ID = 1334607111694450708
TEXT_CHANNEL_ID = 1334606129015296010

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

# Функция для инициализации состояния сервера
def init_server_state(guild_id):
    if guild_id not in server_states:
        server_states[guild_id] = {
            'is_playing_shiza': False,
            'current_radio': None,
            'volume': 1.0,
            'is_paused': False
        }
    if guild_id not in server_kick_limits:
        server_kick_limits[guild_id] = {}

# Функция для сброса лимитов каждый день
@tasks.loop(hours=24)
async def reset_kick_limits():
    for guild_id in server_kick_limits:
        server_kick_limits[guild_id].clear()

class PenizView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=None)
        self.add_member_buttons(members)

    def add_member_buttons(self, members):
        for member in members:
            if not member.bot:
                kick_button = discord.ui.Button(
                    label=f"Отключить {member.name}",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"kick_{member.id}"
                )
                kick_button.callback = lambda i, m=member: self.kick_callback(i, m)
                self.add_item(kick_button)
                
                mute_button = discord.ui.Button(
                    label=f"🔇 {member.name}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"mute_{member.id}"
                )
                mute_button.callback = lambda i, m=member: self.mute_callback(i, m)
                self.add_item(mute_button)

    async def kick_callback(self, interaction: discord.Interaction, member: discord.Member):
        user_id = interaction.user.id
        if user_id not in server_kick_limits[interaction.guild.id]:
            server_kick_limits[interaction.guild.id][user_id] = 0
        
        if server_kick_limits[interaction.guild.id][user_id] >= 10:
            await interaction.response.send_message("Вы достигли лимита исключений на сегодня (10).", ephemeral=True)
            return

        if not member or not member.voice:
            await interaction.response.send_message("Пользователь не находится в голосовом канале.", ephemeral=True)
            return

        await member.move_to(None)
        server_kick_limits[interaction.guild.id][user_id] += 1
        
        remaining = 10 - server_kick_limits[interaction.guild.id][user_id]
        await interaction.response.send_message(
            f"Пользователь {member.name} был отключен.\nОсталось исключений на сегодня: {remaining}",
            ephemeral=True,
            delete_after=2.0
        )

    async def mute_callback(self, interaction: discord.Interaction, member: discord.Member):
        user_id = interaction.user.id
        if user_id not in server_kick_limits[interaction.guild.id]:
            server_kick_limits[interaction.guild.id][user_id] = 0
        
        if server_kick_limits[interaction.guild.id][user_id] >= 10:
            await interaction.response.send_message("Вы достигли лимита действий на сегодня (10).", ephemeral=True)
            return

        if not member or not member.voice:
            await interaction.response.send_message("Пользователь не находится в голосовом канале.", ephemeral=True)
            return

        try:
            if member.voice.self_mute:
                await member.edit(mute=False)
                status = "включен"
            else:
                await member.edit(mute=True)
                status = "отключен"

            server_kick_limits[interaction.guild.id][user_id] += 1
            remaining = 10 - server_kick_limits[interaction.guild.id][user_id]

            await interaction.response.send_message(
                f"Микрофон пользователя {member.name} был {status}.\nОсталось действий на сегодня: {remaining}",
                ephemeral=True,
                delete_after=2.0
            )
        except discord.Forbidden:
            await interaction.response.send_message("У меня нет прав для управления микрофоном пользователя.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Произошла ошибка: {str(e)}", ephemeral=True)

@bot.tree.command(name="peniz", description="Показать список участников в голосовом канале для управления")
async def peniz(interaction: discord.Interaction):
    voice_members = []
    for channel in interaction.guild.voice_channels:
        voice_members.extend(channel.members)
    
    voice_members = list(dict.fromkeys(voice_members))
    
    if not voice_members:
        await interaction.response.send_message("В голосовых каналах никого нет.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎯 Управление участниками",
        description="Выберите действие для каждого участника:\n🔴 - Отключить от голосового канала\n🔇 - Отключить микрофон\n\nЛимит: 10 отключений в день",
        color=discord.Color.red()
    )
    
    view = PenizView(voice_members)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id != bot.user.id and entry.user.id != ADMIN_USER_ID:
            try:
                member = await channel.guild.fetch_member(entry.user.id)
                if member:
                    await member.kick(reason="ДАУН")
                    for ch in channel.guild.text_channels:
                        try:
                            await ch.send(f"Пользователь {entry.user.name} был трахнут за удаление канала {channel.name}")
                            break
                        except:
                            continue
            except discord.Forbidden:
                for ch in channel.guild.text_channels:
                    try:
                        await ch.send(f"Не удалось кикнуть пользователя {entry.user.name} за удаление канала. Недостаточно прав.")
                        break
                    except:
                        continue

@bot.event
async def on_member_remove(member):
    async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
        if entry.user.id != bot.user.id and entry.user.id != ADMIN_USER_ID:
            try:
                kicker = await member.guild.fetch_member(entry.user.id)
                if kicker:
                    reason = "Кикнул другого пользователя"
                    await kicker.kick(reason=reason)
                    for channel in member.guild.text_channels:
                        try:
                            await channel.send(f"{kicker.name} был кикнут за кик {member.name}")
                            break
                        except:
                            continue
            except discord.Forbidden:
                for channel in member.guild.text_channels:
                    try:
                        await channel.send(f"Не удалось кикнуть пользователя {entry.user.name} за кик {member.name}. Недостаточно прав.")
                        break
                    except:
                        continue

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
            if entry.target.id == before.id:
                removed_roles = set(before.roles) - set(after.roles)
                if removed_roles and entry.user.id != bot.user.id and entry.user.id != ADMIN_USER_ID:
                    try:
                        remover = await after.guild.fetch_member(entry.user.id)
                        if remover:
                            roles_to_remove = [role for role in remover.roles if role.name != "@everyone"]
                            await remover.remove_roles(*roles_to_remove, reason="Забрал роли у другого пользователя")
                            
                            for channel in after.guild.text_channels:
                                try:
                                    await channel.send(f"У {remover.mention} были забраны роли")
                                    break
                                except:
                                    continue
                    except discord.Forbidden:
                        for channel in after.guild.text_channels:
                            try:
                                await channel.send(f"Не удалось забрать роли у пользователя {entry.user.name}. Недостаточно прав.")
                                break
                            except:
                                continue

class KickView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(KickButton())

class KickButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Случайное исключение", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("Вы должны находиться в голосовом канале.", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        members = [member for member in channel.members if not member.bot]

        if len(members) > 1:
            member_to_kick = random.choice(members)
            await member_to_kick.move_to(None)
            await interaction.response.send_message(f"{member_to_kick.name} был исключен из голосового канала.")
        else:
            await interaction.response.send_message("В голосовом канале должно быть минимум 2 участника для исключения.", ephemeral=True)

@bot.tree.command(name="kick", description="Исключить случайного участника из голосового канала.")
async def kick(interaction: discord.Interaction):
    view = KickView()
    await interaction.response.send_message("Нажмите, чтобы исключить случайного участника:", view=view)

class RadioView(discord.ui.View):
    def __init__(self, radio_urls, guild_id):
        super().__init__(timeout=None)
        self.radio_urls = radio_urls
        self.guild_id = guild_id
        init_server_state(guild_id)
        self.add_radio_buttons()
        self.add_control_buttons()

    def add_radio_buttons(self):
        for name in self.radio_urls:
            button = discord.ui.Button(label=name.title(), style=ButtonStyle.primary, custom_id=f"radio_{name}")
            button.callback = lambda i, n=name: self.radio_button_callback(i, n)
            self.add_item(button)

    def add_control_buttons(self):
        stop_button = discord.ui.Button(label="⏹️ Стоп", style=ButtonStyle.danger, custom_id="radio_stop")
        stop_button.callback = self.stop_callback
        self.add_item(stop_button)

        pause_button = discord.ui.Button(label="⏸️ Пауза", style=ButtonStyle.secondary, custom_id="radio_pause")
        pause_button.callback = self.pause_callback
        self.add_item(pause_button)

        volume_down = discord.ui.Button(label="🔉", style=ButtonStyle.secondary, custom_id="volume_down")
        volume_down.callback = self.volume_down_callback
        self.add_item(volume_down)

        volume_up = discord.ui.Button(label="🔊", style=ButtonStyle.secondary, custom_id="volume_up")
        volume_up.callback = self.volume_up_callback
        self.add_item(volume_up)

    async def radio_button_callback(self, interaction: discord.Interaction, station: str):
        try:
            url = self.radio_urls[station]

            if not interaction.user.voice:
                await interaction.response.send_message("Вы должны быть в голосовом канале!", ephemeral=True)
                return

            voice_client = server_voice_clients.get(self.guild_id)
            if voice_client and voice_client.is_connected():
                if voice_client.channel != interaction.user.voice.channel:
                    await voice_client.move_to(interaction.user.voice.channel)
                voice_client.stop()
            else:
                voice_client = await interaction.user.voice.channel.connect()
                server_voice_clients[self.guild_id] = voice_client

            server_states[self.guild_id]['current_radio'] = station
            server_states[self.guild_id]['is_paused'] = False
            audio_source = PCMVolumeTransformer(FFmpegPCMAudio(url), volume=server_states[self.guild_id]['volume'])
            voice_client.play(audio_source)

            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {station.title()}\n**Громкость:** {int(server_states[self.guild_id]['volume'] * 100)}%\n**Статус:** Играет",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")

            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except discord.NotFound:
                await interaction.channel.send(embed=embed, view=self)
            except Exception as e:
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
        voice_client = server_voice_clients.get(self.guild_id)
        
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message("Радио не играет!", ephemeral=True)
            return
        
        try:
            if voice_client.is_playing():
                voice_client.pause()
                server_states[self.guild_id]['is_paused'] = True
                status = "На паузе"
                button_label = "▶️ Продолжить"
            elif voice_client.is_paused():
                voice_client.resume()
                server_states[self.guild_id]['is_paused'] = False
                status = "Играет"
                button_label = "⏸️ Пауза"
            else:
                await interaction.response.send_message("Радио не играет!", ephemeral=True)
                return

            for child in self.children:
                if child.custom_id == "radio_pause":
                    child.label = button_label

            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {server_states[self.guild_id]['current_radio'].title() if server_states[self.guild_id]['current_radio'] else 'Ничего'}\n**Громкость:** {int(server_states[self.guild_id]['volume'] * 100)}%\n**Статус:** {status}",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
            
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)

    async def stop_callback(self, interaction: discord.Interaction):
        voice_client = server_voice_clients.get(self.guild_id)
        
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message("Радио уже остановлено!", ephemeral=True)
            return
            
        try:
            voice_client.stop()
            await voice_client.disconnect()
            server_voice_clients.pop(self.guild_id, None)
            server_states[self.guild_id]['current_radio'] = None
            server_states[self.guild_id]['is_paused'] = False
            
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
                
        except Exception as e:
            try:
                await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)
            except discord.NotFound:
                try:
                    await interaction.channel.send(f"Ошибка: {str(e)}")
                except:
                    pass

    async def volume_up_callback(self, interaction: discord.Interaction):
        voice_client = server_voice_clients.get(self.guild_id)
        
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            server_states[self.guild_id]['volume'] = min(2.0, server_states[self.guild_id]['volume'] + 0.1)
            if hasattr(voice_client.source, 'volume'):
                voice_client.source.volume = server_states[self.guild_id]['volume']
            
            status = "На паузе" if server_states[self.guild_id]['is_paused'] else "Играет"
            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {server_states[self.guild_id]['current_radio'].title() if server_states[self.guild_id]['current_radio'] else 'Ничего'}\n**Громкость:** {int(server_states[self.guild_id]['volume'] * 100)}%\n**Статус:** {status}",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Сначала включите радио!", ephemeral=True)

    async def volume_down_callback(self, interaction: discord.Interaction):
        voice_client = server_voice_clients.get(self.guild_id)
        
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            server_states[self.guild_id]['volume'] = max(0.0, server_states[self.guild_id]['volume'] - 0.1)
            if hasattr(voice_client.source, 'volume'):
                voice_client.source.volume = server_states[self.guild_id]['volume']
            
            status = "На паузе" if server_states[self.guild_id]['is_paused'] else "Играет"
            embed = discord.Embed(
                title="🎵 Радио Плеер",
                description=f"**Сейчас играет:** {server_states[self.guild_id]['current_radio'].title() if server_states[self.guild_id]['current_radio'] else 'Ничего'}\n**Громкость:** {int(server_states[self.guild_id]['volume'] * 100)}%\n**Статус:** {status}",
                color=discord.Color.blue()
            )
            embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Сначала включите радио!", ephemeral=True)

@bot.tree.command(name="radio", description="Включить радио")
async def radio(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎵 Радио Плеер",
        description="**Выберите радиостанцию:**",
        color=discord.Color.blue()
    )
    embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWlmbzR1M21zNTh1N3UydXQ2bjBveHIzanQ3MThtbGoxeG8ydmwxZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/9zExs2Q2h1EHfE4P6G/giphy.gif")
    view = RadioView(radio_urls, interaction.guild.id)
    await interaction.response.send_message(embed=embed, view=view)

class ShizaView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        init_server_state(guild_id)
        self.add_item(ShizaButton("🎵 Литвин", "/home/bot/litvin.mp3", guild_id))
        self.add_item(ShizaButton("💫 Сигма", "/home/bot/sigma.mp3", guild_id))
        self.add_item(StopShizaButton(guild_id))

class ShizaButton(discord.ui.Button):
    def __init__(self, label: str, file_path: str, guild_id: int):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.file_path = file_path
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("Вы должны находиться в голосовом канале!", ephemeral=True)
            return

        voice_client = server_voice_clients.get(self.guild_id)

        if voice_client is None:
            voice_client = await interaction.user.voice.channel.connect()
            server_voice_clients[self.guild_id] = voice_client
        elif voice_client.channel != interaction.user.voice.channel:
            await voice_client.move_to(interaction.user.voice.channel)

        if voice_client.is_playing():
            voice_client.stop()

        server_states[self.guild_id]['is_playing_shiza'] = True
        asyncio.create_task(play_shiza_loop(voice_client, self.file_path, self.guild_id))

        embed = discord.Embed(
            title="🎪 Шиза Плеер",
            description=f"**Сейчас играет:** {self.label}\n**Статус:** Играет",
            color=discord.Color.purple()
        )
        embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")

        message = interaction.message
        await message.edit(embed=embed, view=self.view)

class StopShizaButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="⏹️ Остановить", style=discord.ButtonStyle.danger)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        voice_client = server_voice_clients.get(self.guild_id)

        if voice_client and voice_client.is_connected():
            server_states[self.guild_id]['is_playing_shiza'] = False
            voice_client.stop()
            await voice_client.disconnect()
            server_voice_clients.pop(self.guild_id, None)
            
            embed = discord.Embed(
                title="🎪 Шиза Плеер",
                description="**Статус:** Остановлено",
                color=discord.Color.red()
            )
            embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")
            
            message = interaction.message
            await message.edit(embed=embed, view=self.view)
        else:
            await interaction.followup.send("Сейчас ничего не воспроизводится!", ephemeral=True)

async def play_shiza_loop(voice_client, file_path, guild_id):
    while server_states[guild_id]['is_playing_shiza'] and voice_client and voice_client.is_connected():
        try:
            audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(file_path), volume=1.0)
            voice_client.play(audio_source)
            
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
                if not server_states[guild_id]['is_playing_shiza']:
                    voice_client.stop()
                    return
                    
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")
            break

@bot.tree.command(name="shiza", description="Включить зацикленное воспроизведение песен")
async def shiza(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎪 Шиза Плеер",
        description="**Выберите трек:**",
        color=discord.Color.purple()
    )
    embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")
    view = ShizaView(interaction.guild.id)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="gpt", description="Сгенерировать текст с помощью GPT.")
async def gpt(interaction: discord.Interaction, prompt: str):
    client = Client()
    models = ["gpt-4o"]
    await interaction.response.defer()

    loop = asyncio.get_event_loop()

    for model in models:
        try:
            def create_completion():
                return client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    web_search=False
                )

            response = await loop.run_in_executor(None, create_completion)
            
            if hasattr(response.choices[0], 'message'):
                content = response.choices[0].message.content
            else:
                content = response.choices[0].content
                
            await interaction.followup.send(content)
            return
        except Exception as e:
            print(f"Ошибка при использовании модели {model}: {e}")

    await interaction.followup.send("Извините, произошла ошибка при обработке запроса. Попробуйте позже.")

@bot.tree.command(name="image", description="Генерация изображения по запросу")
async def image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    
    try:
        client = Client()
        response = await client.images.async_generate(
            model="flux",
            prompt=prompt,
            response_format="url"
        )
        
        if response and hasattr(response, 'data') and len(response.data) > 0:
            image_url = response.data[0].url
            
            embed = discord.Embed(title="Сгенерированное изображение", description=f"Запрос: {prompt}")
            embed.set_image(url=image_url)
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Не удалось сгенерировать изображение. Попробуйте другой запрос.")
            
    except Exception as e:
        await interaction.followup.send(f"Произошла ошибка при генерации изображения: {str(e)}")

@bot.tree.command(name="clear", description="Очистить чат от сообщений бота и команд.")
async def clear(interaction: discord.Interaction):
    def is_bot_or_command_message(message):
        return message.author == bot.user or message.content.startswith('/')

    deleted = await interaction.channel.purge(limit=100, check=is_bot_or_command_message)
    await interaction.response.send_message(f"Удалено {len(deleted)} сообщений.", ephemeral=True)

@bot.tree.command(name="clearall", description="Очистить чат от всех сообщений.")
async def clearall(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_USER_ID:
        await interaction.response.send_message("У вас нет прав на выполнение этой команды.", ephemeral=True)
        return

    deleted = await interaction.channel.purge(limit=None)
    await interaction.response.send_message(f"Удалено {len(deleted)} сообщений.", ephemeral=True)

@bot.tree.command(name="restart", description="Перезапустить бота (только для администратора)")
async def restart(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_USER_ID:
        await interaction.response.send_message("У вас нет прав на выполнение этой команды.", ephemeral=True)
        return

    await interaction.response.send_message("Перезапуск бота...", ephemeral=True)
    
    try:
        for guild_id, voice_client in server_voice_clients.items():
            try:
                if voice_client and voice_client.is_connected():
                    await voice_client.disconnect()
            except:
                continue
        
        server_states.clear()
        server_voice_clients.clear()
        server_kick_limits.clear()
        server_radio_messages.clear()
        
        reset_kick_limits.stop()
        
        python = sys.executable
        os.execl(python, python, *sys.argv)
        
    except Exception as e:
        await interaction.followup.send(f"Ошибка при перезапуске: {str(e)}", ephemeral=True)

@bot.tree.command(name="spam", description="Удалить сообщения с упоминаниями.")
async def spam(interaction: discord.Interaction, count: int = None):
    try:
        await interaction.response.defer(ephemeral=True)

        def is_mention(message):
            has_mentions = len(message.mentions) > 0 or len(message.role_mentions) > 0
            has_everyone = message.mention_everyone
            return has_mentions or has_everyone

        if count is None:
            deleted = await interaction.channel.purge(limit=1000, check=is_mention)
            try:
                await interaction.followup.send(f"Удалено {len(deleted)} сообщений с упоминаниями.")
            except:
                pass
            return

        if count < 1:
            try:
                await interaction.followup.send("Количество должно быть больше 0.")
            except:
                pass
            return

        deleted_count = 0
        batch_size = 100
        
        while deleted_count < count:
            messages_to_delete = []
            async for message in interaction.channel.history(limit=batch_size):
                if is_mention(message):
                    messages_to_delete.append(message)
                    deleted_count += 1
                    if deleted_count >= count:
                        break
            
            if not messages_to_delete:
                try:
                    await interaction.followup.send(f"Найдено только {deleted_count} сообщений с упоминаниями.")
                except:
                    pass
                break
                
            if len(messages_to_delete) > 1:
                await interaction.channel.delete_messages(messages_to_delete)
            elif messages_to_delete:
                await messages_to_delete[0].delete()

        if deleted_count == count:
            try:
                await interaction.followup.send(f"Удалено {deleted_count} сообщений с упоминаниями.")
            except:
                pass

    except discord.Forbidden:
        try:
            await interaction.followup.send("У меня нет прав на удаление сообщений.")
        except:
            pass
    except Exception as e:
        try:
            await interaction.followup.send(f"Произошла ошибка: {str(e)}")
        except:
            pass

@bot.tree.command(name="down", description="Удалить все каналы сервера, кроме защищенных")
async def down(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_USER_ID:
        await interaction.response.send_message("У вас нет прав на выполнение этой команды.", ephemeral=True)
        return

    protected_channels = [1343943218601005167, 1343943252856012843, 1351109433622659092]
    deleted_count = 0
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        for channel in interaction.guild.channels:
            if channel.id not in protected_channels:
                try:
                    await channel.delete()
                    deleted_count += 1
                except discord.Forbidden:
                    continue
                except discord.HTTPException:
                    continue
        
        await interaction.followup.send(f"Удалено {deleted_count} каналов.")
    except Exception as e:
        await interaction.followup.send(f"Произошла ошибка при удалении каналов: {str(e)}")

@bot.event
async def on_ready():
    print(f'Бот {bot.user} готов к работе!')
    reset_kick_limits.start()
    
    for guild in bot.guilds:
        init_server_state(guild.id)

@bot.event
async def on_guild_join(guild):
    init_server_state(guild.id)
    print(f'Бот присоединился к серверу: {guild.name}')

@bot.event
async def on_guild_remove(guild):
    server_states.pop(guild.id, None)
    server_voice_clients.pop(guild.id, None)
    server_kick_limits.pop(guild.id, None)
    server_radio_messages.pop(guild.id, None)
    print(f'Бот покинул сервер: {guild.name}')

# Запуск бота
bot.run('')
