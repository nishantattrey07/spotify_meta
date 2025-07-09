import os
import json
import spotipy
import requests
from spotipy.oauth2 import SpotifyOAuth
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
SCOPE = "playlist-read-private"

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SCOPE,
    cache_path=".cache"
))

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
        artist = sp.artist(artist_id)
        return {
            "genres": artist.get("genres", []),
            "popularity": artist.get("popularity", 0)
        }
    except Exception:
        return {"genres": [], "popularity": 0}

def get_odesli_links(spotify_url: str) -> Dict:
    """Fetch YouTube and Apple Music links from Odesli (Song.link)."""
    try:
        resp = requests.get("https://api.song.link/v1-alpha.1/links", params={"url": spotify_url}, timeout=10)
        if resp.ok:
            data = resp.json().get("linksByPlatform", {})
            return {
                "youtube_url": data.get("youtube", {}).get("url"),
                "apple_music_url": data.get("appleMusic", {}).get("url")
            }
    except Exception as e:
        print(f"⚠️ Odesli request failed: {e}")
    return {
        "youtube_url": None,
        "apple_music_url": None
    }

def get_playlist_tracks(playlist_url: str) -> List[Dict]:
    playlist_id = extract_playlist_id(playlist_url)
    results = sp.playlist_items(playlist_id, additional_types=["track"])
    
    tracks = []

    while results:
        for item in results['items']:
            track = item['track']
            if not track:
                continue

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
                metadata = get_artist_metadata(artist['id'])
                genres.update(metadata["genres"])
                if i == 0:
                    artist_popularity = metadata["popularity"]

            album = {
                "title": track['album']['name'],
                "main_artist_name": artists[0]["name"]
            }

            # 🧠 Get YouTube and Apple Music links from Odesli
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

        if results.get("next"):
            results = sp.next(results)
        else:
            break

    return tracks
