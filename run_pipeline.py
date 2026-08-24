"""CLI pipeline entry, called by the scheduler.

Scrapes the website, fetches full CRM state, runs matching/classification,
and stores proposals in SQLite. NEVER writes to the CRM — approvals happen
by hand in the review app, which invokes the executor.
"""
import json
import sys
import uuid
from datetime import datetime, timezone

import store
from pipeline import scrape as scrape_mod
from pipeline.api_client import ApiClient
from pipeline.match import run_match


def run(verbose=True):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:6]
    scraped = scrape_mod.scrape()
    for w in scraped["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)

    client = ApiClient()
    accounts = client.list_all("accounts")
    contacts = client.list_all("contacts")

    result = run_match(scraped["locations"], accounts, contacts)

    conn = store.connect()
    counts = store.upsert_proposals(conn, run_id, result["proposals"])
    summary = result["summary"]
    summary["run_id"] = run_id
    summary["scrape_warnings"] = scraped["warnings"]
    summary["homepage_only_slugs"] = scraped["homepage_only"]
    summary["store"] = counts
    store.record_run(conn, run_id, summary)
    conn.close()

    if verbose:
        print(json.dumps({
            "run_id": run_id,
            "brand_parent": summary["brand_parent"],
            "locations_scraped": summary["locations_scraped"],
            "accounts_total": summary["accounts_total"],
            "classification_counts": summary["classification_counts"],
            "proposals": counts,
            "confirmed": summary["confirmed"],
            "orphans": summary["orphans"],
            "homepage_only_slugs": summary["homepage_only_slugs"],
            "scrape_warnings": summary["scrape_warnings"],
        }, indent=2))
    return summary


if __name__ == "__main__":
    run()
