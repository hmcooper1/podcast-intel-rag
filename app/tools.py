import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

EMBEDDING_MODEL = "text-embedding-3-small"

def semantic_search(query: str, match_count: int = 5) -> list[dict]:
    """Embed a query and return the most similar transcript chunks from Supabase."""
    embedding = openai_client.embeddings.create(
        input=query,
        model=EMBEDDING_MODEL,
    ).data[0].embedding

    result = supabase.rpc("match_chunks", {
        "query_embedding": embedding,
        "match_count": match_count,
    }).execute()

    return result.data

def list_podcasts() -> list[str]:
    """Return a list of all unique podcast names in the database."""
    result = supabase.table("episodes").select("podcast_name").execute()
    seen = set()
    podcasts = []
    for row in result.data:
        if row["podcast_name"] not in seen:
            seen.add(row["podcast_name"])
            podcasts.append(row["podcast_name"])
    return sorted(podcasts)

def get_episodes(podcast_name: str, limit: int = 5) -> list[dict]:
    """Return the most recent episodes from a specific podcast."""
    result = (
        supabase.table("episodes")
        .select("episode_title, podcast_name, published_date, description")
        .ilike("podcast_name", f"%{podcast_name}%")
        .order("published_date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data
