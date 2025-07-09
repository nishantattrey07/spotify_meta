import os
import json
import spotipy
import requests
import time
import logging
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from typing import List, Dict, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
SCOPE = "playlist-read-private"

# Progress tracking
PROGRESS_FILE = "metadata/download_progress.json"

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SCOPE,
    cache_path=".cache"
))

class SpotifyQuotaExceeded(Exception):
    """Custom exception for quota exceeded errors"""
    pass

class SpotifyConnectionError(Exception):
    """Custom exception for connection errors"""
    pass

def test_spotify_connection() -> Tuple[bool, str]:
    """Test if Spotify API is working before starting"""
    try:
        user = sp.current_user()
        if user:
            logging.info(f"✅ Connected to Spotify as: {user.get('display_name', 'Unknown')}")
            return True, "Connected successfully"
    except SpotifyException as e:
        if e.http_status == 401:
            return False, "❌ Spotify authentication failed. Check your credentials in .env file"
        elif e.http_status == 429:
            return False, "❌ Spotify rate limit exceeded. Wait and try again later"
        elif "quota exceeded" in str(e).lower():
            return False, "❌ Spotify API quota exceeded. Try again tomorrow"
        else:
            return False, f"❌ Spotify API error: {e}"
    except Exception as e:
        return False, f"❌ Connection failed: {e}"

def safe_spotify_call(func, *args, **kwargs):
    """Make Spotify API calls with proper error handling"""
    try:
        return func(*args, **kwargs)
    except SpotifyException as e:
        if e.http_status == 429:
            logging.error("❌ Rate limit exceeded. Saving progress and exiting...")
            raise SpotifyQuotaExceeded("Rate limit exceeded")
        elif "quota exceeded" in str(e).lower():
            logging.error("❌ API quota exceeded. Saving progress and exiting...")
            raise SpotifyQuotaExceeded("API quota exceeded")
        elif e.http_status == 401:
            logging.error("❌ Authentication failed. Check your Spotify credentials.")
            raise SpotifyConnectionError("Authentication failed")
        else:
            logging.error(f"❌ Spotify API error: {e}")
            raise SpotifyConnectionError(f"API error: {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error in Spotify call: {e}")
        raise SpotifyConnectionError(f"Unexpected error: {e}")

def save_progress(tracks: List[Dict], current_index: int = 0):
    """Save current progress to resume later"""
    os.makedirs("metadata", exist_ok=True)
    progress_data = {
        "tracks": tracks,
        "current_index": current_index,
        "timestamp": time.time(),
        "total_tracks": len(tracks)
    }
    
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)
    
    logging.info(f"💾 Progress saved: {current_index}/{len(tracks)} tracks processed")

