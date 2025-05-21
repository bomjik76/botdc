import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio, ButtonStyle, PCMVolumeTransformer
import asyncio
import random
import datetime
from g4f.client import Client
import sys
import os
import yt_dlp
from collections import deque
import re

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Словари для хранения состояния каждого сервера
server_states = {}
server_voice_clients = {}
server_radio_messages = {}

# Словарь для отслеживания спама с @ упоминаниями
mention_spam_tracker = {}

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
    'ретрогеленджик': 'http://control.craftradio.ru:8000/37_1e7c47df',
    'кантри': 'https://stream.regenbogen2.de/country/mp3-128/radiobrowser',
    'аниме': 'https://pool.anison.fm:9000/AniSonFM(320)?nocache=0.9834540412142996',
    'чил': 'http://node-33.zeno.fm/0r0xa792kwzuv?rj-ttl=5&rj-tok=AAABfMtdjJ4AtC1pGWo1_ohFMw',
    'lofi': 'http://stream.zeno.fm/f3wvbbqmdg8uv',
    'инди': 'http://server-23.stream-server.nl:8438/;listen.pls_',
    'панк рок': 'https://s1-webradio.rockantenne.de/punkrock/stream/mp3',
    'jazz ': 'http://nashe1.hostingradio.ru/jazz-128.mp3'
}

