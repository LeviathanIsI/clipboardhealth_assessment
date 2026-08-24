"""Executor — the ONLY module that writes to the CRM.

Runs a proposal's stored operations in order, capturing created ids so
sequenced steps (CHOW create-then-link) can reference them via the
"{new_id}" placeholder. Notes are prefixed "[sync-bot YYYY-MM-DD]" and are
APPENDED to any existing note content, never overwritten. On API error the
proposal is marked failed with the response body; no automatic retry.
"""
from datetime import date

from . import config
from .api_client import ApiClient


def _note_line(text):
    return f"[{config.BOT_TAG} {date.today().isoformat()}] {text}"


def _resolve(value, captures):
    if isinstance(value, str):
        for key, cap in captures.items():
            value = value.replace("{" + key + "}", str(cap))
    return value


def _resolve_body(body, captures):
    return {k: _resolve(v, captures) for k, v in body.items()}


def _extract_id(payload, key):
    """Pull an id out of a create response, tolerating {data: {...}} wrappers."""
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        data = payload.get("data")
        if isinstance(data, dict) and key in data:
            return data[key]
    return None


def apply_proposal(proposal):
    """Execute proposal['payload'] ops in order.

    Returns (ok, results) where results is a list of per-op dicts recording
    request + response; on the first failure execution stops.
    """
    client = ApiClient()
    captures = {}
    results = []

    for op in proposal["payload"]:
        kind = op["op"]
        try:
            if kind == "create_account":
                body = _resolve_body(op["body"], captures)
                if op.get("set_note"):
                    body["note"] = _note_line(_resolve(op["set_note"], captures))
                resp = client.create_account(body)
                entry = {"op": kind, "request": body,
                         "status_code": resp.status_code, "response": _safe(resp)}
                results.append(entry)
                if not resp.ok:
                    return False, results
                if op.get("capture"):
                    new_id = _extract_id(entry["response"], "account_id")
                    if not new_id:
                        entry["error"] = "could not extract account_id from response"
                        return False, results
                    captures[op["capture"]] = new_id

            elif kind == "patch_account":
                account_id = _resolve(op["account_id"], captures)
                body = _resolve_body(op["body"], captures)
                if op.get("append_note"):
                    current = client.get_account(account_id)
                    existing = current.get("note") or ""
                    line = _note_line(_resolve(op["append_note"], captures))
                    body["note"] = (existing + "\n" if existing else "") + line
                resp = client.patch_account(account_id, body)
                results.append({"op": kind, "account_id": account_id,
                                "request": body, "status_code": resp.status_code,
                                "response": _safe(resp)})
                if not resp.ok:
                    return False, results

            elif kind == "patch_contact":
                contact_id = _resolve(op["contact_id"], captures)
                body = _resolve_body(op["body"], captures)
                resp = client.patch_contact(contact_id, body)
                results.append({"op": kind, "contact_id": contact_id,
                                "request": body, "status_code": resp.status_code,
                                "response": _safe(resp)})
                if not resp.ok:
                    return False, results

            else:
                results.append({"op": kind, "error": "unknown op"})
                return False, results

        except Exception as exc:  # network/parse failure: record, stop, no retry
            results.append({"op": kind, "error": str(exc)})
            return False, results

    return True, results


def _safe(resp):
    try:
        return resp.json()
    except ValueError:
        return {"text": resp.text[:2000]}
