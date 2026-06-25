"""Quick DB connectivity check."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env.local")

from supabase.culture_db import connect_culture_db, culture_db_backend
from supabase.members_auth import authenticate_member
from supabase.table_config import MEMBER_TABLE_NAME

try:
    conn = connect_culture_db()
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM public."{MEMBER_TABLE_NAME}"')
        n = cur.fetchone()[0]
    member = authenticate_member(conn, "culture01", "Pass01!culture")
    conn.close()
    print("backend:", culture_db_backend())
    print("members:", n, "auth:", "OK" if member else "FAIL")
except Exception as e:
    print("FAIL:", type(e).__name__, e)
    sys.exit(1)
