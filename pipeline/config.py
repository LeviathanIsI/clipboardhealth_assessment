"""Runtime configuration. Everything is env-overridable; nothing else is hardcoded."""
import os

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env from the repo root. load_dotenv never overrides variables already
# present in the real environment, so a shell export or the Actions secret
# always wins over the file.
load_dotenv(os.path.join(REPO_ROOT, ".env"))

API_BASE = os.environ.get(
    "BELLHAVEN_API_BASE",
    "https://analyst-assessment-production.up.railway.app/api/v1",
)
SITE_BASE = os.environ.get(
    "BELLHAVEN_SITE_BASE",
    "https://analyst-assessment-production.up.railway.app",
)
# Resolution order: real environment variable (shell export / Actions secret)
# first, then the repo-root .env loaded above. No token is hardcoded.
API_TOKEN = os.environ.get("CRM_API_TOKEN")
if not API_TOKEN:
    raise RuntimeError(
        "CRM_API_TOKEN is not set. Copy .env.example to .env at the repo "
        "root and paste your CRM token, or export CRM_API_TOKEN in the "
        "environment."
    )

DATA_DIR = os.environ.get("BELLHAVEN_DATA_DIR", os.path.join(REPO_ROOT, "data"))
DB_PATH = os.path.join(DATA_DIR, "sync.db")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "scrape_snapshot.json")

# Bot identity used as prefix for every note the executor writes.
BOT_TAG = "sync-bot"
