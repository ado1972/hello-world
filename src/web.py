"""
SFG CRM — Flask web UI
Run with:  python src/web.py
"""

import os
import sys
import threading

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))
import crm
import agent as agent_module

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sfg-crm-dev-secret")

# Track background scrape jobs: job_id -> {"status", "log", "saved"}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    crm.init_db()
    stats = crm.get_stats()
    leads = crm.get_all_leads()[:50]  # most recent 50 on dashboard
    return render_template("index.html", stats=stats, leads=leads)


@app.route("/leads")
def leads():
    crm.init_db()
    status = request.args.get("status")
    all_leads = crm.get_all_leads(status=status)
    stats = crm.get_stats()
    return render_template("leads.html", leads=all_leads, stats=stats, current_status=status)


@app.route("/leads/<int:lead_id>")
def lead_detail(lead_id):
    crm.init_db()
    all_leads = crm.get_all_leads()
    lead = next((l for l in all_leads if l["id"] == lead_id), None)
    if not lead:
        flash("Lead not found.", "error")
        return redirect(url_for("leads"))
    return render_template("lead_detail.html", lead=lead)


@app.route("/leads/<int:lead_id>/status", methods=["POST"])
def update_status_inline(lead_id):
    status = request.form.get("status", "new")
    crm.update_lead_status(lead_id, status)
    # Return to whichever page the user came from
    return redirect(request.referrer or url_for("leads"))


@app.route("/leads/<int:lead_id>/update", methods=["POST"])
def update_lead(lead_id):
    status = request.form.get("status", "new")
    notes  = request.form.get("notes") or None
    crm.update_lead_status(lead_id, status, notes)
    flash("Lead updated.", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route("/scrape")
def scrape_page():
    return render_template("scrape.html")


@app.route("/scrape/run", methods=["POST"])
def scrape_run():
    """Start a scraping session in a background thread, redirect to job status page."""
    query          = request.form.get("query", "").strip()
    max_leads      = int(request.form.get("max_leads", 15))
    sfg_description = request.form.get("sfg_description", "").strip() or (
        os.environ.get("SFG_DESCRIPTION") or "SFG — a business services company"
    )

    if not query:
        flash("Please enter a search query.", "error")
        return redirect(url_for("scrape_page"))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        flash("ANTHROPIC_API_KEY is not set. Add it to your .env file.", "error")
        return redirect(url_for("scrape_page"))

    import uuid
    job_id = uuid.uuid4().hex[:8]

    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "log": [], "saved": 0}

    def run():
        try:
            # Monkey-patch crm.upsert_lead to also stream log messages
            original_upsert = crm.upsert_lead

            def patched_upsert(**kwargs):
                lead_id = original_upsert(**kwargs)
                with _jobs_lock:
                    _jobs[job_id]["log"].append(
                        f"✔ Lead saved → {kwargs.get('company','?')} (id {lead_id})"
                    )
                    _jobs[job_id]["saved"] += 1
                return lead_id

            crm.upsert_lead = patched_upsert

            with _jobs_lock:
                _jobs[job_id]["log"].append(f"Starting search: {query}")

            saved = agent_module.run_scraper(
                search_query=query,
                sfg_description=sfg_description,
                max_leads=max_leads,
            )

            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["log"].append(f"✅ Done — {saved} lead(s) saved.")
        except Exception as exc:
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["log"].append(f"❌ Error: {exc}")
        finally:
            crm.upsert_lead = original_upsert  # restore

    t = threading.Thread(target=run, daemon=True)
    t.start()

    return redirect(url_for("scrape_status", job_id=job_id))


@app.route("/scrape/status/<job_id>")
def scrape_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("index"))
    return render_template("scrape_status.html", job_id=job_id, job=job)


@app.route("/api/job/<job_id>")
def api_job(job_id):
    """Polled by the status page every 2 s."""
    with _jobs_lock:
        job = dict(_jobs.get(job_id, {"status": "not_found", "log": [], "saved": 0}))
    return jsonify(job)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    crm.init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"SFG CRM running at http://localhost:{port}")
    app.run(debug=True, port=port, use_reloader=False)
