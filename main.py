import os
import json
import logging
from spotify_utils import read_playlist_url_from_file, get_playlist_tracks
from youtube_utils import load_metadata, download_song

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("download_log.txt"),
        logging.StreamHandler()
    ]
)

def fetch_spotify_metadata() -> bool:
    print("=" * 60)
    print("🎧 Spotify Playlist Metadata Fetcher")
    print("=" * 60)

    try:
        # Step 1: Read playlist URL
        playlist_url = read_playlist_url_from_file("spotify_playlist.txt")
        logging.info("📄 Playlist URL loaded.")

        # Step 2: Fetch metadata from Spotify (including YouTube & Apple Music)
        logging.info("🔍 Fetching metadata from Spotify and Odesli...")
        tracks = get_playlist_tracks(playlist_url)

        if not tracks:
            logging.warning("⚠️ No tracks found in the playlist.")
            return False

        # Step 3: Save to metadata folder
        os.makedirs("metadata", exist_ok=True)
        output_file = "metadata/spotify_playlist_metadata.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(tracks, f, indent=2, ensure_ascii=False)

        logging.info(f"✅ Saved metadata for {len(tracks)} tracks to {output_file}")
        return True

    except Exception as e:
        logging.error(f"❌ Error fetching Spotify metadata: {e}")
        return False

def download_mp3s():
    print("\n" + "=" * 60)
    print("📥 YouTube MP3 Downloader using Spotify Metadata")
    print("=" * 60)

    tracks = load_metadata()
    if not tracks:
        logging.error("❌ No tracks found in metadata file.")
        return

    logging.info(f"🎶 Found {len(tracks)} tracks to download.")
    for i, track in enumerate(tracks, 1):
        logging.info(f"[{i}/{len(tracks)}] Downloading: {track.get('song_title')}")
        download_song(track)

    logging.info("🎉 All downloads complete. Check the 'songs/' folder and log for details.")

def main():
    if fetch_spotify_metadata():
        download_mp3s()

if __name__ == "__main__":
    main()
