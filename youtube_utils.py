import os
import json
import logging
import yt_dlp
from pathlib import Path

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

def load_metadata():
    """Load metadata from JSON file."""
    if not os.path.exists(METADATA_FILE):
        logging.error(f"Metadata file not found: {METADATA_FILE}")
        return []
    
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_search_query(track: dict) -> str:
    """Build a search query from song title and first primary artist."""
    title = track.get("song_title", "")
    artists = [a["name"] for a in track.get("artists", []) if a["role"] == "primary"]
    artist = artists[0] if artists else ""
    return f"{title} {artist}".strip()

def download_song(track: dict):
    spotify_id = track.get("spotify_id")
    output_path = SONGS_DIR / f"{spotify_id}.mp3"

    if output_path.exists():
        logging.info(f"✅ Already exists: {output_path.name}")
        return

    query = build_search_query(track)
    logging.info(f"🎵 Searching YouTube for: {query}")

    search_url = f"ytsearch1:{query}"

    ydl_opts = YDL_OPTIONS.copy()
    ydl_opts['outtmpl'] = str(output_path.with_suffix('.%(ext)s'))

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_url])
        logging.info(f"✅ Downloaded: {output_path.name}")
    except Exception as e:
        logging.error(f"❌ Failed to download '{query}': {e}")

def main():
    print("=" * 60)
    print("📥 YouTube MP3 Downloader using Spotify Metadata")
    print("=" * 60)

    tracks = load_metadata()
    if not tracks:
        print("❌ No tracks found in metadata.")
        return

    print(f"🔍 Found {len(tracks)} tracks. Starting download...\n")
    for i, track in enumerate(tracks, 1):
        logging.info(f"[{i}/{len(tracks)}] Processing: {track.get('song_title')}")
        download_song(track)

    print("\n🎉 All downloads attempted. Check 'songs/' folder and 'download_log.txt' for results.")

if __name__ == "__main__":
    main()
