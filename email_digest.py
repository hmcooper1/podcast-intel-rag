import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from preferences import USER_PREFERENCES, SEARCH_QUERIES
# simple mail transfer protocol library for sending emails
import smtplib
# email structure libraries for formatting the email content
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
DAYS_BACK = 7
TOP_N_EPISODES = 3
CHUNKS_PER_QUERY = 10   # chunks to retrieve per search query
TOP_EPISODES_TO_LLM = 6 # top scoring episodes to send to LLM
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o"
# ────────────────────────────────────────────────────────────────────────────
 
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI for a chunk of text."""
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding

def search_query(query: str, limit: int = 10) -> list[dict]:
    """
    Embed a single query string and find the most similar chunks in Supabase.
    Total chunks returned is determined by the 'limit' parameter.
    Returns a list of chunk dicts with id, episode_title, podcast_name etc.
    """
    embedding = get_embedding(query)
    result = supabase.rpc("match_chunks", {
        "query_embedding": embedding,
        "match_count": limit
    }).execute()
    return result.data
 
def search_all_queries(queries: list[str]) -> list[dict]:
    """
    Run each search query and combine results into one deduplicated list.
    If the same chunk appears for multiple queries, keeps the highest weight.
    Returns a list of chunk dicts with id, episode_title, podcast_name, weight etc.
    """
    # use dict keyed by chunk id to easily find and update duplicates
    chunks_by_id = {}

    # for each query, get matching chunks and add to dict, keeping highest weight if duplicate
    for query, weight in queries:
        chunks = search_query(query, CHUNKS_PER_QUERY)
        for chunk in chunks:
            cid = chunk["id"]
            if cid not in chunks_by_id:
                # first time seeing this chunk — store it with its weight
                chunk["weight"] = weight
                chunks_by_id[cid] = chunk
            else:
                # chunk already seen from another query — keep the higher weight
                chunks_by_id[cid]["weight"] = max(chunks_by_id[cid]["weight"], weight)

    return list(chunks_by_id.values())

def score_episodes(chunks: list[dict]) -> dict:
    """
    Count how many relevant chunks each episode contributed.
    Returns a dict sorted by score (highest first), each entry containing 
    the score, podcast name, and matched excerpts.
    """
    # dict of dicts: episode_title > {score, podcast_name, excerpts}
    episodes = {}
 
    # for each chunk, add to the episode's score and save an excerpt (up to 300 chars) for context
    for chunk in chunks:
        title = chunk["episode_title"]
        if title not in episodes:
            episodes[title] = {
                "score": 0,
                "podcast_name": chunk.get("podcast_name", ""),
                "excerpts": []
            }
        episodes[title]["score"] += chunk.get("weight", 1.0)
        episodes[title]["excerpts"].append(chunk["chunk_text"][:300])
 
    # convert dict to (key, value) pairs, sort by score, and convert back to dict
    return dict(sorted(episodes.items(), key=lambda x: x[1]["score"], reverse=True))

def get_all_episodes() -> dict:
    """Fetch all distinct episodes from the past DAYS_BACK days from Supabase."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    result = supabase.table("chunks").select(
        "episode_title, podcast_name"
    ).gte("published_date", cutoff).execute()
    
    # deduplicate by episode title
    episodes = {}
    for row in result.data:
        title = row["episode_title"]
        if title not in episodes:
            episodes[title] = row["podcast_name"]
    
    return episodes

