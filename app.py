"""Review UI (Flask). Lists proposals grouped by confidence tier, shows exact
field changes, evidence, and raw API operations. Every CRM write requires an
explicit human approval here — nothing auto-applies, ever."""
import json

from flask import Flask, redirect, render_template_string, request, url_for

import run_pipeline
import store
from pipeline import executor

app = Flask(__name__)

PAGE = """
<!doctype html><html><head><meta charset="utf-8">
<title>Bellhaven CRM Sync — Review</title>
<style>
 body{font-family:Segoe UI,system-ui,sans-serif;margin:0;background:#f5f4f0;color:#222}
 header{background:#2E5D50;color:#fff;padding:14px 24px;display:flex;gap:18px;align-items:center}
 header a{color:#fff;text-decoration:none;font-weight:600}
 header form{margin-left:auto}
 .wrap{max-width:1100px;margin:0 auto;padding:20px}
 h2{margin:26px 0 8px}
 .tier-HIGH{border-left:5px solid #2E7D32}.tier-MEDIUM{border-left:5px solid #C9A227}
 .tier-LOW{border-left:5px solid #B45309}
 .card{background:#fff;border:1px solid #ddd;border-radius:6px;padding:14px 18px;margin:10px 0}
 .badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:3px;background:#eee;margin-right:6px}
 .b-applied{background:#d7ecd9}.b-failed{background:#f6d3d3}.b-rejected{background:#e5e5e5}
 .b-pending{background:#fdf3d5}.b-stale{background:#eee;color:#888}
 table{border-collapse:collapse;margin:8px 0;font-size:13px}
 td,th{border:1px solid #ddd;padding:4px 8px;text-align:left}
 .before{color:#a33;text-decoration:line-through}.after{color:#2E7D32;font-weight:600}
 details{margin:6px 0} pre{background:#f7f6f2;border:1px solid #e5e2d8;padding:8px;
 font-size:12px;overflow-x:auto;border-radius:4px}
 button{cursor:pointer;border:none;border-radius:4px;padding:6px 14px;font-weight:600}
 .approve{background:#2E7D32;color:#fff}.reject{background:#b3b3b3}
 .bulk{background:#2E5D50;color:#fff;padding:8px 16px}
 ul{margin:4px 0}
 .muted{color:#777;font-size:13px}
</style></head><body>
<header>
  <span style="font-size:18px">Bellhaven <b>CRM Sync</b></span>
  <a href="{{ url_for('index') }}">Proposals</a>
  <a href="{{ url_for('summary') }}">Run summary</a>
  <form method="post" action="{{ url_for('trigger_run') }}"
        onsubmit="this.querySelector('button').disabled=true">
    <button class="bulk">Run pipeline now</button></form>
</header>
<div class="wrap">
{% if message %}<div class="card">{{ message }}</div>{% endif %}
{{ body|safe }}
</div></body></html>
"""


def _proposal_card(p):
    status_badge = f'<span class="badge b-{p["status"]}">{p["status"]}</span>'
    stale_badge = '<span class="badge b-stale">stale</span>' if p["stale"] else ""
    rows = "".join(
        f"<tr><td>{c['entity']}</td><td>{c['id']}</td><td>{c['field']}</td>"
        f"<td class='before'>{c['before'] or '&mdash;'}</td>"
        f"<td class='after'>{c['after']}</td></tr>"
        for c in p["changes"]
    )
    human = "".join(f"<li>{h}</li>" for h in p["evidence"].get("human", []))
    actions = ""
    if p["status"] == "pending" and not p["stale"]:
        actions = (
            f'<form style="display:inline" method="post" '
            f'action="/proposals/{p["proposal_id"]}/approve">'
            f'<button class="approve">Approve &amp; apply</button></form> '
            f'<form style="display:inline" method="post" '
            f'action="/proposals/{p["proposal_id"]}/reject">'
            f'<button class="reject">Reject</button></form>'
        )
    api_resp = ""
    if p.get("api_response"):
        api_resp = (
            "<details><summary>API response</summary>"
            f"<pre>{json.dumps(json.loads(p['api_response']), indent=2)}</pre></details>"
        )
    return f"""
    <div class="card tier-{p['tier']}">
      <div>{status_badge}{stale_badge}
        <span class="badge">{p['tier']}</span>
        <span class="badge">{p['classification']}</span>
        <span class="badge">{p['ptype']}</span>
        <b>{p['target']}</b>
        <span style="float:right">{actions}</span></div>
      <table><tr><th>entity</th><th>id</th><th>field</th><th>before</th><th>after</th></tr>
      {rows}</table>
      <b>Evidence</b><ul>{human}</ul>
      <details><summary>Full evidence</summary>
        <pre>{json.dumps(p['evidence'], indent=2)}</pre></details>
      <details><summary>Raw API operations (run in order on approval)</summary>
        <pre>{json.dumps(p['payload'], indent=2)}</pre></details>
      {api_resp}
      <div class="muted">proposal {p['proposal_id'][:16]}&hellip;
        created {p['created_at']}</div>
    </div>"""


