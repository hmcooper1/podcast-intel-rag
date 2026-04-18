import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client
from email_digest import send_email

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
DAYS_BACK = 7

def check_missing_fields():
    """
    Check that all episodes ingested this week have required fields in episode table.
    """
    # grab all episodes published in last week
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    result = supabase.table("episodes").select(
        "id, episode_title, podcast_name, published_date, description"
    ).gte("published_date", cutoff).execute()

    # track any relevant missing fields (that aren't hardcoded) in the episodes table
    issues = []
    for ep in result.data:
        if not ep.get("episode_title"):
            issues.append(f"  MISSING episode_title: episode id {ep['id']} ({ep['podcast_name']})")
        if not ep.get("published_date"):
            issues.append(f"  MISSING published_date: {ep['episode_title']} ({ep['podcast_name']})")
        if not ep.get("description"):
            issues.append(f"  MISSING description: {ep['episode_title']} ({ep['podcast_name']})")

    if issues:
        print("MISSING FIELDS:")
        for issue in issues:
            print(issue)
    else:
        print("  All episodes this week have required fields.")
    return issues

def check_episodes_have_chunks():
    """
    Check that every episode this week has at least one chunk in the chunks table.
    """
    # grab all episodes published in last week
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    episodes = supabase.table("episodes").select(
        "id, episode_title, podcast_name"
    ).gte("published_date", cutoff).execute()

    # check if any of the episodes have no chunks in the chunks table
    issues = []
    for ep in episodes.data:
        chunks = supabase.table("chunks").select("id").eq("episode_id", ep["id"]).limit(1).execute()
        if not chunks.data:
            issues.append(f"  NO CHUNKS: {ep['episode_title']} ({ep['podcast_name']})")

    if issues:
        print("EPISODES WITH NO CHUNKS:")
        for issue in issues:
            print(issue)
    else:
        print("  All episodes this week have chunks.")
    return issues

def run_all_checks():
    print("\n=== Data Quality Checks ===")
    all_issues = check_missing_fields() + check_episodes_have_chunks()

    # if any issues found, send an alert email in case I don't manually check logs that week
    if all_issues:
        body = "Data quality issues found in this week's pipeline run:\n\n" + "\n".join(all_issues)
        send_email(
            subject="Podcast Intel: Data Quality Issues",
            plain_body=body,
            html_body=f"<pre>{body}</pre>"
        )