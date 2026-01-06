from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from triage.run_and_triage import run_once
from triage.storage import list_runs, get_run, compute_flaky_tests

app = FastAPI(title="AI CI Triage")

@app.get("/", response_class=HTMLResponse)
def home():
    runs = list_runs(limit=25)

    rows = []
    for r in runs:
        tri = r["triage"]
        rows.append(f"""
        <tr>
          <td><a href="/runs/{r['id']}">{r['id']}</a></td>
          <td>{r['created_at']}</td>
          <td>{'✅' if r['ok'] else '❌'}</td>
          <td>{tri.get('classification','')}</td>
          <td>{tri.get('action','')}</td>
          <td>{'YES' if tri.get('block_ci') else 'NO'}</td>
          <td>{tri.get('engine','')}</td>
        </tr>
        """)

    html = f"""
    <html>
      <head>
        <title>AI CI Triage</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin-bottom: 18px; }}
          table {{ border-collapse: collapse; width: 100%; }}
          th, td {{ border-bottom: 1px solid #eee; padding: 10px; text-align: left; }}
          th {{ background: #fafafa; }}
          .btn {{ display: inline-block; padding: 10px 14px; border-radius: 10px; border: 1px solid #333; text-decoration: none; color: #111; cursor: pointer; }}
          code {{ background:#f6f6f6; padding:2px 6px; border-radius:6px; }}
          pre.code-block {{
            white-space: pre;
            overflow-x: auto;
            background: #f6f6f6;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #eee;
          }}
          pre.code-block code {{
            background: transparent;
            padding: 0;
          }}

        </style>
      </head>
      <body>
        <h1>AI CI Triage</h1>

        <div class="card">
          <h2>Run tests</h2>
          <form method="post" action="/run">
            <button class="btn" type="submit">Run tests now</button>
          </form>
          <p style="color:#555;margin-top:10px;">
            If <code>OPENAI_API_KEY</code> is set, the system uses an LLM for triage; otherwise it falls back to rules.
          </p>
          <p style="margin-top:10px;">
            <a class="btn" href="/flaky">View flaky tests</a>
          </p>
        </div>

        <div class="card">
          <h2>Recent runs</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Time (UTC)</th><th>OK</th><th>Classification</th><th>Action</th><th>Block CI</th><th>Engine</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows) if rows else '<tr><td colspan="7">No runs yet. Click "Run tests now".</td></tr>'}
            </tbody>
          </table>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(html)

@app.post("/run")
def run_tests():
    # In production you'd do this async (Celery/RQ) to avoid blocking.
    run_once()
    return RedirectResponse(url="/", status_code=303)

@app.get("/flaky", response_class=HTMLResponse)
def flaky_page():
    stats = compute_flaky_tests(window=30, min_occurrences=3)
    flaky = [(t, s) for t, s in stats.items() if s.get("is_flaky")]

    rows = []
    for t, s in sorted(flaky, key=lambda x: (-x[1]["runs"], -x[1]["fails"])):
        rows.append(f"""
        <tr>
          <td><code>{_escape_text(t)}</code></td>
          <td>{s['runs']}</td>
          <td>{s['fails']}</td>
          <td>{s['passes']}</td>
          <td>{s['fail_rate']}</td>
        </tr>
        """)

    html = f"""
    <html>
      <head>
        <title>Flaky Tests</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin-bottom: 18px; }}
          table {{ border-collapse: collapse; width: 100%; }}
          th, td {{ border-bottom: 1px solid #eee; padding: 10px; text-align: left; }}
          th {{ background: #fafafa; }}
          code {{ background:#f6f6f6; padding:2px 6px; border-radius:6px; }}
          a {{ text-decoration:none; }}
        </style>
      </head>
      <body>
        <p><a href="/">← Back</a></p>
        <h1>Flaky tests (heuristic)</h1>
        <div class="card">
          <p>
            A test is marked <b>flaky</b> if, within the last 30 runs, it has both passes and failures
            and appears in at least 3 runs.
          </p>
        </div>
        <div class="card">
          <h2>Flaky list</h2>
          <table>
            <thead>
              <tr><th>Test</th><th>Runs</th><th>Fails</th><th>Passes</th><th>Fail rate</th></tr>
            </thead>
            <tbody>
              {''.join(rows) if rows else '<tr><td colspan="5">No flaky tests detected yet. Run tests multiple times.</td></tr>'}
            </tbody>
          </table>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(run_id: int):
    r = get_run(run_id)
    if not r:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)

    tri = r["triage"]
    failed = r.get("failed_tests", [])
    flaky_stats = compute_flaky_tests(window=30, min_occurrences=3)
    flaky_failed = [t for t in failed if flaky_stats.get(t, {}).get("is_flaky")]

    # tri_html = "<pre>" + _escape_json(tri) + "</pre>"
        # --- Extract "code recommended" and render it as code block ---
    tri_for_json = dict(tri) if isinstance(tri, dict) else {}
    code_rec = tri_for_json.pop("code recommended", None) or tri_for_json.pop("code_recommended", None)

    tri_html = "<pre>" + _escape_json(tri_for_json) + "</pre>"

    code_html = ""
    if code_rec:
        # JSON里通常是 "\\n" 两个字符，转成真正换行
        code_pretty = str(code_rec).replace("\\n", "\n").replace("\\t", "\t")
        code_html = f"""
        <div class="card">
          <h2>Code recommended</h2>
          <pre class="code-block"><code>{_escape_text(code_pretty)}</code></pre>
        </div>
        """

    raw = "<pre style='white-space:pre-wrap;'>" + _escape_text(r["raw_output"]) + "</pre>"

    failed_list = ""
    if failed:
        items = []
        for t in failed:
            tag = " (FLAKY)" if t in flaky_failed else ""
            items.append(f"<li><code>{_escape_text(t)}</code>{tag}</li>")
        failed_list = "<ul>" + "".join(items) + "</ul>"
    else:
        failed_list = "<p>No failed tests.</p>"

    html = f"""
    <html>
      <head>
        <title>Run {run_id}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin-bottom: 18px; }}
          a {{ text-decoration:none; }}
          code {{ background:#f6f6f6; padding:2px 6px; border-radius:6px; }}
        </style>
      </head>
      <body>
        <p><a href="/">← Back</a></p>
        <h1>Run #{run_id}</h1>

        <div class="card">
          <h2>Summary</h2>
          <ul>
            <li><b>Time (UTC):</b> {r['created_at']}</li>
            <li><b>OK:</b> {'✅' if r['ok'] else '❌'}</li>
            <li><b>Return code:</b> {r['return_code']}</li>
          </ul>
        </div>

        <div class="card">
          <h2>Failed tests</h2>
          {failed_list}
          <p style="color:#555;">
            Tip: run tests multiple times to let the flaky heuristic detect pass/fail variability.
          </p>
        </div>

        <div class="card">
          <h2>Triage Decision (JSON)</h2>
          {tri_html}
        </div>
        {code_html}

        <div class="card">
          <h2>Raw pytest output</h2>
          {raw}
        </div>
      </body>
    </html>
    """
    return HTMLResponse(html)

def _escape_text(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _escape_json(obj) -> str:
    import json
    return _escape_text(json.dumps(obj, indent=2, ensure_ascii=False))
