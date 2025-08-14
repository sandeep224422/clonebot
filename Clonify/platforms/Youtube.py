# music_api_client.py

import asyncio
import os
import re
import json
import glob
import random
import logging
from urllib.parse import urlencode, urljoin
from typing import Union, Optional, Tuple

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

# If you want to use AudioPiped/AudioFile in your bot, import these where you call join_call:
# from pytgcalls.types.input_stream import AudioPiped, AudioFile

# Replace with actual function or import from your project
from Clonify.utils.database import is_on_off
from Clonify.utils.formatters import time_to_seconds

# Constants
YOUR_API_KEY = "zefron@123"
BASE_URL = "https://asliaaap-7a3650d5591c.herokuapp.com"
MUSIC_API_STREAM_ENDPOINT = f"{BASE_URL}/api/download"

# --------------------
# Cookie helper
# --------------------
def cookie_txt_file() -> str:
    folder_path = os.path.join(os.getcwd(), "cookies")
    filename = os.path.join(os.getcwd(), "cookies", "logs.csv")
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    chosen = random.choice(txt_files)
    with open(filename, "a") as file:
        file.write(f"Choosen File : {chosen}\n")
    return f"cookies/{os.path.basename(chosen)}"

# --------------------
# Music API Client
# --------------------
async def get_audio_stream_from_api(
    query: str,
    fmt: str = "mp3",
    quality: str = "320kbps",
    timeout_sec: int = 60,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to get a direct audio URL from the Music API.
    Returns (url, query_used) if ready, else (None, None).
    """
    try:
        params = {"query": query, "format": fmt, "quality": quality}
        stream_url = f"{MUSIC_API_STREAM_ENDPOINT}?{urlencode(params)}"

        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url, allow_redirects=True) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if resp.status == 200 and content_type.startswith("audio"):
                    return str(resp.url), query

                if resp.status == 202:
                    data = await resp.json()
                    status_url = data.get("statusUrl")
                    file_url = data.get("fileUrl")
                    if not status_url or not file_url:
                        return None, None

                    if status_url.startswith("/"):
                        status_url = urljoin(BASE_URL, status_url)
                    if file_url.startswith("/"):
                        file_url = urljoin(BASE_URL, file_url)

                    end_time = asyncio.get_event_loop().time() + timeout_sec
                    while asyncio.get_event_loop().time() < end_time:
                        async with session.get(status_url) as r2:
                            if r2.status != 200:
                                await asyncio.sleep(1)
                                continue
                            j = await r2.json()
                            status = j.get("download", {}).get("status")
                            if status == "completed":
                                return file_url, query
                            if status == "failed":
                                return None, None
                        await asyncio.sleep(1)

                    return None, None

                return None, None

    except Exception as e:
        logging.error(f"Music API error: {e}")
        return None, None

# --------------------
# Helpers
# --------------------
async def check_file_size(link: str) -> Optional[int]:
    async def get_format_info(link_):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",
            cookie_txt_file(),
            "-J",
            link_,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f"Error:\n{stderr.decode()}")
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for f in formats:
            if "filesize" in f:
                total_size += f["filesize"]
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None

    formats = info.get("formats", [])
    if not formats:
        print("No formats found.")
        return None

    return parse_size(formats)

async def shell_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if err:
        if "unavailable videos are hidden" in err.decode("utf-8").lower():
            return out.decode("utf-8")
        else:
            return err.decode("utf-8")
    return out.decode("utf-8")

# --------------------
# YouTubeAPI Class
# --------------------
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset is None:
            return None
        return text[offset : offset + length]

    async def details(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Tuple[str, str, int, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if duration_min == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
            return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",
            cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None) -> list:
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            result = [x for x in result if x != ""]
        except Exception:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[dict, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None) -> Tuple[list, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for f in r["formats"]:
                try:
                    str(f["format"])
                    _ = f["filesize"]
                    _ = f["format_id"]
                    _ = f["ext"]
                    _ = f["format_note"]
                except Exception:
                    continue
                if "dash" not in str(f["format"]).lower():
                    formats_available.append(
                        {
                            "format": f["format"],
                            "filesize": f["filesize"],
                            "format_id": f["format_id"],
                            "ext": f["ext"],
                            "format_note": f["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Tuple[Optional[str], Optional[bool]]:
        """
        Returns (source, direct)
          - If direct is False, source is a network URL (use AudioPiped with PyTgCalls)
          - If direct is True, source is a local file path (use AudioFile with PyTgCalls)
        """
        if videoid:
            link = self.base + link

        # Prefer Music API for audio if not video or song video
        if not video and not songvideo:
            try:
                search_title = title
                if not search_title:
                    results = VideosSearch(link, limit=1)
                    for result in (await results.next())["result"]:
                        search_title = result["title"]
                        break

                if search_title:
                    logging.info(f"Searching Music API for: {search_title}")
                    direct_url, api_title = await get_audio_stream_from_api(search_title)
                    if direct_url:
                        logging.info(f"Got audio stream from Music API: {api_title}")
                        # Return URL for the player (network source)
                        return direct_url, False
                    else:
                        logging.warning("Music API pending/failed, falling back to yt-dlp")
            except Exception as e:
                logging.error(f"Music API error, falling back to yt-dlp: {str(e)}")

        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            info = ydl.extract_info(link, False)
            filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(filepath):
                return filepath
            ydl.download([link])
            return filepath

        def video_dl():
            ydl_opts = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            info = ydl.extract_info(link, False)
            filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(filepath):
                return filepath
            ydl.download([link])
            return filepath

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_opts = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            ydl.download([link])

        def song_audio_dl():
            formats = "bestaudio/best"
            fpath = f"downloads/{title}.mp3"
            ydl_opts = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            ydl.download([link])

        if songaudio:
            song_audio_dl()
            return f"downloads/{title}.mp3", True
        elif songvideo:
            song_video_dl()
            return f"downloads/{title}", True
        elif video:
            path = video_dl()
            return path, True
        else:
            path = audio_dl()
            return path, True
