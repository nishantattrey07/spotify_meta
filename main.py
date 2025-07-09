import os
import json
import logging
import sys
from spotify_utils import (
    read_playlist_url_from_file, 
    get_playlist_tracks, 
    test_spotify_connection,
    SpotifyQuotaExceeded,
    SpotifyConnectionError
)
from youtube_utils import load_metadata, download_song, get_download_stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("download_log.txt"),
        logging.StreamHandler()
    ]
)

def check_requirements() -> bool:
    """Check if all required files and dependencies are present"""
    print("🔍 Checking requirements...")
    
    # Check .env file
    if not os.path.exists(".env"):
        print("❌ .env file not found!")
        print("📝 Create .env file with:")
        print("   SPOTIFY_CLIENT_ID=your_client_id")
        print("   SPOTIFY_CLIENT_SECRET=your_client_secret")
        print("   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback")
        return False
    
    # Check Spotify credentials
    from dotenv import load_dotenv
    load_dotenv()
    
    if not os.getenv("SPOTIFY_CLIENT_ID") or not os.getenv("SPOTIFY_CLIENT_SECRET"):
        print("❌ Spotify credentials missing in .env file!")
        return False
    
    # Check playlist file
    if not os.path.exists("spotify_playlist.txt"):
        print("❌ spotify_playlist.txt not found!")
        print("📝 Create spotify_playlist.txt with your Spotify playlist URL")
        return False
    
    print("✅ All requirements met!")
    return True

def fetch_spotify_metadata() -> bool:
    """Fetch metadata with robust error handling"""
    print("=" * 60)
    print("🎧 Spotify Playlist Metadata Fetcher")
    print("🛡️  Enhanced with Error Handling")
    print("=" * 60)

    try:
        # Step 1: Test Spotify connection
        print("\n🔗 Testing Spotify connection...")
        is_connected, message = test_spotify_connection()
        if not is_connected:
            print(message)
            print("\n💡 Troubleshooting tips:")
            print("   1. Check your .env file credentials")
            print("   2. Ensure you have internet connection")
            print("   3. Try again in a few minutes if rate limited")
            return False
        
        print(message)

        # Step 2: Read playlist URL
        print("\n📄 Reading playlist URL...")
        playlist_url = read_playlist_url_from_file("spotify_playlist.txt")
        logging.info("✅ Playlist URL loaded successfully")

        # Step 3: Fetch metadata from Spotify (including YouTube & Apple Music)
        print("\n🔍 Fetching metadata from Spotify and Odesli...")
        print("⚠️  This may take a while for large playlists...")
        
        tracks = get_playlist_tracks(playlist_url)

        if not tracks:
            logging.warning("⚠️ No tracks found in the playlist.")
            return False

        # Step 4: Save to metadata folder
        os.makedirs("metadata", exist_ok=True)
        output_file = "metadata/spotify_playlist_metadata.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(tracks, f, indent=2, ensure_ascii=False)

        # Step 5: Show statistics
        youtube_urls_count = sum(1 for track in tracks if track.get('youtube_url'))
        
        print(f"\n✅ Successfully fetched metadata!")
        print(f"📊 Statistics:")
        print(f"   📝 Total tracks: {len(tracks)}")
        print(f"   🎯 YouTube URLs found: {youtube_urls_count}")
        print(f"   🔍 Will use search for: {len(tracks) - youtube_urls_count}")
        print(f"   💾 Saved to: {output_file}")

        logging.info(f"✅ Saved metadata for {len(tracks)} tracks to {output_file}")
        return True

    except SpotifyQuotaExceeded as e:
        print(f"\n⏰ Spotify quota/rate limit exceeded!")
        print(f"🔧 Error: {e}")
        print(f"💾 Progress has been saved automatically")
        print(f"⏳ Please try again later (usually 1 hour for quota, few minutes for rate limits)")
        return False
        
    except SpotifyConnectionError as e:
        print(f"\n❌ Spotify connection error!")
        print(f"🔧 Error: {e}")
        print(f"💡 Check your internet connection and credentials")
        return False
        
    except FileNotFoundError as e:
        print(f"\n❌ File not found: {e}")
        return False
        
    except ValueError as e:
        print(f"\n❌ Invalid input: {e}")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.error(f"❌ Error fetching Spotify metadata: {e}")
        return False

