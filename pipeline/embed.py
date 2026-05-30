import os
import re
import json
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from .podcasts import PODCASTS

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

AD_PATTERNS = re.compile("|".join([
    r"brought to you by",
    r"today'?s sponsor",
    r"sponsored by",
    r"use code\s+\w+",
    r"head to\s+\S+\.(com|ai|io)",
    r"\S+\.(com|ai|io)\s+slash",
    r"www\.\S+",
    r"\d+%\s*off",
    r"first\s+(three|3)\s+months?\s+free",
    r"check out\s+\S+\.(com|ai|io)",
]), re.IGNORECASE)

def clean_transcript(text: str) -> str:
    """Remove sponsor/ad sentences from transcript text before chunking."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    clean = [s for s in sentences if not AD_PATTERNS.search(s)]
    removed = len(sentences) - len(clean)
    if removed > 0:
        print(f"  Removed {removed} ad sentence(s) from transcript")
    return " ".join(clean)

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

def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embedding vectors from OpenAI for a list of texts in one API call."""
    response = openai_client.embeddings.create(
        input=texts,
        model=EMBEDDING_MODEL
    )
    return [r.embedding for r in response.data]

def already_embedded(episode_title: str) -> bool:
    """Check if an episode has already been embedded by looking it up in the episodes table.
    If a row exists in episodes, chunks were already inserted for it.
    """
    result = supabase.table("episodes").select("id").eq("episode_title", episode_title).limit(1).execute()
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

    description = None
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        published_date = metadata.get("published_date")
        duration_seconds = metadata.get("duration_seconds")
        description = metadata.get("description")
    else:
        print(f"  No metadata found for {filename}")

    # insert episode into episodes table, get back the id
    episode_row = supabase.table("episodes").insert({
        "podcast_id": podcast_id,
        "podcast_name": podcast["name"],
        "category": podcast["category"],
        "episode_title": episode_title,
        "published_date": published_date,
        "duration_seconds": duration_seconds,
        "description": description,
    }).execute()
    episode_id = episode_row.data[0]["id"]

    # read transcript
    filepath = os.path.join(TRANSCRIPTS_DIR, filename)
    with open(filepath, "r") as f:
        text = f.read()

    text = clean_transcript(text)
    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    print(f"  Split into {len(chunks)} chunks")

    # embed all chunks per ep in one API call, then store in Supabase
    embeddings = get_embeddings(chunks)
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        # only store chunk-specific data — episode metadata lives in the episodes table
        supabase.table("chunks").insert({
            "episode_id": episode_id,
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