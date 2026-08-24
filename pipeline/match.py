"""Matching + classification. Pure: takes scraped locations + full CRM state,
emits proposals. Never talks to the network. Every decision is a generic rule
computed at runtime — no account ids, facility names, or per-record special
cases appear here.

Classifications
  CONFIRMED  matched account, already under the Bellhaven parent, name matches.
  NEEDS_FIX  matched account with name drift and/or wrong/missing parent.
  MISSING    no account matches with a strong signal -> propose create.
  ORPHANED   Active Bellhaven-parent account matching no website location.

Matching signals
  strong        address key equal (street+city+state)
  strong (PO)   name key equal + same city/state, when the CRM street is a
                PO Box / empty and therefore cannot address-match
  medium        name key equal (same city/state only — never across cities)
  corroborating website administrator matches a CRM contact on the account;
                phone digits equal
"""
import hashlib
import json

from .normalize import (
    address_key, city_key, has_usable_street, name_key, name_tokens,
    person_key, phone_key, state_key,
)

PARENT_MARKER = "(parent account)"
BRAND_TOKEN = "bellhaven"  # derived from the operator whose website we sync

# Website care-offering vocabulary -> CRM care_type vocabulary (keyed by name_key).
CARE_TYPE_MAP = {
    "short term rehab nursing": "Skilled Nursing",
    "skilled nursing": "Skilled Nursing",
    "memory support": "Memory Care",
    "memory care": "Memory Care",
    "assisted living": "Assisted Living",
    "independent living": "Independent Living",
}


def _care_type_for(offerings):
    for off in offerings or []:
        mapped = CARE_TYPE_MAP.get(name_key(off))
        if mapped:
            return mapped
    return ""


def _loc_key(city, state):
    return (city_key(city), state_key(state))