# Music player class to handle music playback
class MusicPlayer:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = deque()
        self.current_track = None
        self.voice_client = None
        self.is_playing = False
        self.volume = 1.0
        self.max_queue_size = 50  # Maximum number of tracks in queue
        self.max_duration = 7200  # Maximum duration in seconds (2 hours)
        self.player_message = None
        self.view = None
        self.loop = False  # Loop state (all queue)
        self.loop_current = False  # Loop current track only
        
        # Configure yt-dlp options with optimized settings for both YouTube and SoundCloud
        self.ytdl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # For playlist support
            'noplaylist': False,   # Allow playlists
            'extract_audio': True,  # Extract audio for SoundCloud
            'audio_quality': 0,    # Best audio quality
            'audio_format': 'mp3', # Preferred audio format
            'prefer_ffmpeg': True, # Prefer ffmpeg for better compatibility
            'socket_timeout': 30,  # Increase timeout for better reliability
            'retries': 10,         # Number of retries for failed downloads
            'fragment_retries': 10, # Number of retries for failed fragments
            'skip_download': True, # Skip downloading, only extract info
            'nocheckcertificate': True,  # Skip certificate validation
            'ignoreerrors': True,  # Ignore errors and continue
            'no_color': True,      # Disable color output
            'geo_bypass': True,    # Bypass geographic restrictions
            'geo_verification_proxy': None,  # Disable geo verification proxy
        }
        
    async def add_to_queue(self, url, user):
        """Add a track or playlist to the queue"""
        try:
            with yt_dlp.YoutubeDL(self.ytdl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Handle playlists
                if 'entries' in info:
                    tracks = []
                    for entry in info['entries']:
                        if entry:
                            # Determine platform and get metadata
                            platform = 'soundcloud' if 'soundcloud.com' in url else 'youtube'
                            thumbnail = entry.get('thumbnail')
                            if not thumbnail and platform == 'soundcloud':
                                thumbnail = entry.get('artwork_url')
                            
                            track = {
                                'url': entry.get('url', url),
                                'title': entry.get('title', 'Unknown Title'),
                                'duration': entry.get('duration', 0),
                                'user': user,
                                'platform': platform,
                                'thumbnail': thumbnail,
                                'uploader': entry.get('uploader', entry.get('artist', 'Unknown Artist'))
                            }
                            if track['duration'] <= self.max_duration:
                                tracks.append(track)
                    self.queue.extend(tracks[:self.max_queue_size - len(self.queue)])
                    return tracks
                else:
                    # Handle single track
                    if info.get('duration', 0) > self.max_duration:
                        raise Exception("Track duration exceeds maximum limit (2 hours)")
                        
                    if len(self.queue) >= self.max_queue_size:
                        raise Exception("Queue is full")
                    
                    # Determine platform and get metadata
                    platform = 'soundcloud' if 'soundcloud.com' in url else 'youtube'
                    thumbnail = info.get('thumbnail')
                    if not thumbnail and platform == 'soundcloud':
                        thumbnail = info.get('artwork_url')
                        
                    track = {
                        'url': url,
                        'title': info.get('title', 'Unknown Title'),
                        'duration': info.get('duration', 0),
                        'user': user,
                        'platform': platform,
                        'thumbnail': thumbnail,
                        'uploader': info.get('uploader', info.get('artist', 'Unknown Artist'))
                    }
                    self.queue.append(track)
                    return track
                    
        except Exception as e:
            raise Exception(f"Error adding track to queue: {str(e)}")
            
    async def play_next(self):
        """Play the next track in the queue"""
        if not self.queue and not self.loop and not (self.loop_current and self.current_track):
            self.is_playing = False
            self.current_track = None
            if self.view:
                await self.view.update_player_message()
            return
            
        # Handle looping the current track
        if self.loop_current and self.current_track:
            # Keep the same track for replay
            track_to_play = self.current_track
        else:
            # Handle queue looping - only add current track back if we're looping the whole queue
            if self.loop and self.current_track and not self.loop_current:
                # Add the current track to the end of the queue for queue looping
                self.queue.append(self.current_track)
            
            # If queue is empty now, we can't continue
            if not self.queue:
                self.is_playing = False
                self.current_track = None
                if self.view:
                    await self.view.update_player_message()
                return
                
            # Get the next track from queue
            track_to_play = self.queue.popleft()
            self.current_track = track_to_play
            
        try:
            # Make sure we have a playback_url
            if 'playback_url' not in track_to_play:
                # Try to get the playback URL if it doesn't exist
                with yt_dlp.YoutubeDL(self.ytdl_opts) as ydl:
                    info = ydl.extract_info(track_to_play['url'], download=False)
                    if 'url' in info:
                        track_to_play['playback_url'] = info['url']
                    else:
                        # Try to get URL from formats
                        formats = info.get('formats', [])
                        if formats:
                            audio_formats = [f for f in formats if f.get('acodec') != 'none']
                            if audio_formats:
                                audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                                track_to_play['playback_url'] = audio_formats[0]['url']
                            else:
                                track_to_play['playback_url'] = formats[0]['url']
            
            # Create audio source and play
            audio_source = PCMVolumeTransformer(
                FFmpegPCMAudio(track_to_play['playback_url'], **FFMPEG_OPTS),
                volume=self.volume
            )
            
            def after_playing(error):
                if error:
                    print(f"Error in after_playing: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(), self.voice_client.loop)
            
            self.voice_client.play(audio_source, after=after_playing)
            self.is_playing = True
            
            # Update player message after starting playback
            if self.view:
                await self.view.update_player_message()
            
        except Exception as e:
            print(f"Error playing track: {e}")
            # Skip this track and move to the next one
            await self.play_next()
            
    def skip(self):
        """Skip the current track"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            
    def stop(self):
        """Stop playback and clear queue"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        self.queue.clear()
        self.current_track = None
        self.is_playing = False
        
    def set_volume(self, volume):
        """Set the volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.volume
            
    def get_queue_info(self):
        """Get information about the current queue"""
        total_duration = sum(track['duration'] for track in self.queue)
        if self.current_track:
            total_duration += self.current_track['duration']
            
        return {
            'current_track': self.current_track,
            'queue_size': len(self.queue),
            'total_duration': total_duration,
            'is_playing': self.is_playing
        }

# FFmpeg options for audio playback
FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k'  # Added bitrate limit for better performance
}

# Dictionary to store music players for each guild
music_players = {}

# Функция для инициализации состояния сервера
def init_server_state(guild_id):
    if guild_id not in server_states:
        server_states[guild_id] = {
            'is_playing_shiza': False,
            'current_radio': None,
            'volume': 1.0,
            'is_paused': False
        }

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

@bot.event
async def on_voice_state_update(member, before, after):
    # Если бот был отключен от голосового канала
    if member.id == bot.user.id and before.channel and not after.channel:
        guild_id = before.channel.guild.id
        # Очищаем состояние сервера
        if guild_id in server_states:
            server_states[guild_id]['is_playing_shiza'] = False
            server_states[guild_id]['current_radio'] = None
            server_states[guild_id]['is_paused'] = False
        
        # Удаляем voice client
        if guild_id in server_voice_clients:
            server_voice_clients.pop(guild_id, None)
        
        # Сбрасываем статус бота
        await update_bot_status(discord.ActivityType.watching, "за сервером")

@bot.event
async def on_message(message):
    # Пропускаем сообщения от бота
    if message.author.bot:
        return

    # Проверяем наличие @ упоминаний
    has_mentions = len(message.mentions) > 0 or len(message.role_mentions) > 0 or message.mention_everyone

    if has_mentions:
        user_id = message.author.id
        guild_id = message.guild.id

        # Инициализируем трекер для пользователя если его нет
        if guild_id not in mention_spam_tracker:
            mention_spam_tracker[guild_id] = {}
        if user_id not in mention_spam_tracker[guild_id]:
            mention_spam_tracker[guild_id][user_id] = {
                'count': 0,
                'last_message_time': datetime.datetime.now(),
                'warned': False
            }

        # Получаем данные пользователя
        user_data = mention_spam_tracker[guild_id][user_id]
        current_time = datetime.datetime.now()

        # Проверяем, прошло ли 10 секунд с последнего сообщения
        if (current_time - user_data['last_message_time']).total_seconds() > 10:
            # Сбрасываем счетчик если прошло больше 10 секунд
            user_data['count'] = 1
            user_data['warned'] = False
        else:
            user_data['count'] += 1

        user_data['last_message_time'] = current_time

        # Проверяем количество сообщений
        if user_data['count'] >= 4:
            if not user_data['warned']:
                # Отправляем предупреждение
                await message.channel.send(f"{message.author.mention}, спамер ебаный стоп нахуй, заебало чистить говно за тобой")
                user_data['warned'] = True
            else:
                # Выдаем таймаут
                try:
                    await message.author.timeout(datetime.timedelta(seconds=60), reason="Спам упоминаниями")
                    # Сбрасываем счетчик после таймаута
                    user_data['count'] = 0
                    user_data['warned'] = False
                except discord.Forbidden:
                    await message.channel.send("У меня нет прав для выдачи таймаута.")

    # Важно: не забываем обрабатывать команды
    await bot.process_commands(message)

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

            # Проверяем, может ли бот подключиться к каналу
            if not interaction.user.voice.channel.permissions_for(interaction.guild.me).connect:
                await interaction.response.send_message("У меня нет прав для подключения к голосовому каналу!", ephemeral=True)
                return

            # Проверяем, может ли бот говорить в канале
            if not interaction.user.voice.channel.permissions_for(interaction.guild.me).speak:
                await interaction.response.send_message("У меня нет прав для воспроизведения звука в голосовом канале!", ephemeral=True)
                return

            voice_client = server_voice_clients.get(self.guild_id)
            if voice_client and voice_client.is_connected():
                if voice_client.channel != interaction.user.voice.channel:
                    try:
                        await voice_client.move_to(interaction.user.voice.channel)
                    except discord.ClientException:
                        await interaction.response.send_message("Не удалось переключиться на другой голосовой канал!", ephemeral=True)
                        return
                # Корректно останавливаем текущее воспроизведение
                if voice_client.is_playing():
                    voice_client.stop()
                    # Даем время на завершение процесса ffmpeg
                    await asyncio.sleep(0.5)
            else:
                try:
                    voice_client = await interaction.user.voice.channel.connect()
                    server_voice_clients[self.guild_id] = voice_client
                except discord.ClientException as e:
                    await interaction.response.send_message(f"Не удалось подключиться к голосовому каналу: {str(e)}", ephemeral=True)
                    return

            server_states[self.guild_id]['current_radio'] = station
            server_states[self.guild_id]['is_paused'] = False
            
            try:
                audio_source = PCMVolumeTransformer(FFmpegPCMAudio(url), volume=server_states[self.guild_id]['volume'])
                voice_client.play(audio_source)
            except Exception as e:
                await interaction.response.send_message(f"Ошибка при воспроизведении: {str(e)}", ephemeral=True)
                return

            # Update bot status
            await update_bot_status(discord.ActivityType.listening, f"радио {station}")

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
            if voice_client.is_playing():
                voice_client.stop()
                # Даем время на завершение процесса ffmpeg
                await asyncio.sleep(0.5)
            await voice_client.disconnect()
            server_voice_clients.pop(self.guild_id, None)
            server_states[self.guild_id]['current_radio'] = None
            server_states[self.guild_id]['is_paused'] = False
            
            # Reset bot status
            await update_bot_status(discord.ActivityType.watching, "за сервером")
            
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
        self.add_item(ShizaButton("🚽 скибиди фортнайт", "/home/bot/skibidifortnite.mp3", guild_id))
        self.add_item(ShizaButton("🇷🇺 🤟 z руссский", "/home/bot/Smellslikeirusskiy.mp3", guild_id))
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

        # Проверяем, может ли бот подключиться к каналу
        if not interaction.user.voice.channel.permissions_for(interaction.guild.me).connect:
            await interaction.followup.send("У меня нет прав для подключения к голосовому каналу!", ephemeral=True)
            return

        # Проверяем, может ли бот говорить в канале
        if not interaction.user.voice.channel.permissions_for(interaction.guild.me).speak:
            await interaction.followup.send("У меня нет прав для воспроизведения звука в голосовом канале!", ephemeral=True)
            return

        voice_client = server_voice_clients.get(self.guild_id)

        if voice_client is None:
            try:
                voice_client = await interaction.user.voice.channel.connect()
                server_voice_clients[self.guild_id] = voice_client
            except discord.ClientException as e:
                await interaction.followup.send(f"Не удалось подключиться к голосовому каналу: {str(e)}", ephemeral=True)
                return
        elif voice_client.channel != interaction.user.voice.channel:
            try:
                await voice_client.move_to(interaction.user.voice.channel)
            except discord.ClientException:
                await interaction.followup.send("Не удалось переключиться на другой голосовой канал!", ephemeral=True)
                return

        if voice_client.is_playing():
            voice_client.stop()

        server_states[self.guild_id]['is_playing_shiza'] = True
        asyncio.create_task(play_shiza_loop(voice_client, self.file_path, self.guild_id))

        # Update bot status
        await update_bot_status(discord.ActivityType.listening, self.label)

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
            try:
                voice_client.stop()
                await voice_client.disconnect()
            except Exception as e:
                print(f"Ошибка при отключении: {e}")
            finally:
                server_voice_clients.pop(self.guild_id, None)
            
            # Reset bot status
            await update_bot_status(discord.ActivityType.watching, "за сервером")
            
            embed = discord.Embed(
                title="🎪 Шиза Плеер",
                description="**Статус:** Остановлено",
                color=discord.Color.red()
            )
            embed.set_image(url="https://i.pinimg.com/originals/c5/52/8e/c5528e6c4bb0a0ed0b7a3fcf127c68a2.gif")
            
            try:
                message = interaction.message
                await message.edit(embed=embed, view=self.view)
            except discord.NotFound:
                # Если сообщение уже удалено, пытаемся отправить новое
                try:
                    await interaction.channel.send(embed=embed, view=self.view)
                except:
                    pass
        else:
            await interaction.followup.send("Сейчас ничего не воспроизводится!", ephemeral=True)

async def play_shiza_loop(voice_client, file_path, guild_id):
    while server_states[guild_id]['is_playing_shiza'] and voice_client and voice_client.is_connected():
        try:
            audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(file_path), volume=1.0)
            voice_client.play(audio_source)
            
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
                if not server_states[guild_id]['is_playing_shiza'] or not voice_client.is_connected():
                    voice_client.stop()
                    # Даем время на завершение процесса ffmpeg
                    await asyncio.sleep(0.5)
                    return
                    
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")
            # Очищаем состояние при ошибке
            server_states[guild_id]['is_playing_shiza'] = False
            if guild_id in server_voice_clients:
                try:
                    if voice_client.is_playing():
                        voice_client.stop()
                        await asyncio.sleep(0.5)
                except:
                    pass
                server_voice_clients.pop(guild_id, None)
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
    # Update bot status
    await update_bot_status("custom", "генерирует текст")
    
    client = Client()
    models = ["deepseek-v3"]
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
            # Reset status after generation
            await update_bot_status(discord.ActivityType.watching, "за сервером")
            return
        except Exception as e:
            print(f"Ошибка при использовании модели {model}: {e}")

    await interaction.followup.send("Извините, произошла ошибка при обработке запроса. Попробуйте позже.")
    # Reset status after error
    await update_bot_status(discord.ActivityType.watching, "за сервером")

@bot.tree.command(name="image", description="Генерация изображения по запросу")
async def image(interaction: discord.Interaction, prompt: str):
    # Update bot status
    await update_bot_status("custom", "генерирует изображение")
    
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
    
    # Reset status after generation or error
    await update_bot_status(discord.ActivityType.watching, "за сервером")

@bot.tree.command(name="clear", description="Очистить чат от сообщений бота и команд.")
async def clear(interaction: discord.Interaction):
    def is_bot_or_command_message(message):
        return message.author == bot.user or message.content.startswith('/')

    deleted = await interaction.channel.purge(limit=100, check=is_bot_or_command_message)
    await interaction.response.send_message(f"Удалено {len(deleted)} сообщений.", ephemeral=True)

@bot.tree.command(name="clearall", description="Очистить чат от всех сообщений (только для администратора)")
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
        server_radio_messages.clear()
        
        python = sys.executable
        os.execl(python, python, *sys.argv)
        
    except Exception as e:
        await interaction.followup.send(f"Ошибка при перезапуске: {str(e)}", ephemeral=True)

@bot.tree.command(name="spam", description="Удалить сообщения с упоминаниями.")
async def spam(interaction: discord.Interaction, skolko: int = None):
    try:
        await interaction.response.defer(ephemeral=True)

        def is_mention(message):
            has_mentions = len(message.mentions) > 0 or len(message.role_mentions) > 0
            has_everyone = message.mention_everyone
            return has_mentions or has_everyone

        if skolko is None:
            deleted = await interaction.channel.purge(limit=1000, check=is_mention)
            try:
                await interaction.followup.send(f"Удалено {len(deleted)} сообщений с упоминаниями.")
            except:
                pass
            return

        if skolko < 1:
            try:
                await interaction.followup.send("Количество должно быть больше 0.")
            except:
                pass
            return

        deleted_count = 0
        batch_size = 100
        
        while deleted_count < skolko:
            messages_to_delete = []
            async for message in interaction.channel.history(limit=batch_size):
                if is_mention(message):
                    messages_to_delete.append(message)
                    deleted_count += 1
                    if deleted_count >= skolko:
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

        if deleted_count == skolko:
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

@bot.tree.command(name="del", description="Удалить N сообщений выбранного пользователя (только для администратора)")
async def del_messages(interaction: discord.Interaction, user: discord.Member, amount: int):
    if interaction.user.id != ADMIN_USER_ID:
        await interaction.response.send_message("У вас нет прав на выполнение этой команды.", ephemeral=True)
        return

    if amount < 1:
        await interaction.response.send_message("Количество должно быть больше 0.", ephemeral=True)
        return

    try:
        await interaction.response.defer(ephemeral=True)
        
        deleted_count = 0
        batch_size = 100
        
        while deleted_count < amount:
            messages_to_delete = []
            async for message in interaction.channel.history(limit=batch_size):
                if message.author.id == user.id:
                    messages_to_delete.append(message)
                    deleted_count += 1
                    if deleted_count >= amount:
                        break
            
            if not messages_to_delete:
                await interaction.followup.send(f"Найдено только {deleted_count} сообщений от пользователя {user.mention}.", ephemeral=True)
                break
                
            if len(messages_to_delete) > 1:
                await interaction.channel.delete_messages(messages_to_delete)
            elif messages_to_delete:
                await messages_to_delete[0].delete()

        if deleted_count == amount:
            await interaction.followup.send(f"Удалено {deleted_count} сообщений от пользователя {user.mention}.", ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send("У меня нет прав на удаление сообщений.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Произошла ошибка: {str(e)}", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Бот {bot.user} готов к работе!')
    
    for guild in bot.guilds:
        init_server_state(guild.id)
    
    # Sync commands
    try:
        await bot.tree.sync()
        print("Команды успешно синхронизированы!")
    except Exception as e:
        print(f"Ошибка при синхронизации команд: {e}")
    
    # Set initial status
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="за сервером"), status=discord.Status.online)

async def update_bot_status(activity_type, name):
    """Helper function to update bot status"""
    if activity_type == "custom":
        await bot.change_presence(activity=discord.Activity(name=name), status=discord.Status.online)
    else:
        activity = discord.Activity(type=activity_type, name=name)
        await bot.change_presence(activity=activity, status=discord.Status.online)

@bot.event
async def on_guild_join(guild):
    init_server_state(guild.id)
    print(f'Бот присоединился к серверу: {guild.name}')

@bot.event
async def on_guild_remove(guild):
    server_states.pop(guild.id, None)
    server_voice_clients.pop(guild.id, None)
    server_radio_messages.pop(guild.id, None)
    print(f'Бот покинул сервер: {guild.name}')

@bot.tree.command(name="play", description="Музыкальный плеер YouTube или SoundCloud")
async def play(interaction: discord.Interaction):
    """Open music player"""
    if not interaction.user.voice:
        await interaction.response.send_message("Вы должны быть в голосовом канале!", ephemeral=True)
        return
        
    await interaction.response.defer()
    
    guild_id = interaction.guild.id
    
    # Clean up old player if it exists
    if guild_id in music_players:
        old_player = music_players[guild_id]
        if old_player.voice_client and old_player.voice_client.is_connected():
            await old_player.voice_client.disconnect()
        if old_player.player_message:
            try:
                await old_player.player_message.delete()
            except:
                pass
    
    # Create new player
    music_players[guild_id] = MusicPlayer(guild_id)
    player = music_players[guild_id]
    
    try:
        # Check bot permissions
        if not interaction.user.voice.channel.permissions_for(interaction.guild.me).connect:
            await interaction.followup.send("У меня нет прав для подключения к голосовому каналу!", ephemeral=True)
            return
            
        if not interaction.user.voice.channel.permissions_for(interaction.guild.me).speak:
            await interaction.followup.send("У меня нет прав для воспроизведения звука в голосовом канале!", ephemeral=True)
            return
            
        # Connect to voice channel if not already connected
        if not player.voice_client or not player.voice_client.is_connected():
            player.voice_client = await interaction.user.voice.channel.connect()
        elif player.voice_client.channel != interaction.user.voice.channel:
            await player.voice_client.move_to(interaction.user.voice.channel)
            
        # Create new player view
        player.view = MusicPlayerView(player)
            
        # Create initial embed
        embed = await player.view.create_player_embed()
        
        # Send new player message
        player.player_message = await interaction.followup.send(embed=embed, view=player.view)
        player.view.message = player.player_message
            
    except Exception as e:
        await interaction.followup.send(f"Ошибка: {str(e)}", ephemeral=True)

class MusicPlayerView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player
        self.message = None
        
    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.primary, custom_id="play_pause")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.voice_client:
            await interaction.response.send_message("Сейчас ничего не играет!", ephemeral=True)
            return
            
        if self.player.voice_client.is_playing():
            self.player.voice_client.pause()
            button.label = "▶️"
        elif self.player.voice_client.is_paused():
            self.player.voice_client.resume()
            button.label = "⏸️"
            
        await self.update_player_message(interaction)
        
    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary, custom_id="skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.voice_client:
            await interaction.response.send_message("Сейчас ничего не играет!", ephemeral=True)
            return
            
        self.player.skip()
        await self.update_player_message(interaction)
        
    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger, custom_id="stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.voice_client:
            await interaction.response.send_message("Сейчас ничего не играет!", ephemeral=True)
            return
            
        self.player.stop()
        
        # Disconnect from voice channel
        if self.player.voice_client and self.player.voice_client.is_connected():
            await self.player.voice_client.disconnect()
            self.player.voice_client = None
            
        await self.update_player_message(interaction)

    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, custom_id="loop")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.voice_client:
            await interaction.response.send_message("Сейчас ничего не играет!", ephemeral=True)
            return
        
        # Cycle through loop states: No loop -> Loop current track -> Loop queue -> No loop
        if not self.player.loop and not self.player.loop_current:
            # No loop -> Loop current track
            self.player.loop_current = True
            self.player.loop = False
            button.label = "🔂"  # Loop current track symbol
            button.style = discord.ButtonStyle.success
        elif self.player.loop_current:
            # Loop current track -> Loop queue
            self.player.loop_current = False
            self.player.loop = True
            button.label = "🔁"  # Loop queue symbol
            button.style = discord.ButtonStyle.success
        else:
            # Loop queue -> No loop
            self.player.loop = False
            self.player.loop_current = False
            button.label = "🔁"
            button.style = discord.ButtonStyle.secondary
        
        await self.update_player_message(interaction)

    @discord.ui.button(label="➕ Добавить трек", style=discord.ButtonStyle.success, custom_id="add_track")
    async def add_track(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.response.send_message("Вы должны быть в голосовом канале!", ephemeral=True)
            return

        # Create a modal for URL input
        class AddTrackModal(discord.ui.Modal, title="Добавить трек"):
            url = discord.ui.TextInput(
                label="Ссылка на трек",
                placeholder="Введите ссылку на YouTube или SoundCloud",
                required=True,
                min_length=1,
                max_length=200
            )

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer()
                
                # Validate URL
                if not re.match(r'^https?://(?:www\.)?(?:youtube\.com|youtu\.be|soundcloud\.com|spotify\.com|music\.yandex\.ru)/', self.url.value):
                    await interaction.followup.send("Пожалуйста, укажите корректную ссылку с поддерживаемых платформ (YouTube, SoundCloud)!", ephemeral=True)
                    return

                try:
                    # Check bot permissions
                    if not interaction.user.voice.channel.permissions_for(interaction.guild.me).connect:
                        await interaction.followup.send("У меня нет прав для подключения к голосовому каналу!", ephemeral=True)
                        return
                        
                    if not interaction.user.voice.channel.permissions_for(interaction.guild.me).speak:
                        await interaction.followup.send("У меня нет прав для воспроизведения звука в голосовом канале!", ephemeral=True)
                        return

                    # Connect to voice channel if not already connected
                    if not self.player.voice_client or not self.player.voice_client.is_connected():
                        self.player.voice_client = await interaction.user.voice.channel.connect()
                    elif self.player.voice_client.channel != interaction.user.voice.channel:
                        await self.player.voice_client.move_to(interaction.user.voice.channel)

                    # Get track info
                    with yt_dlp.YoutubeDL(self.player.ytdl_opts) as ydl:
                        info = ydl.extract_info(self.url.value, download=False)
                        
                        # Determine platform and get metadata
                        platform = 'soundcloud' if 'soundcloud.com' in self.url.value else 'youtube'
                        thumbnail = info.get('thumbnail')
                        if not thumbnail and platform == 'soundcloud':
                            thumbnail = info.get('artwork_url')
                            
                        # Get the direct URL for playback
                        if 'url' not in info:
                            # Try to get the URL from formats
                            formats = info.get('formats', [])
                            if formats:
                                # Get the best audio format
                                audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                                if audio_formats:
                                    # Sort by quality and get the best one
                                    audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                                    playback_url = audio_formats[0]['url']
                                else:
                                    # Fallback to the first format if no audio-only format is found
                                    playback_url = formats[0]['url']
                            else:
                                raise Exception("Could not find a playable URL for this track")
                        else:
                            playback_url = info['url']
                            
                        track = {
                            'url': self.url.value,  # Original URL for display
                            'playback_url': playback_url,  # Direct URL for playback
                            'title': info.get('title', 'Неизвестное название'),
                            'duration': info.get('duration', 0),
                            'user': interaction.user,
                            'platform': platform,
                            'thumbnail': thumbnail,
                            'uploader': info.get('uploader', info.get('artist', 'Unknown Artist'))
                        }

                    # Start playing if not already playing
                    if not self.player.is_playing:
                        # Prepare audio before starting playback
                        audio_source = PCMVolumeTransformer(
                            FFmpegPCMAudio(track['playback_url'], **FFMPEG_OPTS),
                            volume=self.player.volume
                        )
                        
                        def after_playing(error):
                            if error:
                                print(f"Error in after_playing: {error}")
                            asyncio.run_coroutine_threadsafe(self.player.play_next(), self.player.voice_client.loop)
                        
                        self.player.voice_client.play(audio_source, after=after_playing)
                        self.player.is_playing = True
                        self.player.current_track = track  # Set current track
                        
                        # Update message after playback has started
                        await asyncio.sleep(0.1)  # Small delay to ensure playback has started
                        embed = await self.view.create_player_embed()
                        try:
                            await self.view.message.edit(embed=embed, view=self.view)
                        except discord.NotFound:
                            # If message was deleted, send a new one
                            self.view.message = await interaction.channel.send(embed=embed, view=self.view)
                    else:
                        # If already playing, add to queue
                        self.player.queue.append(track)
                        # Update message
                        embed = await self.view.create_player_embed()
                        try:
                            await self.view.message.edit(embed=embed, view=self.view)
                        except discord.NotFound:
                            # If message was deleted, send a new one
                            self.view.message = await interaction.channel.send(embed=embed, view=self.view)
                        
                except Exception as e:
                    await interaction.followup.send(f"Ошибка: {str(e)}", ephemeral=True)

        # Add player reference to modal
        modal = AddTrackModal()
        modal.player = self.player
        modal.view = self
        
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔉", style=discord.ButtonStyle.secondary, custom_id="volume_down")
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.voice_client:
            await interaction.response.send_message("Сейчас ничего не играет!", ephemeral=True)
            return

        # Decrease volume by 10%
        self.player.set_volume(max(0.0, self.player.volume - 0.1))
        await self.update_player_message(interaction)

    @discord.ui.button(label="🔊", style=discord.ButtonStyle.secondary, custom_id="volume_up")
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.voice_client:
            await interaction.response.send_message("Сейчас ничего не играет!", ephemeral=True)
            return

        # Increase volume by 10% (max 2.0)
        self.player.set_volume(min(2.0, self.player.volume + 0.1))
        await self.update_player_message(interaction)

    async def update_player_message(self, interaction: discord.Interaction = None):
        if not self.message:
            return
            
        embed = await self.create_player_embed()
        try:
            if interaction:
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            self.message = None
            
    async def create_player_embed(self):
        embed = discord.Embed(title="🎵 Музыкальный плеер", color=discord.Color.blue())
        
        if self.player.current_track:
            # Handle thumbnails and track info based on platform
            platform = self.player.current_track.get('platform', 'youtube')
            
            if platform == 'youtube':
                # Get thumbnail and video ID for YouTube videos
                video_id = None
                if 'youtube.com' in self.player.current_track['url']:
                    video_id = self.player.current_track['url'].split('v=')[-1].split('&')[0]
                else:  # youtu.be
                    video_id = self.player.current_track['url'].split('/')[-1].split('?')[0]
                    
                if video_id:
                    embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg")
                    embed.set_image(url=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg")
            else:  # SoundCloud
                thumbnail = self.player.current_track.get('thumbnail')
                if thumbnail:
                    # Replace t500x500 with t300x300 for better Discord compatibility
                    thumbnail = thumbnail.replace('t500x500', 't300x300')
                    embed.set_thumbnail(url=thumbnail)
                    embed.set_image(url=thumbnail)
                else:
                    # Default SoundCloud thumbnail if none provided
                    embed.set_thumbnail(url="https://a-v2.sndcdn.com/assets/images/sc-icons/ios-a62dfc8f.png")
                    embed.set_image(url="https://a-v2.sndcdn.com/assets/images/sc-icons/ios-a62dfc8f.png")
            
            status = "⏸️ На паузе" if self.player.voice_client.is_paused() else "▶️ Играет"
            duration = float(self.player.current_track.get('duration', 0))
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            
            # Add platform-specific emoji
            platform_emoji = "🎵"  # Use music note for all tracks
            
            embed.description = f"**Сейчас играет:** {platform_emoji} {self.player.current_track.get('title', 'Unknown Title')}\n"
            embed.description += f"**Исполнитель:** {self.player.current_track.get('uploader', 'Unknown Artist')}\n"
            embed.description += f"**Длительность:** {minutes}:{seconds:02d}\n"
            embed.description += f"**Добавил:** {self.player.current_track.get('user', 'Unknown User').mention}\n"
            embed.description += f"**Статус:** {status}\n"
            embed.description += f"**Громкость:** {int(self.player.volume * 100)}%\n"
            
            # Show looping status with appropriate emoji
            if self.player.loop_current:
                embed.description += f"**Повтор:** 🔂 Текущий трек\n"
            elif self.player.loop:
                embed.description += f"**Повтор:** 🔁 Вся очередь\n"
            else:
                embed.description += f"**Повтор:** Выключен\n"
                
            embed.description += f"**Ссылка:** [Нажмите здесь]({self.player.current_track.get('url', '')})"
            
            # Show next 3 tracks in queue with platform indicators
            if self.player.queue:
                queue_list = []
                for i, track in enumerate(list(self.player.queue)[:3], 1):
                    track_platform = track.get('platform', 'youtube')
                    platform_emoji = "🎵" if track_platform == 'soundcloud' else "🎥"
                    queue_list.append(f"{i}. {platform_emoji} {track.get('title', 'Unknown Title')} - {track.get('uploader', 'Unknown Artist')} ({track.get('user', 'Unknown User').mention})")
                
                embed.add_field(
                    name="Следующие треки",
                    value="\n".join(queue_list) + ("\n..." if len(self.player.queue) > 3 else ""),
                    inline=False
                )
        else:
            embed.description = "Сейчас ничего не играет"
            
        return embed

# Запуск бота
bot.run('')