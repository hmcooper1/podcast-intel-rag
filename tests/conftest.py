import os

# Set dummy env variables
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("SUPABASE_URL", "https://abcdefghijklmnop.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key-not-real")
os.environ.setdefault("GMAIL_ADDRESS", "test@example.com")
os.environ.setdefault("GMAIL_APP_PASSWORD", "test-password")