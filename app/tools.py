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
