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

# Config -----------------------------------------------------
DAYS_BACK = 7
TOP_N_EPISODES = 3
CHUNKS_PER_QUERY = 10   # chunks to retrieve per search query
TOP_EPISODES_TO_LLM = 6 # top scoring episodes to send to LLM
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o"
# ------------------------------------------------------------
 
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
    """Fetch all distinct episodes from the past DAYS_BACK days from the episodes table."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    result = supabase.table("episodes").select(
        "episode_title, podcast_name"
    ).gte("published_date", cutoff).execute()

    # episodes table has one row per episode so no deduplication needed
    return {row["episode_title"]: row["podcast_name"] for row in result.data}

def get_top_episode_recommendations(episodes: dict, preferences: str) -> str:
    """
    Take the top scoring episodes and ask GPT-4o to pick the best 3.
    Sends each episode's score and excerpts along with the my preferences
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
 
Select the top {TOP_N_EPISODES} DISTINCT episodes most valuable for this user
Do not recommend the same episode more than once.
Do not recommend two episodes from the same podcast if one of them is already in the top {TOP_N_EPISODES}, unless there are not enough distinct podcasts in the list.
For each, explain SPECIFICALLY why it matches their interests — reference
both the episode content AND their stated preferences.
 
When selecting the top {TOP_N_EPISODES} episodes, prioritize in this order:
1. Early career / breaking into AI engineering
2. Biotech, pharma, or health and AI intersection
3. Practical AI tools and workflows
4. AI agents and deployment (only if nothing better matches above)

Format each recommendation exactly like this example — no extra labels, no deviations (replace "Episode Title" with the actual episode title):
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

def render_rec_block(block: dict) -> str:
    """
    Helper: turns one recommendation dict into an HTML card string for build_html_email.
    """
    return (
        # border left: purple stripe on the left
        f'<div style="background:#f9f9f9;border-left:4px solid #6c63ff;'
        # space inside the card and between cards, rounded corners on right
        f'padding:16px 20px;margin-bottom:16px;border-radius:0 8px 8px 0;">'
        # episode number + title
        f'<div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:10px;">{block["title"]}</div>'
        # "why" line - span labels "what you'll take away" in purple, rest in dark grey
        f'<div style="font-size:14px;color:#444;margin-bottom:6px;">'
        f'<span style="font-weight:600;color:#6c63ff;">Why this is for you:</span> {block["why"]}</div>'
        # "takeaway" line
        f'<div style="font-size:14px;color:#444;">'
        f'<span style="font-weight:600;color:#6c63ff;">What you\'ll take away:</span> {block["takeaway"]}</div>'
        f'</div>'
    )

def build_html_email(week_of: str, recommendations: str, episode_list: str) -> str:
    """
    Convert the digest content into a pretty HTML email string.
    Takes the three main pieces of content already built in
    generate_digest() and wraps them in HTML/CSS.
    """

    # ------------------------------------------------------------
    # 1: parse the recommendations string into structured blocks
    # the LLM returns recommendations as plain text like:
    #   #1. Episode Title (Podcast Name)
    #   Why this is for you: ...
    #   What you'll take away: ...
    # split response into pieces so to style each part separately

    rec_blocks_html = ""
    # build each recommendation as a dict with title, why, and takeaway
    current = {"title": "", "why": "", "takeaway": ""}

    # split recommendations into lines (recieve plain text with newlines)
    for line in recommendations.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        
        # 1: new episode recommendation (starts with #1., #2., etc.)
        if line.startswith("#"):
            if current["title"]:
                # turn previous block into HTML and add to the full recommendations HTML
                rec_blocks_html += render_rec_block(current)
            # if no title is set (first episode), start a new block
            current = {"title": line, "why": "", "takeaway": ""}

        # 2: "why" line
        elif line.lower().startswith("why this is for you:"):
            current["why"] = line[len("why this is for you:"):].strip()

        # 3: "takeaway" line
        elif line.lower().startswith("what you'll take away:"):
            current["takeaway"] = line[len("what you'll take away:"):].strip()

    # add the last block to the HTML
    if current["title"]:
        rec_blocks_html += render_rec_block(current)

    # ------------------------------------------------------------
    # 2: build the episode list rows as HTML
    # scored episodes are "1. Title (Podcast)", unscored are "- Title (Podcast)"

    ep_rows_html = ""
    for line in episode_list.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # scored episode (starts with #) - pull out the number and the rest of the line
        if line[0].isdigit():
            num, _, rest = line.partition(". ")
            # all combines to one HTML string with two columns: number and episode title
            ep_rows_html += (
                # tr: table row, td: table data - each ep is one row with two cells (number and title)
                f'<tr>'
                f'<td style="padding:8px 12px;color:#6c63ff;font-weight:700;width:28px;vertical-align:top;">{num}</td>'
                f'<td style="padding:8px 12px;color:#333;font-size:14px;">{rest}</td>'
                f'</tr>'
            )
        # unscored episode — shown dimmed and italic at the bottom
        else:
            rest = line.lstrip("- ")
            # all combines to one HTML string with two columns: dash and episode title
            ep_rows_html += (
                f'<tr>'
                f'<td style="padding:8px 12px;color:#ccc;width:28px;vertical-align:top;">—</td>'
                f'<td style="padding:8px 12px;color:#999;font-size:13px;font-style:italic;">{rest}</td>'
                f'</tr>'
            )

    # ------------------------------------------------------------
    # 3: create the full HTML document
    # use <table> tags instead of <div> tags to be safer for email clients

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <!-- tells mobile clients to render at device width, not zooming out -->
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>

