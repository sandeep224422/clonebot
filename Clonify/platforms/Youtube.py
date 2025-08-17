import aiohttp
import asyncio
import logging
from typing import Optional, Tuple

BASE_API_URL = "https://apikeyy-zeta.vercel.app/api"

async def get_audio_stream_from_api(
    query: str,
    fmt: str = "mp3",
    quality: str = "320kbps",
    timeout_sec: int = 60,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Get direct audio URL from new API.
    Returns (url, query) or (None, None).
    """
    try:
        download_url = f"{BASE_API_URL}/download"
        params = {"search": query}
        headers = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "formats" in data:
                        audio_formats = [f for f in data["formats"] if f.get("kind") in ("audio-only", "progressive")]
                        if audio_formats:
                            best_audio = sorted(audio_formats, key=lambda x: x.get("abr", 0), reverse=True)[0]
                            direct_url = best_audio.get("url")
                            if direct_url:
                                logging.info(f"Audio URL found: {direct_url}")
                                return direct_url, query
                    logging.warning("No audio formats found.")
                    return None, None
                else:
                    logging.error(f"API response status: {resp.status}")
                    return None, None
    except asyncio.TimeoutError:
        logging.error("Request timed out")
        return None, None
    except Exception as e:
        logging.error(f"Error fetching audio: {e}")
        return None, None

async def get_audio_stream_from_api_v2(
    query: str,
    timeout_sec: int = 60,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Alternative method using /fast-meta then /download endpoint.
    """
    try:
        meta_url = f"{BASE_API_URL}/fast-meta"
        params = {"search": query}
        headers = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession() as session:
            async with session.get(meta_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "link" in data and data["link"]:
                        download_url = f"{BASE_API_URL}/download"
                        download_params = {"url": data["link"]}

                        async with session.get(download_url, params=download_params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as dl_resp:
                            if dl_resp.status == 200:
                                dl_data = await dl_resp.json()
                                if "formats" in dl_data:
                                    audio_formats = [f for f in dl_data["formats"] if f.get("kind") in ("audio-only", "progressive")]
                                    if audio_formats:
                                        best_audio = sorted(audio_formats, key=lambda x: x.get("abr", 0), reverse=True)[0]
                                        direct_url = best_audio.get("url")
                                        if direct_url:
                                            logging.info(f"Audio URL found (v2): {direct_url}")
                                            return direct_url, query
                    logging.warning("No audio found in fast-meta response.")
                    return None, None
                else:
                    logging.error(f"Fast-meta response status: {resp.status}")
                    return None, None
    except asyncio.TimeoutError:
        logging.error("Request timed out")
        return None, None
    except Exception as e:
        logging.error(f"Error in v2 fetch: {e}")
        return None, None
