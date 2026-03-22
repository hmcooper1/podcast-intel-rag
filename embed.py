import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from podcasts import PODCASTS

load_dotenv(dotenv_path=".env")

# Config -----------------------------------------------------
TRANSCRIPTS_DIR = "transcripts"
METADATA_DIR = "metadata"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "text-embedding-3-small"
# ------------------------------------------------------------

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# build a lookup dict from podcast id > podcast metadata for easy access
PODCAST_LOOKUP = {p["id"]: p for p in PODCASTS}

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks of chunk_size words with chunk_overlap."""
    words = text.split()
    chunks = []
    step = chunk_size - overlap
 
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
 
    return chunks

def get_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI for a chunk of text."""
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding

def already_embedded(episode_title: str) -> bool:
    """Check if an episode has already been embedded in Supabase."""
    # supabase query: SELECT id FROM chunks WHERE episode_title = {episode_title} LIMIT 1
    result = supabase.table("chunks").select("id").eq("episode_title", episode_title).limit(1).execute()
    return len(result.data) > 0

def parse_filename(filename: str) -> tuple[str, str]:
    """
    Extract podcast_id and episode_title from filename.
    Filenames are formatted as: podcast_id__episode_title.txt
    """
    name = filename.replace(".txt", "")
    parts = name.split("__", 1)
    podcast_id = parts[0]
    episode_title = parts[1].replace("_", " ") if len(parts) > 1 else name
    return podcast_id, episode_title

def embed_transcript(filename: str):
    """Chunk, embed, and store a single transcript in Supabase."""
    podcast_id, episode_title = parse_filename(filename)
 
    if already_embedded(episode_title):
        print(f"  Already embedded, skipping: {episode_title}")
        return
 
    # get podcast metadata from lookup
    podcast = PODCAST_LOOKUP.get(podcast_id)
    if not podcast:
        print(f"  Unknown podcast id: {podcast_id}, skipping")
        return
    
    # read metadata file for episode to get published date and duration (if exists)
    metadata_filename = filename.replace(".txt", ".json")
    metadata_path = os.path.join(METADATA_DIR, metadata_filename)
    published_date = None
    duration_seconds = None

    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        published_date = metadata.get("published_date")
        duration_seconds = metadata.get("duration_seconds")
    else:
        print(f"  No metadata found for {filename}")
 
    # read transcript
    filepath = os.path.join(TRANSCRIPTS_DIR, filename)
    with open(filepath, "r") as f:
        text = f.read()
 
    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    print(f"  Split into {len(chunks)} chunks")
 
    # embed each chunk and store in Supabase
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
 
        supabase.table("chunks").insert({
            "podcast_id": podcast_id,
            "podcast_name": podcast["name"],
            "category": podcast["category"],
            "episode_title": episode_title,
            "published_date": published_date,
            "episode_duration": duration_seconds,
            "chunk_index": i,
            "chunk_text": chunk,
            "embedding": embedding,
        }).execute()
 
    print(f"  Embedded and stored {len(chunks)} chunks")

    # clean up local files — everything is now in supabase
    os.remove(filepath)
    print(f"  Deleted transcript: {filepath}")
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
        print(f"  Deleted metadata: {metadata_path}")

def main():
    txt_files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith(".txt")]
    print(f"Found {len(txt_files)} transcripts in '{TRANSCRIPTS_DIR}/'\n")

    for filename in txt_files:
        print(f"Episode: {filename}")
        embed_transcript(filename)
    
    print("\nDone!")
 
if __name__ == "__main__":
    main()