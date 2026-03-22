import feedparser # for parsing RSS feeds
import requests
import os
import re
import json
from datetime import datetime, timedelta, timezone
from podcasts import PODCASTS

# Config -----------------------------------------------------
OUTPUT_DIR = "audio"
METADATA_DIR = "metadata"
DAYS_BACK = 7
# ------------------------------------------------------------

def sanitize_filename(title: str) -> str:
    """Remove special characters from episode title for use as filename"""
    return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")

def fetch_feed(rss_url: str) -> feedparser.FeedParserDict:
    """Fetch and parse the RSS feed"""
    print(f"  Fetching feed: {rss_url}")
    # make HTTP GET request to RSS URL, get XML, parse into Python object
    feed = feedparser.parse(rss_url)
    return feed

def is_recent(entry: feedparser.FeedParserDict, cutoff: datetime) -> bool:
    """Check if an episode was published after the cutoff date."""
    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return pub_date >= cutoff

def parse_duration(raw: str) -> int:
    """Convert duration to seconds. Handles both 'HH:MM:SS' and raw seconds formats."""
    if not raw:
        return None
    if ":" in raw:
        # HH:MM:SS or MM:SS format
        parts = raw.strip().split(":")
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
    return int(raw)  # raw seconds

def download_episode(entry: feedparser.FeedParserDict, podcast_id: str, output_dir: str) -> str:
    """
    1: Download a single episode mp3, returns path to saved file.
    2: Download metadata for episode: title, episode, publication date, duration.
    """
    # 1: grab audio url and create filepath: audio/{podcast_id}__{sanitized_title}.mp3
    if not entry.get("enclosures"):
        print(f"    Skipping (no audio): {entry.title}")
        return None
    audio_url = entry.enclosures[0].href
    filename = f"{podcast_id}__{sanitize_filename(entry.title)}.mp3"
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        print(f"    Already exists, skipping: {filename}")
        return filepath

    print(f"    Downloading: {filename}")
    response = requests.get(audio_url, stream=True) # stream=True to download in chunks

    # save to file in chunks to avoid loading entire file into memory
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"    Saved: {filepath}")

    # 2: save metadata to a JSON file with the same name but .json extension
    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).date().isoformat()
    duration = parse_duration(entry.get("itunes_duration"))
    metadata = {
        "podcast_id": podcast_id,
        "episode_title": entry.title,
        "published_date": pub_date,
        "duration_seconds": duration
    }
    os.makedirs(METADATA_DIR, exist_ok=True)
    metadata_path = os.path.join(METADATA_DIR, filename.replace(".mp3", ".json"))
    with open(metadata_path, "w") as f:
        json.dump(metadata, f)

    return filepath

def fetch_recent_episodes(podcast: dict, cutoff: datetime, output_dir: str):
    """Fetch and download all episodes from the last DAYS_BACK days for a podcast"""
    feed = fetch_feed(podcast["rss_feed"])
    downloaded = 0

    for entry in feed.entries:
        if not is_recent(entry, cutoff):
            break  # RSS is newest-first, so we can stop here

        download_episode(entry, podcast["id"], output_dir)
        downloaded += 1

    if downloaded == 0:
        print(f"    No new episodes in the last {DAYS_BACK} days")
    else:
        print(f"  Found {downloaded} episode(s) in the last {DAYS_BACK} days")

def main():
    """Main function to fetch feed and download episodes"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    print(f"Fetching episodes since {cutoff.strftime('%Y-%m-%d')}\n")

    for podcast in PODCASTS:
        print(f"Podcast: {podcast['name']}")
        fetch_recent_episodes(podcast, cutoff, OUTPUT_DIR)
        print()

    print(f"Done! Episodes saved to '{OUTPUT_DIR}/'")

if __name__ == "__main__":
    main()