<!-- fonts: tries helvetica neue first, then helvetica, then arial -->
<body style="margin:0;padding:0;background:#ffffff;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">

  <!-- outer table just centers the 600px content column -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;">
    <tr><td align="center">

      <!-- main content column, 600px wide (standard email width) -->
      <table width="600" cellpadding="0" cellspacing="0">

        <!-- ── HEADER ── -->
        <tr>
          <td style="background:#6c63ff;padding:36px 40px;text-align:center;">
            <!-- small all caps label at the top: PODCAST INTEL -->
            <div style="font-size:13px;font-weight:600;color:rgba(255,255,255,0.75);letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">Podcast Intel</div>
            <!-- main title: font-weight: thinner than normal -->
            <div style="font-size:28px;font-weight:300;color:#ffffff;letter-spacing:1px;">Your Weekly Digest</div>
            <!-- date subtitle -->
            <div style="font-size:13px;color:rgba(255,255,255,0.7);margin-top:8px;letter-spacing:1px;">{week_of}</div>
          </td>
        </tr>

        <!-- ── TOP PICKS ── -->
        <tr>
          <td style="padding:32px 40px 8px;">
            <!-- section label: top 3 picks for you -->
            <div style="font-size:11px;font-weight:700;color:#6c63ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:20px;">Top {TOP_N_EPISODES} picks for you</div>
            <!-- recommendation cards injected here -->
            {rec_blocks_html}
          </td>
        </tr>

        <!-- ── ALL EPISODES ── -->
        <tr>
          <td style="padding:8px 40px 36px;">
            <div style="font-size:11px;font-weight:700;color:#6c63ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;">All episodes this week</div>
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
              <tbody>
                {ep_rows_html}
              </tbody>
            </table>
          </td>
        </tr>

        <!-- ── FOOTER ── -->
        <tr>
          <td style="border-top:1px solid #eee;padding:20px 40px;text-align:center;">
            <div style="font-size:12px;color:#bbb;">Generated by Hannah Cooper &nbsp;|&nbsp; {week_of}</div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>

</body>
</html>"""


def send_email(subject: str, plain_body: str, html_body: str):
    """Send the digest as an email to yourself via Gmail SMTP."""
    gmail_address = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    # multipart/alternative means the email contains two versions of the same content
    # the email client picks whichever it can render (HTML if it can, plain text if not)
    msg = MIMEMultipart("alternative")
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg["Subject"] = subject

    # plain text attached first bc email clients use the last attachment they support
    # HTML goes second and will be preferred if client can render it
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

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

    # 5: build full digest string (backup in case HTML cannot render)
    digest = f"""
=====================================
PODCAST INTEL DIGEST: {week_of}
=====================================

TOP {TOP_N_EPISODES} EPISODES FOR YOU THIS WEEK
-------------------------------------
{recommendations}

ALL EPISODES THIS WEEK (by relevance)
-------------------------------------
{episode_list}
=====================================
"""

    # build the styled HTML version and send both (email client picks whichever it supports)
    html_digest = build_html_email(week_of, recommendations, episode_list)
    send_email(subject=f"Podcast Intel Digest for {week_of}", plain_body=digest, html_body=html_digest)

if __name__ == "__main__":
    generate_digest()