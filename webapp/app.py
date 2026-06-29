#!/usr/bin/env python3
"""
保险商机情报系统 - Web 可视化界面 v2
新增: 政府/企业分类、保险关联度、时效过滤、商机理由
"""

import sqlite3, os, sys, json, subprocess, secrets, functools
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, abort

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, 'leads.db')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyzer import (
    classify_project_type, classify_insurance_relevance,
    is_fresh, insurance_opportunity_reason
)

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# API authentication via token (set via environment variable)
API_TOKEN = os.environ.get('LEAD_HUNTER_API_TOKEN', '')

ALLOWED_STATUSES = {'new', 'followed', 'closed'}
MAX_PER_PAGE = 100


def require_auth(f):
    """Require API token authentication for state-changing endpoints."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not API_TOKEN:
            # If no token configured, allow access (local dev mode)
            return f(*args, **kwargs)
        token = request.headers.get('X-API-Token', '') or request.args.get('token', '')
        if not secrets.compare_digest(token, API_TOKEN):
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db

def enrich_lead(row):
    """给线索附加分析结果"""
    d = dict(row)
    d['project_type'] = d.get('project_type') or classify_project_type(
        d.get('title',''), d.get('summary',''))
    d['insurance_relevance'] = d.get('insurance_relevance') or classify_insurance_relevance(
        d.get('title',''), d.get('summary',''))
    fresh, _ = is_fresh(d.get('publish_date',''))
    d['is_fresh'] = fresh
    d['opportunity'] = insurance_opportunity_reason(
        d.get('title',''), d.get('summary',''))
    return d

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def api_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    new = db.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0]
    followed = db.execute("SELECT COUNT(*) FROM leads WHERE status='followed'").fetchone()[0]
    closed = db.execute("SELECT COUNT(*) FROM leads WHERE status='closed'").fetchone()[0]
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    recent = db.execute("SELECT COUNT(*) FROM leads WHERE created_at >= ?", (week_ago,)).fetchone()[0]
    
    cats = db.execute("SELECT category, COUNT(*) as cnt FROM leads GROUP BY category ORDER BY cnt DESC").fetchall()
    srcs = db.execute("SELECT source_name, COUNT(*) as cnt FROM leads GROUP BY source_name ORDER BY cnt DESC").fetchall()
    daily = db.execute("SELECT DATE(created_at) as day, COUNT(*) as cnt FROM leads WHERE created_at >= ? GROUP BY day ORDER BY day", (week_ago,)).fetchall()
    
    # Government vs enterprise stats
    all_rows = db.execute("SELECT title, summary, project_type, insurance_relevance FROM leads").fetchall()
    gov_count = 0
    ent_count = 0
    high_rel = 0
    for r in all_rows:
        pt = r['project_type'] or classify_project_type(r['title'], r['summary'] or '')
        ir = r['insurance_relevance'] or classify_insurance_relevance(r['title'], r['summary'] or '')
        if pt == '政府项目': gov_count += 1
        elif pt == '企业项目': ent_count += 1
        if ir == '高': high_rel += 1
    
    db.close()
    return jsonify({
        'total': total, 'new': new, 'followed': followed, 'closed': closed,
        'recent_7d': recent,
        'by_category': {r['category']: r['cnt'] for r in cats},
        'by_source': {r['source_name']: r['cnt'] for r in srcs},
        'daily': {r['day']: r['cnt'] for r in daily},
        'gov_count': gov_count, 'ent_count': ent_count,
        'high_relevance': high_rel,
    })

@app.route('/api/leads')
def api_leads():
    db = get_db()
    category = request.args.get('category', '')
    source = request.args.get('source', '')
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    project_type = request.args.get('project_type', '')  # 政府项目/企业项目
    relevance = request.args.get('relevance', '')  # 高/中/低
    freshness = request.args.get('freshness', '')  # 7d/30d/all
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(request.args.get('per_page', 30))))
    except (ValueError, TypeError):
        page, per_page = 1, 30

    where = ['1=1']
    params = []
    if category: where.append('category=?'); params.append(category)
    if source: where.append('source_name=?'); params.append(source)
    if status: where.append('status=?'); params.append(status)
    if search: where.append('(title LIKE ? OR summary LIKE ?)'); params.extend([f'%{search}%', f'%{search}%'])

    where_clause = ' AND '.join(where)
    total = db.execute(f"SELECT COUNT(*) FROM leads WHERE {where_clause}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM leads WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    db.close()

    # Enrich and filter
    enriched = [enrich_lead(r) for r in rows]
    
    # Apply calculated filters (project_type, relevance, freshness)
    if project_type:
        enriched = [e for e in enriched if e['project_type'] == project_type]
    if relevance:
        enriched = [e for e in enriched if e['insurance_relevance'] == relevance]
    if freshness == '7d':
        enriched = [e for e in enriched if e.get('is_fresh')]
    elif freshness == '30d':
        enriched = [e for e in enriched if e.get('is_fresh')]

    return jsonify({
        'total': len(enriched), 'page': page, 'per_page': per_page,
        'leads': enriched,
    })

@app.route('/api/leads/<int:lead_id>')
def api_lead_detail(lead_id):
    db = get_db()
    lead = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    db.close()
    if lead:
        return jsonify(enrich_lead(lead))
    return jsonify({'error': 'not found'}), 404

@app.route('/api/leads/<int:lead_id>/status', methods=['POST'])
@require_auth
def api_update_status(lead_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'invalid request body'}), 400
    new_status = data.get('status', '')
    if new_status == 'delete':
        db = get_db()
        db.execute("DELETE FROM leads WHERE id=?", (lead_id,))
        db.commit()
        db.close()
        return jsonify({'ok': True})
    if new_status not in ALLOWED_STATUSES:
        return jsonify({'error': f'invalid status, must be one of: {sorted(ALLOWED_STATUSES)}'}), 400
    db = get_db()
    db.execute("UPDATE leads SET status=? WHERE id=?", (new_status, lead_id))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@app.route('/api/collect', methods=['POST'])
@require_auth
def api_collect():
    try:
        collector = os.path.join(PROJECT_DIR, 'sources', 'playwright_collector.py')
        if not os.path.isfile(collector):
            return jsonify({'ok': False, 'error': 'collector script not found'}), 500
        result = subprocess.run(
            [sys.executable, collector],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=180
        )
        # Only return a success summary, not raw stdout/stderr (avoid info disclosure)
        if result.returncode == 0:
            return jsonify({'ok': True, 'message': '采集完成'})
        else:
            return jsonify({'ok': False, 'error': '采集脚本执行失败'})
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'error': '采集超时'})
    except Exception:
        return jsonify({'ok': False, 'error': '采集过程中发生错误'})

if __name__ == '__main__':
    print("🛡️ 保险商机情报系统 Web v2")
    print(f"📍 http://127.0.0.1:5200")
    print(f"📂 {DB_PATH}")
    print(f"✨ 政府/企业分类 | 保险关联度 | 时效过滤 | 商机理由")
    if API_TOKEN:
        print("🔒 API token authentication enabled")
    else:
        print("⚠️  No LEAD_HUNTER_API_TOKEN set — running without auth (dev mode)")
    # Bind to localhost by default; set FLASK_HOST=0.0.0.0 to expose externally
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    app.run(host=host, port=5200, debug=False)