def _proposal_id(ptype, target, ops):
    canon = json.dumps({"type": ptype, "target": target, "ops": ops}, sort_keys=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _mk_proposal(ptype, target, classification, tier, ops, changes, evidence):
    return {
        "proposal_id": _proposal_id(ptype, target, ops),
        "type": ptype,
        "target": target,
        "classification": classification,
        "tier": tier,
        "payload": ops,
        "changes": changes,
        "evidence": evidence,
    }


def find_brand_parent(accounts):
    """Locate the Bellhaven parent account at runtime by name pattern only."""
    parents = [a for a in accounts if PARENT_MARKER in (a.get("name") or "").lower()]
    brand = [p for p in parents if BRAND_TOKEN in name_key(p.get("name"))]
    if len(brand) != 1:
        raise RuntimeError(
            f"Expected exactly one '{BRAND_TOKEN}' parent account, found "
            f"{[p.get('name') for p in brand]}"
        )
    return brand[0], parents


def _candidate(loc, acct, contacts_by_account, loc_addr_key):
    acct_street = acct.get("billing_street") or ""
    addr_match = bool(
        loc_addr_key
        and has_usable_street(acct_street)
        and address_key(acct_street) == loc_addr_key
    )
    nm_match = name_key(acct.get("name")) == name_key(loc["name"])
    po_fallback = nm_match and not has_usable_street(acct_street)
    admin = person_key(loc.get("administrator"))
    contact_match = bool(admin) and any(
        person_key(c.get("name")) == admin
        for c in contacts_by_account.get(acct["account_id"], [])
    )
    ph_match = bool(phone_key(loc.get("phone"))) and phone_key(
        loc.get("phone")
    ) == phone_key(acct.get("phone"))
    return {
        "account": acct,
        "addr_match": addr_match,
        "name_match": nm_match,
        "po_fallback": po_fallback,
        "contact_match": contact_match,
        "phone_match": ph_match,
        "is_match": addr_match or po_fallback,
    }


def _rank_key(cand, brand_parent_id):
    a = cand["account"]
    return (
        cand["addr_match"],
        cand["name_match"],
        cand["contact_match"],
        cand["phone_match"],
        a.get("parent_id") == brand_parent_id,
        (a.get("lifetime_revenue") or 0) > 0,
        a.get("status") == "Active",
        a["account_id"],  # deterministic tie-break
    )


def _signals_text(cand):
    parts = []
    if cand["addr_match"]:
        parts.append("address match")
    if cand["po_fallback"]:
        parts.append("name match with PO-Box/blank CRM street (fallback)")
    elif cand["name_match"]:
        parts.append("name match")
    if cand["contact_match"]:
        parts.append("administrator matches CRM contact")
    if cand["phone_match"]:
        parts.append("phone match")
    return ", ".join(parts) or "no signals"


def _chow_locked(acct):
    return (acct.get("lifetime_revenue") or 0) > 0 and (
        acct.get("outstanding_ar") or 0
    ) > 0


def _acct_summary(a):
    return {
        "account_id": a["account_id"],
        "name": a.get("name"),
        "parent_name": a.get("parent_name"),
        "address": f"{a.get('billing_street')}, {a.get('billing_city')}, "
                   f"{a.get('billing_state')} {a.get('billing_zip')}",
        "status": a.get("status"),
        "lifetime_revenue": a.get("lifetime_revenue"),
        "outstanding_ar": a.get("outstanding_ar"),
    }


def _loc_summary(loc):
    return {
        "slug": loc["slug"],
        "name": loc["name"],
        "address": f"{loc['address']}, {loc['city']}, {loc['state']} {loc['zip']}",
        "administrator": loc.get("administrator"),
        "url": loc.get("url"),
        "homepage_only": loc.get("homepage_only", False),
    }


def _create_body(loc, brand_parent):
    return {
        "name": loc["name"],
        "parent_id": brand_parent["account_id"],
        "billing_street": loc["address"],
        "billing_city": loc["city"],
        "billing_state": loc["state"],
        "billing_zip": loc["zip"],
        "care_type": _care_type_for(loc.get("care_offerings")),
        "phone": loc.get("phone") or "",
        "status": "Active",
    }


def run_match(locations, accounts, contacts):
    brand_parent, parents = find_brand_parent(accounts)
    brand_id = brand_parent["account_id"]
    parent_ids = {p["account_id"] for p in parents}

    # Accounts already resolved by a prior CHOW or duplicate merge are
    # superseded records: never match, re-flag, or orphan them again.
    superseded = [
        a for a in accounts
        if a.get("chow_current_account") or a.get("duplicate_of_account")
    ]
    superseded_ids = {a["account_id"] for a in superseded}
    facilities = [
        a for a in accounts
        if a["account_id"] not in parent_ids and a["account_id"] not in superseded_ids
    ]

    contacts_by_account = {}
    for c in contacts:
        contacts_by_account.setdefault(c.get("account_id"), []).append(c)

    facilities_by_cs = {}
    for a in facilities:
        facilities_by_cs.setdefault(
            _loc_key(a.get("billing_city"), a.get("billing_state")), []
        ).append(a)

    proposals, confirmed, classifications = [], [], {}
    matched_account_ids = set()  # any account that matched any location
    duplicate_loser_ids = set()

    for loc in locations:
        if not loc.get("city") or not loc.get("state"):
            classifications[loc["slug"]] = {
                "classification": "UNPARSEABLE",
                "detail": "missing city/state; cannot match",
            }
            continue
        loc_addr = address_key(loc["address"]) if loc.get("address") else None
        local_accts = facilities_by_cs.get(_loc_key(loc["city"], loc["state"]), [])
        cands = [
            _candidate(loc, a, contacts_by_account, loc_addr) for a in local_accts
        ]
        matches = [c for c in cands if c["is_match"]]

        # Near-miss + collision evidence (never a match by themselves).
        near_misses = [
            {
                "account": _acct_summary(c["account"]),
                "shared_name_tokens": sorted(
                    name_tokens(loc["name"]) & name_tokens(c["account"].get("name"))
                ),
            }
            for c in cands
            if not c["is_match"]
            and len(name_tokens(loc["name"]) & name_tokens(c["account"].get("name"))) >= 2
        ]
        name_collisions_elsewhere = [
            _acct_summary(a)
            for a in facilities
            if name_key(a.get("name")) == name_key(loc["name"])
            and _loc_key(a.get("billing_city"), a.get("billing_state"))
            != _loc_key(loc["city"], loc["state"])
        ]

        if not matches:
            # ---- MISSING: propose create under the brand parent ------------
            tier = "LOW" if near_misses else "MEDIUM"
            body = _create_body(loc, brand_parent)
            reason = (
                f"Community listed on website ({loc['url']}) with no CRM account "
                f"matching by address or name in {loc['city']}, {loc['state']}."
            )
            ops = [{"op": "create_account", "body": body, "set_note": reason}]
            changes = [
                {"entity": "account", "id": "(new)", "field": k, "before": "", "after": v}
                for k, v in body.items()
            ]
            evidence = {
                "location": _loc_summary(loc),
                "signals": "no strong match in city/state",
                "near_misses": near_misses,
                "name_collisions_in_other_cities": name_collisions_elsewhere,
                "human": [reason]
                + [
                    "NEAR MISS (not a match — same city, different street, "
                    f"shared tokens {nm['shared_name_tokens']}): "
                    f"{nm['account']['name']} [{nm['account']['account_id']}] "
                    f"at {nm['account']['address']}"
                    for nm in near_misses
                ]
                + [
                    "CAUTION name collision in another city (different facility): "
                    f"{a['name']} [{a['account_id']}] at {a['address']}"
                    for a in name_collisions_elsewhere
                ],
            }
            proposals.append(
                _mk_proposal("CREATE_ACCOUNT", loc["slug"], "MISSING", tier, ops,
                             changes, evidence)
            )
            classifications[loc["slug"]] = {"classification": "MISSING"}
            continue

        matches.sort(key=lambda c: _rank_key(c, brand_id), reverse=True)
        winner = matches[0]
        acct = winner["account"]
        for m in matches:
            matched_account_ids.add(m["account"]["account_id"])

        # ---- duplicates: >=2 accounts share this website address key -------
        addr_set = [
            a for a in local_accts
            if loc_addr
            and has_usable_street(a.get("billing_street"))
            and address_key(a.get("billing_street")) == loc_addr
        ]
        if len(addr_set) > 1:
            survivor = acct  # ranking above already encodes survivor preference
            for loser in addr_set:
                if loser["account_id"] == survivor["account_id"]:
                    continue
                duplicate_loser_ids.add(loser["account_id"])
                if loser.get("duplicate_of_account"):
                    continue  # already resolved in CRM
                fields = {"duplicate_of_account": survivor["account_id"]}
                if loser.get("status") != "Inactive":
                    fields["status"] = "Inactive"
                reason = (
                    f"Duplicate of {survivor['name']} [{survivor['account_id']}] — "
                    f"same address ({loc['address']}, {loc['city']}, {loc['state']}). "
                    f"Survivor corroborated by website listing "
                    f"({_signals_text(winner)})."
                )
                ops = [
                    {
                        "op": "patch_account",
                        "account_id": loser["account_id"],
                        "body": fields,
                        "append_note": reason,
                    }
                ]
                changes = [
                    {"entity": "account", "id": loser["account_id"], "field": k,
                     "before": loser.get(k, ""), "after": v}
                    for k, v in fields.items()
                ]
                moved = []
                for c in contacts_by_account.get(loser["account_id"], []):
                    ops.append(
                        {
                            "op": "patch_contact",
                            "contact_id": c["contact_id"],
                            "body": {"account_id": survivor["account_id"]},
                        }
                    )
                    changes.append(
                        {"entity": "contact", "id": c["contact_id"],
                         "field": "account_id", "before": loser["account_id"],
                         "after": survivor["account_id"]}
                    )
                    moved.append(f"{c.get('name')} ({c.get('title')})")
                tier = "HIGH" if (winner["contact_match"] and winner["name_match"]) else "MEDIUM"
                evidence = {
                    "location": _loc_summary(loc),
                    "survivor": _acct_summary(survivor),
                    "loser": _acct_summary(loser),
                    "survivor_signals": _signals_text(winner),
                    "contacts_moved": moved,
                    "human": [reason]
                    + ([f"Re-pointing contacts to survivor: {', '.join(moved)}"]
                       if moved else ["No contacts on the losing record."]),
                }
                proposals.append(
                    _mk_proposal("MARK_DUPLICATE", loser["account_id"], "DUPLICATE",
                                 tier, ops, changes, evidence)
                )

        # ---- classify the winner -------------------------------------------
        name_ok = name_key(acct.get("name")) == name_key(loc["name"])
        parent_ok = acct.get("parent_id") == brand_id
        base_evidence = {
            "location": _loc_summary(loc),
            "account": _acct_summary(acct),
            "signals": _signals_text(winner),
            "human": [f"Matched via {_signals_text(winner)}."],
        }

        if name_ok and parent_ok:
            confirmed.append(
                {"slug": loc["slug"], "account_id": acct["account_id"],
                 "name": acct.get("name"), "signals": _signals_text(winner)}
            )
            classifications[loc["slug"]] = {
                "classification": "CONFIRMED", "account_id": acct["account_id"]
            }
            continue

        classifications[loc["slug"]] = {
            "classification": "NEEDS_FIX", "account_id": acct["account_id"]
        }

        if not parent_ok and _chow_locked(acct):
            # CHOW sequence: create replacement first, then link the old account.
            body = _create_body(loc, brand_parent)
            create_note = (
                f"Created under {brand_parent['name']} to complete CHOW re-parent "
                f"of {acct.get('name')} [{acct['account_id']}]; facility verified "
                f"on website ({loc['url']})."
            )
            old_note = (
                "CHOW: facility continues as account {new_id} under "
                f"{brand_parent['name']}. This account has lifetime revenue "
                f"{acct.get('lifetime_revenue')} and outstanding AR "
                f"{acct.get('outstanding_ar')}, so it is preserved unchanged "
                "per the CHOW rule."
            )
            ops = [
                {"op": "create_account", "body": body, "capture": "new_id",
                 "set_note": create_note},
                {"op": "patch_account", "account_id": acct["account_id"],
                 "body": {"chow_current_account": "{new_id}"},
                 "append_note": old_note},
            ]
            changes = [
                {"entity": "account", "id": "(new)", "field": k, "before": "",
                 "after": v} for k, v in body.items()
            ] + [
                {"entity": "account", "id": acct["account_id"],
                 "field": "chow_current_account",
                 "before": acct.get("chow_current_account", ""),
                 "after": "(new account id)"}
            ]
            evidence = dict(base_evidence)
            evidence["human"] = evidence["human"] + [
                f"Re-parent required ({acct.get('parent_name') or 'no parent'} -> "
                f"{brand_parent['name']}) but lifetime_revenue="
                f"{acct.get('lifetime_revenue')} and outstanding_ar="
                f"{acct.get('outstanding_ar')} are both > 0: CHOW rule forbids "
                "editing the old account. Creating a successor account and "
                "linking chow_current_account instead.",
            ]
            proposals.append(
                _mk_proposal("CHOW_REPARENT", acct["account_id"], "NEEDS_FIX",
                             "MEDIUM", ops, changes, evidence)
            )
            continue

        fields = {}
        human = list(base_evidence["human"])
        if not name_ok:
            fields["name"] = loc["name"]
            human.append(
                f"Name drift: CRM '{acct.get('name')}' vs website '{loc['name']}' "
                "— proposing the website spelling."
            )
        if not parent_ok:
            fields["parent_id"] = brand_id
            human.append(
                f"Parent fix: {acct.get('parent_name') or 'no parent'} -> "
                f"{brand_parent['name']} (no CHOW trigger: revenue="
                f"{acct.get('lifetime_revenue')}, AR={acct.get('outstanding_ar')})."
            )
        reason = " ".join(human[1:]) or human[0]
        ops = [
            {"op": "patch_account", "account_id": acct["account_id"],
             "body": fields, "append_note": reason}
        ]
        changes = [
            {"entity": "account", "id": acct["account_id"], "field": k,
             "before": acct.get("parent_name") if k == "parent_id" else acct.get(k, ""),
             "after": brand_parent["name"] if k == "parent_id" else v}
            for k, v in fields.items()
        ]
        single_field = len(fields) == 1
        corroborated = winner["addr_match"] and (
            winner["name_match"] or winner["contact_match"]
        )
        tier = "HIGH" if (single_field and corroborated) else "MEDIUM"
        evidence = dict(base_evidence)
        evidence["human"] = human
        proposals.append(
            _mk_proposal("UPDATE_ACCOUNT", acct["account_id"], "NEEDS_FIX",
                         tier, ops, changes, evidence)
        )

    # ---- reverse direction: ORPHANED brand-parent accounts -----------------
    orphans = []
    for acct in facilities:
        if acct.get("parent_id") != brand_id or acct.get("status") != "Active":
            continue
        if acct["account_id"] in matched_account_ids:
            continue
        if acct["account_id"] in duplicate_loser_ids:
            continue

        others_at_addr = []
        if has_usable_street(acct.get("billing_street")):
            akey = address_key(acct["billing_street"])
            others_at_addr = [
                o for o in facilities
                if o["account_id"] != acct["account_id"]
                and o.get("parent_id")
                and o.get("parent_id") != brand_id
                and has_usable_street(o.get("billing_street"))
                and address_key(o["billing_street"]) == akey
                and _loc_key(o.get("billing_city"), o.get("billing_state"))
                == _loc_key(acct.get("billing_city"), acct.get("billing_state"))
            ]

        if others_at_addr and _chow_locked(acct):
            # Divestiture under billing constraints -> CHOW link only.
            other = others_at_addr[0]
            if acct.get("chow_current_account"):
                continue  # already linked
            reason = (
                f"Facility no longer on the website; {other.get('name')} "
                f"[{other['account_id']}] ({other.get('parent_name')}) exists at "
                f"the same address — likely divestiture. Revenue "
                f"{acct.get('lifetime_revenue')} and AR {acct.get('outstanding_ar')} "
                "are both > 0, so per the CHOW rule only chow_current_account is "
                "set; all other fields untouched, status stays Active."
            )
            ops = [
                {"op": "patch_account", "account_id": acct["account_id"],
                 "body": {"chow_current_account": other["account_id"]},
                 "append_note": reason}
            ]
            changes = [
                {"entity": "account", "id": acct["account_id"],
                 "field": "chow_current_account",
                 "before": acct.get("chow_current_account", ""),
                 "after": other["account_id"]}
            ]
            evidence = {
                "account": _acct_summary(acct),
                "same_address_operator_accounts": [
                    _acct_summary(o) for o in others_at_addr
                ],
                "human": [reason],
            }
            proposals.append(
                _mk_proposal("CHOW_DIVESTITURE", acct["account_id"], "ORPHANED",
                             "LOW", ops, changes, evidence)
            )
            orphans.append({"account_id": acct["account_id"],
                            "name": acct.get("name"), "handling": "CHOW_DIVESTITURE"})
            continue

        if acct.get("status") == "Needs Review":
            continue  # condition already addressed
        if others_at_addr:
            reason = (
                f"Facility not on the website and {others_at_addr[0].get('name')} "
                f"[{others_at_addr[0]['account_id']}] exists at the same address "
                "under another operator — possible divestiture, but no billing "
                "constraint forces the CHOW form. A human should decide."
            )
        else:
            reason = (
                "Active under the Bellhaven parent but no website location "
                "matches by address or name. No proof it closed or was sold — "
                "flagging for human review instead of deactivating."
            )
        ops = [
            {"op": "patch_account", "account_id": acct["account_id"],
             "body": {"status": "Needs Review"}, "append_note": reason}
        ]
        changes = [
            {"entity": "account", "id": acct["account_id"], "field": "status",
             "before": acct.get("status"), "after": "Needs Review"}
        ]
        evidence = {
            "account": _acct_summary(acct),
            "same_address_operator_accounts": [
                _acct_summary(o) for o in others_at_addr
            ],
            "human": [reason],
        }
        proposals.append(
            _mk_proposal("NEEDS_REVIEW", acct["account_id"], "ORPHANED", "LOW",
                         ops, changes, evidence)
        )
        orphans.append({"account_id": acct["account_id"], "name": acct.get("name"),
                        "handling": "NEEDS_REVIEW"})

    counts = {}
    for v in classifications.values():
        counts[v["classification"]] = counts.get(v["classification"], 0) + 1
    counts["ORPHANED"] = len(orphans)
    counts["DUPLICATE_LOSERS"] = len(duplicate_loser_ids)

    summary = {
        "brand_parent": {"account_id": brand_id, "name": brand_parent["name"]},
        "locations_scraped": len(locations),
        "accounts_total": len(accounts),
        "superseded_accounts_excluded": sorted(superseded_ids),
        "classification_counts": counts,
        "classifications": classifications,
        "confirmed": confirmed,
        "orphans": orphans,
        "proposal_count": len(proposals),
    }
    return {"proposals": proposals, "summary": summary}
