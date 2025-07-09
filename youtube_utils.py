import os
import json
import logging
import yt_dlp
from pathlib import Path
from typing import List, Dict, Tuple

# Paths
METADATA_FILE = "metadata/spotify_playlist_metadata.json"
SONGS_DIR = Path("songs")
SONGS_DIR.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("download_log.txt"),
        logging.StreamHandler()
    ]
)

# yt-dlp config
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }]
}

def load_metadata() -> List[Dict]:
    """Load metadata from JSON file."""
    if not os.path.exists(METADATA_FILE):
        logging.error(f"Metadata file not found: {METADATA_FILE}")
        return []
    
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_youtube_url(url: str) -> Tuple[bool, str]:
    """Check if YouTube URL is valid and accessible"""
    if not url:
        return False, "No URL provided"
    
    # Check URL format
    if not any(domain in url for domain in ["youtube.com", "youtu.be"]):
        return False, "Invalid YouTube URL format"
    
    # Quick test if video exists
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return True, "Valid URL"
    except Exception as e:
        return False, f"Video not accessible: {str(e)[:100]}"
    
    return False, "Unknown validation error"

def build_search_query(track: dict) -> str:
    """Build a search query from song title and first primary artist."""
    title = track.get("song_title", "")
    artists = [a["name"] for a in track.get("artists", []) if a["role"] == "primary"]
    artist = artists[0] if artists else ""
    return f"{title} {artist}".strip()

def download_with_direct_url(track: dict, youtube_url: str, output_path: Path) -> Tuple[bool, str]:
    """Download using direct YouTube URL"""
    ydl_opts = YDL_OPTIONS.copy()
    ydl_opts['outtmpl'] = str(output_path.with_suffix('.%(ext)s'))
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        return True, "Downloaded successfully using direct URL"
    except Exception as e:
        return False, f"Direct URL download failed: {str(e)[:200]}"

def download_with_search(track: dict, output_path: Path) -> Tuple[bool, str]:
    """Download using YouTube search as fallback"""
    query = build_search_query(track)
    search_url = f"ytsearch1:{query}"
    
    ydl_opts = YDL_OPTIONS.copy()
    ydl_opts['outtmpl'] = str(output_path.with_suffix('.%(ext)s'))
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_url])
        return True, f"Downloaded successfully using search: '{query}'"
    except Exception as e:
        return False, f"Search download failed: {str(e)[:200]}"

def download_song(track: dict) -> bool:
    """Download song using direct URL first, then fallback to search"""
    spotify_id = track.get("spotify_id")
    song_title = track.get("song_title", "Unknown")
    youtube_url = track.get("youtube_url")
    
    output_path = SONGS_DIR / f"{spotify_id}.mp3"

    # Check if already exists
    if output_path.exists():
        logging.info(f"⏭️  Already exists: {song_title}")
        return True

    logging.info(f"🎵 Processing: {song_title}")

    # Method 1: Try direct YouTube URL first (if available)
    if youtube_url:
        logging.debug(f"🎯 Trying direct URL: {youtube_url}")
        
        # Validate URL first
        is_valid, validation_msg = validate_youtube_url(youtube_url)
        if is_valid:
            success, msg = download_with_direct_url(track, youtube_url, output_path)
            if success:
                logging.info(f"✅ {msg}")
                return True
            else:
                logging.warning(f"⚠️  Direct URL failed: {msg}")
        else:
            logging.warning(f"⚠️  Invalid URL: {validation_msg}")
    else:
        logging.debug("🔍 No direct YouTube URL available")

    # Method 2: Fallback to text search
    logging.debug("🔍 Falling back to YouTube search...")
    success, msg = download_with_search(track, output_path)
    
    if success:
        logging.info(f"✅ {msg}")
        return True
    else:
        logging.error(f"❌ All methods failed for '{song_title}': {msg}")
        return False

def get_download_stats(tracks: List[Dict]) -> Dict:
    """Get statistics about downloads"""
    total = len(tracks)
    downloaded = 0
    has_youtube_url = 0
    
    for track in tracks:
        spotify_id = track.get("spotify_id")
        output_path = SONGS_DIR / f"{spotify_id}.mp3"
        
        if output_path.exists():
            downloaded += 1
        
        if track.get("youtube_url"):
            has_youtube_url += 1
    
    return {
        "total": total,
        "downloaded": downloaded,
        "remaining": total - downloaded,
        "has_youtube_url": has_youtube_url,
        "success_rate": (downloaded / total * 100) if total > 0 else 0
    }

def main():
    print("=" * 60)
    print("📥 Enhanced YouTube MP3 Downloader")
    print("📱 Direct URLs + Search Fallback")
    print("=" * 60)

    tracks = load_metadata()
    if not tracks:
        print("❌ No tracks found in metadata.")
        return

    # Show statistics
    stats = get_download_stats(tracks)
    print(f"\n📊 Download Statistics:")
    print(f"   📝 Total tracks: {stats['total']}")
    print(f"   ✅ Already downloaded: {stats['downloaded']}")
    print(f"   ⏳ Remaining: {stats['remaining']}")
    print(f"   🎯 Have YouTube URLs: {stats['has_youtube_url']}")
    print(f"   📈 Success rate: {stats['success_rate']:.1f}%")

    if stats['remaining'] == 0:
        print("\n🎉 All tracks already downloaded!")
        return

    print(f"\n🚀 Starting download of {stats['remaining']} tracks...\n")

    # Download remaining tracks
    success_count = 0
    fail_count = 0

    for i, track in enumerate(tracks, 1):
        spotify_id = track.get("spotify_id")
        output_path = SONGS_DIR / f"{spotify_id}.mp3"
        
        # Skip if already exists
        if output_path.exists():
            continue
            
        logging.info(f"[{i}/{len(tracks)}] Starting download...")
        
        if download_song(track):
            success_count += 1
        else:
            fail_count += 1

    # Final statistics
    print(f"\n" + "=" * 60)
    print(f"📊 DOWNLOAD COMPLETE")
    print(f"=" * 60)
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"📁 Check 'songs/' folder for downloaded files")
    print(f"📋 Check 'download_log.txt' for detailed logs")

if __name__ == "__main__":
    main()