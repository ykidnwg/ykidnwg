"""
dashboard.py – optional FastAPI dashboard for monitoring bot activity.
Start with:  uvicorn dashboard:app --host 0.0.0.0 --port 8080
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Terabox Bot Dashboard", version="1.0.0")


def _get_stats():
    from database.models import Job, get_session
    session = get_session()
    try:
        total = session.query(Job).count()
        pending = session.query(Job).filter(Job.status == "PENDING").count()
        running = session.query(Job).filter(Job.status == "RUNNING").count()
        success = session.query(Job).filter(Job.status == "SUCCESS").count()
        failed = session.query(Job).filter(Job.status == "FAILED").count()
        duplicate = session.query(Job).filter(Job.status == "DUPLICATE").count()
        recent = (
            session.query(Job)
            .order_by(Job.updated_at.desc())
            .limit(20)
            .all()
        )
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "success": success,
            "failed": failed,
            "duplicate": duplicate,
            "recent": recent,
        }
    finally:
        session.close()


@app.get("/api/stats")
def api_stats():
    stats = _get_stats()
    stats.pop("recent")  # strip ORM objects for JSON
    return stats


@app.get("/api/jobs")
def api_jobs(limit: int = 50):
    from database.models import Job, get_session
    session = get_session()
    try:
        jobs = (
            session.query(Job)
            .order_by(Job.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": j.id,
                "link": j.link,
                "status": j.status,
                "file_name": j.file_name,
                "share_link": j.share_link,
                "created_at": str(j.created_at),
                "updated_at": str(j.updated_at),
            }
            for j in jobs
        ]
    finally:
        session.close()


@app.get("/", response_class=HTMLResponse)
def dashboard_ui():
    stats = _get_stats()
    rows = "".join(
        f"<tr>"
        f"<td>{j.id}</td>"
        f"<td style='max-width:300px;overflow:hidden;text-overflow:ellipsis'>{j.link}</td>"
        f"<td>{j.status}</td>"
        f"<td>{j.file_name or ''}</td>"
        f"<td><a href='{j.share_link}' target='_blank'>{j.share_link or ''}</a></td>"
        f"<td>{j.updated_at}</td>"
        f"</tr>"
        for j in stats["recent"]
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Terabox Bot Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; background:#1a1a2e; color:#eee; padding:20px; }}
    h1 {{ color:#e94560; }}
    .cards {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px; }}
    .card {{ background:#16213e; padding:20px 32px; border-radius:8px; text-align:center; }}
    .card .num {{ font-size:2.5rem; font-weight:bold; color:#0f3460; }}
    .card .label {{ font-size:.9rem; color:#aaa; }}
    .num.success {{ color:#27ae60; }}
    .num.failed {{ color:#e74c3c; }}
    .num.pending {{ color:#f39c12; }}
    table {{ width:100%; border-collapse:collapse; background:#16213e; border-radius:8px; overflow:hidden; }}
    th {{ background:#0f3460; padding:10px; text-align:left; }}
    td {{ padding:8px 10px; border-bottom:1px solid #333; font-size:.85rem; }}
    tr:hover td {{ background:#0d2137; }}
    a {{ color:#e94560; }}
  </style>
</head>
<body>
  <h1>📊 Terabox Bot Dashboard</h1>
  <div class="cards">
    <div class="card"><div class="num">{stats['total']}</div><div class="label">Total Jobs</div></div>
    <div class="card"><div class="num pending">{stats['pending']}</div><div class="label">Pending</div></div>
    <div class="card"><div class="num">{stats['running']}</div><div class="label">Running</div></div>
    <div class="card"><div class="num success">{stats['success']}</div><div class="label">Success</div></div>
    <div class="card"><div class="num failed">{stats['failed']}</div><div class="label">Failed</div></div>
    <div class="card"><div class="num">{stats['duplicate']}</div><div class="label">Duplicate</div></div>
  </div>
  <h2>Recent Jobs</h2>
  <table>
    <thead><tr><th>#</th><th>Link</th><th>Status</th><th>File Name</th><th>Share Link</th><th>Updated</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <script>setTimeout(()=>location.reload(), 30000);</script>
</body>
</html>"""
    return HTMLResponse(content=html)
