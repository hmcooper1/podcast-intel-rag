from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
import os

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def search(query: str, limit: int = 3):
    # embed the query
    response = openai_client.embeddings.create(
        input=query,
        model="text-embedding-3-small"
    )
    query_embedding = response.data[0].embedding

    # search supabase - rpc: remote proceudre call to function in supabase
    result = supabase.rpc("match_chunks", {
        "query_embedding": query_embedding,
        "match_count": limit
    }).execute()

    return result.data

results = search("what are people saying about AI agents?")
for r in results:
    print(r["podcast_id"], "-", r["episode_title"])
    print(r["chunk_text"][:200])
    print()