import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from preferences import USER_PREFERENCES

load_dotenv()