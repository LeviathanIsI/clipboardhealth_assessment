"""Thin CRM API client. GET helpers paginate fully; write helpers are used
ONLY by pipeline.executor (the single module allowed to modify the CRM)."""
import requests

from . import config


def _session():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {config.API_TOKEN}"})
    return s


class ApiClient:
    def __init__(self):
        self.session = _session()
        self.base = config.API_BASE.rstrip("/")

    # ---- reads -------------------------------------------------------------
    def list_all(self, resource, page_size=50):
        """Exhaustively page through a {data, page, page_size, total} listing."""
        out, page = [], 1
        while True:
            r = self.session.get(
                f"{self.base}/{resource}",
                params={"page": page, "page_size": page_size},
                timeout=30,
            )
            r.raise_for_status()
            body = r.json()
            data = body.get("data", [])
            out.extend(data)
            total = body.get("total", len(out))
            if len(out) >= total or not data:
                break
            page += 1
        return out

    def get_account(self, account_id):
        r = self.session.get(f"{self.base}/accounts/{account_id}", timeout=30)
        r.raise_for_status()
        return r.json()

    # ---- writes (executor only) -------------------------------------------
    def patch_account(self, account_id, body):
        r = self.session.patch(f"{self.base}/accounts/{account_id}", json=body, timeout=30)
        return r

    def create_account(self, body):
        r = self.session.post(f"{self.base}/accounts", json=body, timeout=30)
        return r

    def patch_contact(self, contact_id, body):
        r = self.session.patch(f"{self.base}/contacts/{contact_id}", json=body, timeout=30)
        return r
