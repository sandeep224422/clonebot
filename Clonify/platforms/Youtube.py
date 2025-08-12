# music_api_client.py

from Clonify.utils.database import is_on_off
from Clonify.utils.formatters import time_to_seconds

import asyncio
import os
import re
import json
import aiohttp
from typing import Union, Optional, Tuple

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

import glob
import random
import logging
from urllib.parse import urlencode, urljoin

# If you want to use AudioPiped/AudioFile in your bot, import these where you call join_call
# from pytgcalls.types.input_stream import AudioPiped, AudioFile


def cookie_txt_file() -> str:
    folder_path = f"{os.getcwd()}/cookies"
    filename = f"{os.getcwd()}/cookies/logs.csv"
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    chosen = random.choice(txt_files)
    with open(filename, "a") as file:
        file.write(f"Choosen File : {chosen}\n")
    return f"cookies/{str(chosen).split('/')[-1]}"


# Optional; not required by the API (server does not check it)
YOUR_API_KEY = "zefron@123"
BASE_URL = "https://shreeapi-d165da120f71.herokuapp.com"
MUSIC_API_STREAM_ENDPOINT = f"{BASE_URL}/api/downloads/stream"


async def get_audio_stream_from_api(
    query: str,
    fmt: str = "mp3",
    quality: str = "320kbps",
    timeout_sec: int = 60,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to get a direct audio URL from the Zefron API.
    Returns (url, query_used) if ready, else (None, None).
    """
    try:
        params = {"query": query, "format": fmt, "quality": quality}
        stream_url = f"{MUSIC_API_STREAM_ENDPOINT}?{urlencode(params)}"

        async with aiohttp.ClientSession() as session:
            # First attempt: directly call stream endpoint
            async with session.get(stream_url, allow_redirects=True) as resp:
                content_type = resp.headers.get("Content-Type", "")
                # If the server finished quickly, it returns audio directly
                if resp.status == 200 and content_type.startswith("audio"):
                    return str(resp.url), query

                # Otherwise, server returns 202 JSON with status/file URLs
                if resp.status == 202:
                    data = await resp.json()
                    status_url = data.get("statusUrl")
                    file_url = data.get("fileUrl")
                    if not status_url or not file_url:
                        return None, None

                    # Absolutize URLs
                    if status_url.startswith("/"):
                        status_url = urljoin(BASE_URL, status_url)
                    if file_url.startswith("/"):
                        file_url = urljoin(BASE_URL, file_url)

                    # Poll until completed or timeout
                    end_time = asyncio.get_event_loop().time() + timeout_sec
                    while asyncio.get_event_loop().time() < end_time:
                        async with session.get(status_url) as r2:
                            if r2.status != 200:
                                await asyncio.sleep(1)
                                continue
                            j = await r2.json()
                            status = j.get("download", {}).get("status")
                            if status == "completed":
                                # Return file URL to stream
                                return file_url, query
                            if status == "failed":
                                return None, None
                        await asyncio.sleep(1)

                    # Timed out
                    return None, None

                # Any other status → fallback
                return None, None

    except Exception as e:
        logging.error(f"Music API error: {e}")
        return None, None


async def check_file_size(link):
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

    total_size = parse_size(formats)
    return total_size


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if err:
        if "unavailable videos are hidden" in (err.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return err.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
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
        if offset in (None,):
            return None
        return text[offset: offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
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
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
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
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except Exception:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
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

    async def formats(self, link: str, videoid: Union[bool, str] = None):
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
                except Exception:
                    continue
                if "dash" not in str(f["format"]).lower():
                    try:
                        f["format"]
                        f["filesize"]
                        f["format_id"]
                        f["ext"]
                        f["format_note"]
                    except Exception:
                        continue
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

        # Prefer Music API for audio
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
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
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
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath, True
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath, True
        elif video:
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
                return downloaded_file, True
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies",
                    cookie_txt_file(),
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                if stdout:
                    # Direct network stream URL
                    return stdout.decode().split("\n")[0], False
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        return None, None
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        return None, None
                    downloaded_file = await loop.run_in_executor(None, video_dl)
                    return downloaded_file, True
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, True


# Example usage with PyTgCalls (call from your handler):
# async def play_with_pytgcalls(PRO, chat_id: int, link_or_title: str):
#     from pytgcalls.types.input_stream import AudioPiped, AudioFile
#     source, direct = await YouTubeAPI().download(
#         link=link_or_title,
#         mystic=None,
#         video=False,
#         songaudio=False,
#         songvideo=False,
#         format_id=None,
#         title=None,
#     )
#     if source is None:
#         return
#     if direct:
#         # Local file path
#         await PRO.join_call(chat_id, AudioFile(source))
#     else:
#         # Network URL from Zefron API (use URL, do NOT os.stat it)
#         await PRO.join_call(chat_id, AudioPiped(source))