@app.route("/")
def index():
    conn = store.connect()
    pending = store.list_proposals(conn, status="pending")
    decided = [
        p for s in ("failed", "applied", "approved", "rejected")
        for p in store.list_proposals(conn, status=s, include_stale=True)
    ]
    stale = store.list_stale_pending(conn)
    conn.close()

    parts = []
    high_count = sum(1 for p in pending if p["tier"] == "HIGH")
    if high_count:
        parts.append(
            f'<form method="post" action="{url_for("approve_all_high")}">'
            f'<button class="bulk">Approve all HIGH ({high_count})</button>'
            "<span class='muted'> — applies immediately; still an explicit human "
            "action</span></form>"
        )
    for tier in ("HIGH", "MEDIUM", "LOW"):
        group = [p for p in pending if p["tier"] == tier]
        if group:
            parts.append(f"<h2>{tier} confidence — pending ({len(group)})</h2>")
            parts.extend(_proposal_card(p) for p in group)
    if not pending:
        parts.append("<h2>No pending proposals</h2><p class='muted'>Run the "
                     "pipeline to generate proposals.</p>")
    if decided:
        parts.append(f"<h2>Decided ({len(decided)})</h2>")
        parts.extend(_proposal_card(p) for p in decided)
    if stale:
        parts.append(
            f"<h2>Stale ({len(stale)})</h2><p class='muted'>The underlying "
            "condition disappeared on the latest run; hidden from review.</p>")
        parts.extend(_proposal_card(p) for p in stale)
    return render_template_string(
        PAGE, body="".join(parts), message=request.args.get("m"))


@app.route("/proposals/<pid>/approve", methods=["POST"])
def approve(pid):
    conn = store.connect()
    p = store.get_proposal(conn, pid)
    if not p or p["status"] != "pending" or p["stale"]:
        conn.close()
        return redirect(url_for("index", m="Proposal not pending — nothing done."))
    store.set_decision(conn, pid, "approved")
    ok, results = executor.apply_proposal(p)
    store.set_applied(conn, pid, ok, results)
    conn.close()
    msg = "Applied." if ok else "FAILED — see the proposal's API response."
    return redirect(url_for("index", m=msg))


@app.route("/proposals/<pid>/reject", methods=["POST"])
def reject(pid):
    conn = store.connect()
    p = store.get_proposal(conn, pid)
    if p and p["status"] == "pending":
        store.set_decision(conn, pid, "rejected")
    conn.close()
    return redirect(url_for("index", m="Rejected."))


@app.route("/approve-all-high", methods=["POST"])
def approve_all_high():
    conn = store.connect()
    high = [p for p in store.list_proposals(conn, status="pending")
            if p["tier"] == "HIGH"]
    applied = failed = 0
    for p in high:
        store.set_decision(conn, p["proposal_id"], "approved")
        ok, results = executor.apply_proposal(p)
        store.set_applied(conn, p["proposal_id"], ok, results)
        applied += ok
        failed += not ok
    conn.close()
    return redirect(url_for("index", m=f"HIGH bulk: {applied} applied, {failed} failed."))


@app.route("/run", methods=["POST"])
def trigger_run():
    try:
        run_pipeline.run(verbose=False)
        msg = "Pipeline run complete."
    except Exception as exc:
        msg = f"Pipeline run FAILED: {exc}"
    return redirect(url_for("index", m=msg))


@app.route("/summary")
def summary():
    conn = store.connect()
    run = store.last_run(conn)
    stale = store.list_stale_pending(conn)
    conn.close()
    if not run:
        return render_template_string(
            PAGE, body="<h2>No runs yet</h2>", message=None)
    s = run["summary"]
    counts = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in s["classification_counts"].items())
    confirmed = "".join(
        f"<li>{c['name']} [{c['account_id']}] &larr; {c['slug']} "
        f"<span class='muted'>({c['signals']})</span></li>"
        for c in s["confirmed"])
    orphans = "".join(
        f"<li>{o['name']} [{o['account_id']}] &rarr; {o['handling']}</li>"
        for o in s["orphans"])
    warnings = "".join(f"<li>{w}</li>" for w in s.get("scrape_warnings", []))
    body = f"""
    <h2>Last run: {s.get('run_id')}</h2>
    <div class="card">
      <p>Finished {run['finished_at']} &middot; {s['locations_scraped']} website
      locations &middot; {s['accounts_total']} CRM accounts &middot; brand parent:
      {s['brand_parent']['name']} [{s['brand_parent']['account_id']}]</p>
      <table><tr><th>classification</th><th>count</th></tr>{counts}</table>
      <p>Proposals this run: {json.dumps(s.get('store'))}</p>
      <p>Homepage-only slugs: {', '.join(s.get('homepage_only_slugs') or []) or 'none'}</p>
      {'<b>Scrape warnings</b><ul>' + warnings + '</ul>' if warnings else ''}
    </div>
    <h2>Confirmed matches ({len(s['confirmed'])})</h2>
    <div class="card"><ul>{confirmed or '<li>none</li>'}</ul></div>
    <h2>Orphaned accounts ({len(s['orphans'])})</h2>
    <div class="card"><ul>{orphans or '<li>none</li>'}</ul></div>
    <h2>Stale proposals ({len(stale)})</h2>
    <div class="card"><ul>{''.join(f"<li>{p['ptype']} {p['target']}</li>" for p in stale) or '<li>none</li>'}</ul></div>
    """
    return render_template_string(PAGE, body=body, message=None)


if __name__ == "__main__":
    app.run(debug=False, port=5000)
