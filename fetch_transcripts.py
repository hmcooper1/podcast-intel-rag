from datetime import datetime, timedelta, timezone
import os
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build

def get_recent_playlist_videos(api_key, playlist_id, num_days=7):
    """
    Fetch video IDs from a YouTube playlist uploaded in the last `num_days`
    Args:
        api_key (str): YouTube Data API key
        playlist_id (str): YouTube playlist ID
        num_days (int): number of days to look back for videos
    Returns:
        List[Tuple[str, str]]: list of tuples with (video_id, publish_date)
    """

    # initialize youtube api client
    youtube = build("youtube", "v3", developerKey=api_key)
    recent_videos = []
    seen_videos = set() # to track seen video IDs and avoid duplicates

    # calculate cutoff datetime based on num_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=num_days)

    # start on the first page of playlist items
    next_page_token = None
    while True:
        # construct api request to fetch basic info from videos (playlist items)
        request = youtube.playlistItems().list(
            part="snippet", # fetch basic info: video ID, publish date, etc.
            playlistId=playlist_id,
            maxResults=50, # max allowed by API
            pageToken=next_page_token
        )
        response = request.execute()

        # iterate through videos in current page, stop when date cutoff is reached
        for item in response["items"]:
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            publish_date = snippet["publishedAt"]
            # convert string to Python datetime object
            publish_dt = datetime.strptime(publish_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            
            # if video is newer than cutoff and haven't seen it before, add to results
            if publish_dt >= cutoff:
                if video_id not in seen_videos:
                    recent_videos.append((video_id, publish_date))
                    seen_videos.add(video_id) # mark this video ID as seen
            else:
                # older than cutoff -> stop
                return recent_videos

        # check if there are more pages
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return recent_videos

def save_transcripts(video_files, folder="transcripts"):
    """
    Fetch and save transcripts for a list of videos as separate text files
    Args:        
        video_files (List[Tuple[str, str]]): list of tuples with (video_id, filename)
        folder (str): directory to save transcript files
    """
    
    # ensure ouptut folder exists
    os.makedirs(folder, exist_ok=True)
    for video_id, filename in video_files:
        # fetch transcript, concentrate on text content, and save to file
        try:
            transcript = YouTubeTranscriptApi().fetch(video_id)
            full_text = " ".join([snippet.text for snippet in transcript])
            path = os.path.join(folder, filename)
            with open(path, "w") as f:
                f.write(full_text)
            print(f"Transcript saved for video {filename} -> {path}")
        except Exception as e:
            print(f"Failed to fetch transcript for video {video_id}: {e}")



# test functions
API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY not found in environment variables")

# dataframed
DF_PLAYLIST_ID = "PLjgj6kdf_snbWS6Ltl66CIIBNqVnOL_NR" 
recent_videos = get_recent_playlist_videos(API_KEY, DF_PLAYLIST_ID, num_days=7)
save_transcripts([
    (vid, f"dataframed_{date.split('T')[0]}.txt")
    for vid, date in recent_videos
])

# women in data
WID_PLAYLIST_ID = "PL4uU3uBIZarQYpepzylx2NSKx8bj9XrK6" 
recent_videos = get_recent_playlist_videos(API_KEY, WID_PLAYLIST_ID, num_days=20)
print(recent_videos)
save_transcripts([
    (vid, f"wid_{date.split('T')[0]}.txt")
    for vid, date in recent_videos
])