def get_top_episode_recommendations(episodes: dict, preferences: str) -> str:
    """
    Take the top scoring episodes and ask GPT-4o to pick the best 3.
    Sends each episode's score and excerpts along with the user's preferences
    so the LLM can make a personalised, specific recommendation.
    """
    # get the top N episodes to send to the LLM, based on score (number of matching chunks)
    top_episodes = dict(list(episodes.items())[:TOP_EPISODES_TO_LLM])
 
    episodes_text = "\n\n---\n\n".join([
        f"Podcast: {v['podcast_name']}\n"
        f"Episode: {k}\n"
        f"Relevance score: {v['score']} matching chunks\n"
        f"Excerpts:\n" +
        "\n".join([f"- {e}" for e in v["excerpts"][:3]])
        # k: podcast episode title, v: dict with podcast name, score, and excerpts
        for k, v in top_episodes.items()
    ])
 
    prompt = f"""You are a personalized podcast recommendation engine.
 
Here are the user's interests and preferences:
{preferences}
 
Below are the most relevant podcast episodes this week, ranked by how many
chunks matched the user's interests. Each episode shows its relevance score
and excerpts from the matching chunks.
 
Select the top {TOP_N_EPISODES} episodes most valuable for this user.
For each, explain SPECIFICALLY why it matches their interests — reference
both the episode content AND their stated preferences.
 
When selecting the top {TOP_N_EPISODES} episodes, prioritize in this order:
1. Early career / breaking into AI engineering
2. Biotech, pharma, or health and AI intersection
3. Practical AI tools and workflows
4. AI agents and deployment (only if nothing better matches above)

Format each recommendation exactly like this example:
#1. Episode Title (The AI Daily Brief)
Why this is for you: ...
What you'll take away: ...

Use the actual podcast name from the "Podcast:" field in each episode's data above.
 
Episodes:
{episodes_text}"""
 
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def send_email(subject: str, body: str):
    """Send the digest as an email to yourself via Gmail SMTP."""
    gmail_address = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    # create email envelope (from, to, subject header)
    msg = MIMEMultipart()
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg["Subject"] = subject

    # create plain body part and attach to email
    msg.attach(MIMEText(body, "plain"))

    # connect to gmail's server with SSL (to encrypt) and send the email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, gmail_address, msg.as_string())

    print(f"Email sent to {gmail_address}!")

def generate_digest():
    """
    Run the full recommendation pipeline and send as email.
 
    Workflow:
    1. Run multi-query search to find relevant chunks
    2. Score episodes by chunk count (weighted by priority)
    3. Ask LLM to pick top 3 (send top 6) and explain why
    4. Build episode list (scored + unscored)
    5. Combine into digest string and email it
    """
    week_of = datetime.now().strftime("%B %d, %Y")
    
    # 1: run all search queries and collect chunks
    print(f"Running {len(SEARCH_QUERIES)} preference searches...\n")
    all_chunks = search_all_queries(SEARCH_QUERIES)
    print(f"Found {len(all_chunks)} unique relevant chunks\n")

    # 2: score episodes by how many chunks matched
    print("Scoring episodes...")
    scored_episodes = score_episodes(all_chunks)
    for title, data in list(scored_episodes.items())[:TOP_EPISODES_TO_LLM]:
        print(f"  {data['score']} chunks — {title[:60]}")
    print()

    # 3: ask LLM to pick top 3 from highest scoring episodes (6)
    print("Generating recommendations...")
    recommendations = get_top_episode_recommendations(scored_episodes, USER_PREFERENCES)

    # 4: build full episode list - scored first (in order), then unscored at the bottom
    all_episodes = get_all_episodes()
    episode_list = ""
    for i, (title, data) in enumerate(scored_episodes.items(), start=1):
        episode_list += f"{i}. {title} ({data['podcast_name']})\n"
    # unscored episodes had no chunks match any query
    unscored = [t for t in all_episodes if t not in scored_episodes]
    for title in unscored:
        episode_list += f"- {title} ({all_episodes[title]})\n"

    # 5: build full digest string
    digest = f"""
=====================================
PODCAST INTEL DIGEST - {week_of}
=====================================

TOP {TOP_N_EPISODES} EPISODES FOR YOU THIS WEEK
-------------------------------------
{recommendations}

ALL EPISODES THIS WEEK (by relevance)
-------------------------------------
{episode_list}
=====================================
"""

    print(digest)
    send_email(subject=f"Podcast Intel Digest — {week_of}", body=digest)

if __name__ == "__main__":
    generate_digest()