def download_mp3s() -> bool:
    """Download MP3s with enhanced error handling"""
    print("\n" + "=" * 60)
    print("📥 YouTube MP3 Downloader")
    print("🎯 Direct URLs + Search Fallback")
    print("=" * 60)

    tracks = load_metadata()
    if not tracks:
        print("❌ No tracks found in metadata file.")
        print("💡 Run the metadata fetcher first!")
        return False

    # Show initial statistics
    stats = get_download_stats(tracks)
    print(f"\n📊 Current Status:")
    print(f"   📝 Total tracks: {stats['total']}")
    print(f"   ✅ Already downloaded: {stats['downloaded']}")
    print(f"   ⏳ Remaining: {stats['remaining']}")
    print(f"   🎯 Have YouTube URLs: {stats['has_youtube_url']}")
    print(f"   📈 Current success rate: {stats['success_rate']:.1f}%")

    if stats['remaining'] == 0:
        print("\n🎉 All tracks already downloaded!")
        return True

    # Confirm before starting
    user_input = input(f"\n🚀 Download {stats['remaining']} remaining tracks? (y/n): ")
    if user_input.lower() != 'y':
        print("⏹️  Download cancelled by user")
        return False

    print(f"\n🎵 Starting downloads...\n")

    # Download tracks
    success_count = 0
    fail_count = 0
    
    for i, track in enumerate(tracks, 1):
        spotify_id = track.get("spotify_id")
        song_title = track.get("song_title", "Unknown")
        output_path = f"songs/{spotify_id}.mp3"
        
        # Skip if already exists
        if os.path.exists(output_path):
            continue
            
        print(f"[{i}/{len(tracks)}] {song_title}")
        
        try:
            if download_song(track):
                success_count += 1
            else:
                fail_count += 1
        except KeyboardInterrupt:
            print(f"\n⏹️  Download stopped by user")
            break
        except Exception as e:
            logging.error(f"❌ Unexpected error downloading '{song_title}': {e}")
            fail_count += 1

    # Final statistics
    total_attempted = success_count + fail_count
    final_success_rate = (success_count / total_attempted * 100) if total_attempted > 0 else 0
    
    print(f"\n" + "=" * 60)
    print(f"📊 DOWNLOAD SUMMARY")
    print(f"=" * 60)
    print(f"✅ Successful downloads: {success_count}")
    print(f"❌ Failed downloads: {fail_count}")
    print(f"📈 Success rate: {final_success_rate:.1f}%")
    print(f"📁 Files saved to: songs/ folder")
    print(f"📋 Detailed logs: download_log.txt")

    if fail_count > 0:
        print(f"\n💡 Tips for failed downloads:")
        print(f"   • Check download_log.txt for specific errors")
        print(f"   • Some videos might be region-blocked or deleted")
        print(f"   • Try running the downloader again later")

    return success_count > 0

def main():
    """Main orchestration with comprehensive error handling"""
    print("🎵 Spotify to YouTube MP3 Downloader")
    print("🚀 Enhanced Version with Error Handling")
    print("=" * 60)
    
    # Check requirements first
    if not check_requirements():
        print("\n❌ Requirements check failed. Please fix the issues above.")
        sys.exit(1)
    
    try:
        # Step 1: Fetch metadata
        metadata_success = fetch_spotify_metadata()
        
        if not metadata_success:
            print("\n❌ Metadata fetching failed. Check the errors above.")
            sys.exit(1)
        
        # Step 2: Download MP3s
        download_success = download_mp3s()
        
        if download_success:
            print("\n🎉 Process completed successfully!")
        else:
            print("\n⚠️  Process completed with some issues. Check logs for details.")
            
    except KeyboardInterrupt:
        print("\n⏹️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error in main process: {e}")
        logging.error(f"❌ Unexpected error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()