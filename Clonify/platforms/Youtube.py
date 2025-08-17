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

# Constants - Updated for JioSaavn API
BASE_URL = "https://apikeyy-zeta.vercel.app"

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
# Test and Debug Functions
# --------------------
async def test_jiosaavn_api():
    """
    Test function to debug JioSaavn API endpoints and responses.
    """
    import aiohttp
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Check if base URL is accessible
        try:
            async with session.get(BASE_URL, headers=headers, timeout=10) as resp:
                logging.info(f"Base URL test - Status: {resp.status}")
                if resp.status == 200:
                    text = await resp.text()
                    logging.info(f"Base URL response: {text[:200]}...")
        except Exception as e:
            logging.error(f"Base URL test failed: {e}")
        
        # Test 2: Test search endpoint
        search_url = f"{BASE_URL}/search/songs"
        params = {"query": "latest"}
        
        try:
            async with session.get(search_url, params=params, headers=headers, timeout=10) as resp:
                logging.info(f"Search endpoint test - Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    logging.info(f"Search response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    logging.info(f"Search response: {str(data)[:500]}...")
                else:
                    error_text = await resp.text()
                    logging.error(f"Search endpoint error: {error_text}")
        except Exception as e:
            logging.error(f"Search endpoint test failed: {e}")
        
        # Test 3: Test trending endpoint
        trending_url = f"{BASE_URL}/search/songs"
        trending_params = {"query": "trending"}
        
        try:
            async with session.get(trending_url, params=trending_params, headers=headers, timeout=10) as resp:
                logging.info(f"Trending endpoint test - Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    logging.info(f"Trending response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    logging.info(f"Trending response: {str(data)[:500]}...")
                else:
                    error_text = await resp.text()
                    logging.error(f"Trending endpoint error: {error_text}")
        except Exception as e:
            logging.error(f"Trending endpoint test failed: {e}")

# --------------------
# JioSaavn API Client - UPDATED VERSION
# --------------------
async def get_audio_stream_from_jiosaavn_api(
    query: str,
    timeout_sec: int = 60,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to get a direct audio URL from the JioSaavn API.
    Returns (url, query_used) if ready, else (None, None).
    """
    try:
        # Search for songs using JioSaavn API
        search_url = f"{BASE_URL}/search/songs"
        
        params = {
            "query": query
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        logging.info(f"Searching JioSaavn API with URL: {search_url} and params: {params}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
                logging.info(f"JioSaavn search response status: {resp.status}")
                
                if resp.status == 200:
                    data = await resp.json()
                    logging.info(f"JioSaavn search response data structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    # Check if we got results - handle different possible response structures
                    results = None
                    if "data" in data and "results" in data["data"]:
                        results = data["data"]["results"]
                    elif "results" in data:
                        results = data["results"]
                    elif "data" in data and isinstance(data["data"], list):
                        results = data["data"]
                    
                    if results and len(results) > 0:
                        # Get the first result
                        first_song = results[0]
                        logging.info(f"First song result: {first_song.get('name', 'No name')} by {first_song.get('artists', {}).get('primary', [{}])[0].get('name', 'Unknown') if first_song.get('artists') else 'Unknown'}")
                        
                        song_id = first_song.get("id")
                        
                        if song_id:
                            # Now get the song details with download URLs
                            song_url = f"{BASE_URL}/songs/{song_id}"
                            logging.info(f"Fetching song details from: {song_url}")
                            
                            async with session.get(song_url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as song_resp:
                                logging.info(f"Song details response status: {song_resp.status}")
                                
                                if song_resp.status == 200:
                                    song_data = await song_resp.json()
                                    logging.info(f"Song details data structure: {list(song_data.keys()) if isinstance(song_data, dict) else 'Not a dict'}")
                                    
                                    # Handle different possible response structures
                                    song_info = None
                                    if "data" in song_data and song_data["data"]:
                                        if isinstance(song_data["data"], list):
                                            song_info = song_data["data"][0]
                                        else:
                                            song_info = song_data["data"]
                                    elif "result" in song_data:
                                        song_info = song_data["result"]
                                    else:
                                        song_info = song_data
                                    
                                    if song_info:
                                        # Get download URLs - prefer higher quality
                                        download_urls = song_info.get("downloadUrl", [])
                                        if not download_urls:
                                            download_urls = song_info.get("download_url", [])
                                        if not download_urls:
                                            download_urls = song_info.get("downloadUrls", [])
                                        
                                        logging.info(f"Found {len(download_urls)} download URLs")
                                        
                                        if download_urls:
                                            # Sort by quality (assuming higher index = better quality)
                                            # Get the best available quality
                                            best_url = None
                                            for i, url_info in enumerate(reversed(download_urls)):
                                                if isinstance(url_info, dict) and url_info.get("url"):
                                                    best_url = url_info["url"]
                                                    logging.info(f"Selected download URL {len(download_urls) - i}: {best_url}")
                                                    break
                                                elif isinstance(url_info, str):
                                                    best_url = url_info
                                                    logging.info(f"Selected download URL {len(download_urls) - i}: {best_url}")
                                                    break
                                            
                                            if best_url:
                                                logging.info(f"Got JioSaavn audio URL: {best_url}")
                                                return best_url, query
                                        else:
                                            logging.warning("No download URLs found in song info")
                                    else:
                                        logging.warning("No song info found in response")
                                else:
                                    logging.error(f"Song details request failed with status {song_resp.status}")
                                    if song_resp.status == 404:
                                        logging.error("Song not found in JioSaavn database")
                    else:
                        logging.warning(f"No search results found for query: {query}")
                        logging.info(f"Search response: {data}")
                    
                    logging.warning("No audio URLs found in JioSaavn API response")
                    return None, None
                    
                elif resp.status == 404:
                    logging.error("Search endpoint not found - API might be down or endpoint changed")
                    return None, None
                else:
                    logging.error(f"JioSaavn API returned status {resp.status}")
                    try:
                        error_text = await resp.text()
                        logging.error(f"Error response: {error_text}")
                    except:
                        pass
                    return None, None

    except asyncio.TimeoutError:
        logging.error("JioSaavn API request timed out")
        return None, None
    except Exception as e:
        logging.error(f"JioSaavn API error: {e}")
        return None, None

# Alternative method using direct song search
async def get_audio_stream_from_jiosaavn_api_v2(
    query: str,
    timeout_sec: int = 60,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Alternative method for JioSaavn API with better error handling.
    """
    try:
        # First search for the song
        search_url = f"{BASE_URL}/search/songs"
        
        params = {
            "query": query
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        logging.info(f"JioSaavn v2: Searching with query: {query}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
                logging.info(f"JioSaavn v2: Search response status: {resp.status}")
                
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Handle different response structures
                    results = None
                    if "data" in data and "results" in data["data"]:
                        results = data["data"]["results"]
                    elif "results" in data:
                        results = data["results"]
                    elif "data" in data and isinstance(data["data"], list):
                        results = data["data"]
                    
                    if results and len(results) > 0:
                        # Get the first result
                        first_song = results[0]
                        song_id = first_song.get("id")
                        
                        if song_id:
                            # Get song details
                            song_url = f"{BASE_URL}/songs/{song_id}"
                            
                            async with session.get(song_url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as song_resp:
                                if song_resp.status == 200:
                                    song_data = await song_resp.json()
                                    
                                    # Handle different response structures
                                    song_info = None
                                    if "data" in song_data and song_data["data"]:
                                        if isinstance(song_data["data"], list):
                                            song_info = song_data["data"][0]
                                        else:
                                            song_info = song_data["data"]
                                    elif "result" in song_data:
                                        song_info = song_data["result"]
                                    else:
                                        song_info = song_data
                                    
                                    if song_info:
                                        # Try to get the best quality download URL
                                        download_urls = song_info.get("downloadUrl", [])
                                        if not download_urls:
                                            download_urls = song_info.get("download_url", [])
                                        if not download_urls:
                                            download_urls = song_info.get("downloadUrls", [])
                                        
                                        if download_urls:
                                            # Look for the best quality URL
                                            for url_info in download_urls:
                                                if isinstance(url_info, dict) and url_info.get("url"):
                                                    # Check if it's a valid audio URL
                                                    url = url_info["url"]
                                                    if any(ext in url.lower() for ext in ['.mp3', '.m4a', '.aac', '.ogg']):
                                                        logging.info(f"Got JioSaavn audio URL via v2: {url}")
                                                        return url, query
                                            
                                            # If no specific audio extension found, use the first available
                                            for url_info in download_urls:
                                                if isinstance(url_info, dict) and url_info.get("url"):
                                                    logging.info(f"Got JioSaavn URL via v2: {url_info['url']}")
                                                    return url_info["url"], query
                                                elif isinstance(url_info, str):
                                                    logging.info(f"Got JioSaavn URL via v2: {url_info}")
                                                    return url_info, query
                    
                    logging.warning("No audio stream found via JioSaavn v2 method")
                    return None, None
                    
                else:
                    logging.error(f"JioSaavn API v2 returned status {resp.status}")
                    return None, None

    except asyncio.TimeoutError:
        logging.error("JioSaavn API v2 request timed out")
        return None, None
    except Exception as e:
        logging.error(f"JioSaavn API v2 error: {e}")
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

        # Prefer JioSaavn API for audio if not video or song video
        if not video and not songvideo:
            try:
                search_title = title
                if not search_title:
                    results = VideosSearch(link, limit=1)
                    for result in (await results.next())["result"]:
                        search_title = result["title"]
                        break

                if search_title:
                    logging.info(f"Searching JioSaavn API for: {search_title}")
                    
                    # Try both JioSaavn API methods
                    direct_url, api_title = await get_audio_stream_from_jiosaavn_api(search_title)
                    if not direct_url:
                        direct_url, api_title = await get_audio_stream_from_jiosaavn_api_v2(search_title)
                    
                    if direct_url:
                        logging.info(f"Got audio stream from JioSaavn API: {api_title}")
                        # Return URL for the player (network source)
                        return direct_url, False
                    else:
                        logging.warning("JioSaavn API pending/failed, falling back to yt-dlp")
                        # Run API test to debug issues
                        try:
                            await test_jiosaavn_api()
                        except Exception as test_e:
                            logging.error(f"API test failed: {test_e}")
            except Exception as e:
                logging.error(f"JioSaavn API error, falling back to yt-dlp: {str(e)}")

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
#         # Network URL from JioSaavn API (use URL, do NOT os.stat it)
#         await PRO.join_call(chat_id, AudioPiped(source))
