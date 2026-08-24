"""Runtime configuration. Everything is env-overridable; nothing else is hardcoded."""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

API_BASE = os.environ.get(
    "BELLHAVEN_API_BASE",
    "https://analyst-assessment-production.up.railway.app/api/v1",
)
SITE_BASE = os.environ.get(
    "BELLHAVEN_SITE_BASE",
    "https://analyst-assessment-production.up.railway.app",
)
API_TOKEN = os.environ.get("BELLHAVEN_API_TOKEN", "bh_OcpnKK1KL6i2bcsahGQpJA")

DATA_DIR = os.environ.get("BELLHAVEN_DATA_DIR", os.path.join(REPO_ROOT, "data"))
DB_PATH = os.path.join(DATA_DIR, "sync.db")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "scrape_snapshot.json")

# Bot identity used as prefix for every note the executor writes.
BOT_TAG = "sync-bot"