def load_progress() -> Tuple[List[Dict], int]:
    """Load previous progress if exists"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            tracks = data.get("tracks", [])
            current_index = data.get("current_index", 0)
            
            logging.info(f"📂 Resuming from progress: {current_index}/{len(tracks)} tracks")
            return tracks, current_index
        except Exception as e:
            logging.warning(f"⚠️ Could not load progress file: {e}")
    
    return [], 0

def read_playlist_url_from_file(filepath="spotify_playlist.txt") -> str:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"{filepath} not found. Please create the file with your Spotify playlist link.")
    
    with open(filepath, "r") as f:
        url = f.readline().strip()
        if not url.startswith("https://open.spotify.com/playlist/"):
            raise ValueError("Invalid Spotify playlist URL format.")
        return url

def extract_playlist_id(playlist_url: str) -> str:
    return playlist_url.split("/")[-1].split("?")[0]

def get_artist_metadata(artist_id: str) -> Dict:
    try:
        artist = safe_spotify_call(sp.artist, artist_id)
        return {
            "genres": artist.get("genres", []),
            "popularity": artist.get("popularity", 0)
        }
    except (SpotifyQuotaExceeded, SpotifyConnectionError):
        raise  # Re-raise quota/connection errors
    except Exception as e:
        logging.warning(f"⚠️ Could not get artist metadata for {artist_id}: {e}")
        return {"genres": [], "popularity": 0}

def get_odesli_links(spotify_url: str) -> Dict:
    """Fetch YouTube and Apple Music links from Odesli (Song.link)."""
    try:
        resp = requests.get(
            "https://api.song.link/v1-alpha.1/links", 
            params={"url": spotify_url}, 
            timeout=10
        )
        if resp.ok:
            data = resp.json().get("linksByPlatform", {})
            youtube_url = data.get("youtube", {}).get("url")
            apple_music_url = data.get("appleMusic", {}).get("url")
            
            if youtube_url:
                logging.debug(f"✅ Found YouTube URL via Odesli: {youtube_url}")
            else:
                logging.debug("⚠️ No YouTube URL found via Odesli")
                
            return {
                "youtube_url": youtube_url,
                "apple_music_url": apple_music_url
            }
        else:
            logging.warning(f"⚠️ Odesli API returned status {resp.status_code}")
    except requests.exceptions.Timeout:
        logging.warning("⚠️ Odesli request timed out")
    except Exception as e:
        logging.warning(f"⚠️ Odesli request failed: {e}")
    
    return {
        "youtube_url": None,
        "apple_music_url": None
    }

def get_playlist_tracks(playlist_url: str) -> List[Dict]:
    """Get playlist tracks with robust error handling and progress saving"""
    
    # Check if we have previous progress
    existing_tracks, start_index = load_progress()
    if existing_tracks:
        user_input = input(f"📂 Found previous progress ({start_index}/{len(existing_tracks)} tracks). Continue? (y/n): ")
        if user_input.lower() == 'y':
            return existing_tracks
        else:
            # Clear progress file
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
    
    playlist_id = extract_playlist_id(playlist_url)
    
    try:
        results = safe_spotify_call(sp.playlist_items, playlist_id, additional_types=["track"])
    except (SpotifyQuotaExceeded, SpotifyConnectionError) as e:
        logging.error(f"❌ Failed to fetch playlist: {e}")
        return []
    
    tracks = []
    track_count = 0

    while results:
        for item in results['items']:
            track = item['track']
            if not track:
                continue

            track_count += 1
            logging.info(f"📥 Processing track {track_count}: {track['name']}")

            try:
                title = track['name']
                duration_ms = track['duration_ms']
                duration_sec = int(duration_ms / 1000)
                spotify_url = track['external_urls']['spotify']
                spotify_id = track['id']
                track_popularity = track.get('popularity', 0)

                artists = []
                genres = set()
                artist_popularity = 0

                for i, artist in enumerate(track['artists']):
                    artists.append({"name": artist['name'], "role": "primary"})
                    try:
                        metadata = get_artist_metadata(artist['id'])
                        genres.update(metadata["genres"])
                        if i == 0:
                            artist_popularity = metadata["popularity"]
                    except (SpotifyQuotaExceeded, SpotifyConnectionError):
                        # Save progress and exit
                        save_progress(tracks, track_count - 1)
                        raise

                album = {
                    "title": track['album']['name'],
                    "main_artist_name": artists[0]["name"]
                }

                # 🎯 Get YouTube and Apple Music links from Odesli
                external_links = get_odesli_links(spotify_url)

                track_data = {
                    "spotify_id": spotify_id,
                    "spotify_url": spotify_url,
                    "youtube_url": external_links.get("youtube_url"),
                    "apple_music_url": external_links.get("apple_music_url"),
                    "song_title": title,
                    "duration": duration_sec,
                    "track_popularity": track_popularity,
                    "artist_popularity": artist_popularity,
                    "artists": artists,
                    "album": album,
                    "genres": list(genres)
                }

                tracks.append(track_data)

                # Save progress every 10 tracks
                if track_count % 10 == 0:
                    save_progress(tracks, track_count)

            except (SpotifyQuotaExceeded, SpotifyConnectionError):
                # Save progress and re-raise
                save_progress(tracks, track_count - 1)
                raise
            except Exception as e:
                logging.warning(f"⚠️ Error processing track '{track.get('name', 'Unknown')}': {e}")
                continue

        # Get next page
        try:
            if results.get("next"):
                results = safe_spotify_call(sp.next, results)
            else:
                break
        except (SpotifyQuotaExceeded, SpotifyConnectionError):
            # Save progress and exit
            save_progress(tracks, track_count)
            raise

    # Save final progress
    save_progress(tracks, track_count)
    
    # Clean up progress file on successful completion
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    
    return tracks