#!/usr/bin/env python3
"""
保险商机情报系统 - Web 可视化界面 v2
新增: 政府/企业分类、保险关联度、时效过滤、商机理由
"""

import sqlite3, os, sys, json, subprocess
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, 'leads.db')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyzer import (
    classify_project_type, classify_insurance_relevance,
    is_fresh, insurance_opportunity_reason
)

app = Flask(__name__, template_folder='templates')

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
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 30))
    except (ValueError, TypeError):
        return jsonify({'error': 'page and per_page must be integers'}), 400
    if page < 1:
        return jsonify({'error': 'page must be >= 1'}), 400
    if per_page < 1 or per_page > 200:
        return jsonify({'error': 'per_page must be between 1 and 200'}), 400

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
def api_update_status(lead_id):
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'missing status field in request body'}), 400
    new_status = data['status']
    valid_statuses = ('new', 'followed', 'closed', 'delete')
    if new_status not in valid_statuses:
        return jsonify({'error': f'invalid status, must be one of: {valid_statuses}'}), 400
    db = get_db()
    # Verify lead exists
    existing = db.execute("SELECT id FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not existing:
        db.close()
        return jsonify({'error': f'lead {lead_id} not found'}), 404
    if new_status == 'delete':
        db.execute("DELETE FROM leads WHERE id=?", (lead_id,))
    else:
        db.execute("UPDATE leads SET status=? WHERE id=?", (new_status, lead_id))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@app.route('/api/collect', methods=['POST'])
def api_collect():
    try:
        collector = os.path.join(PROJECT_DIR, 'sources', 'playwright_collector.py')
        if not os.path.exists(collector):
            return jsonify({'ok': False, 'error': f'采集脚本不存在: {collector}'}), 500
        result = subprocess.run(
            [sys.executable, collector],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            return jsonify({
                'ok': False,
                'error': f'采集脚本退出码: {result.returncode}',
                'stdout': result.stdout[-3000:],
                'stderr': result.stderr[-1000:],
            })
        return jsonify({'ok': True, 'stdout': result.stdout[-3000:], 'stderr': result.stderr[-500:]})
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'error': '采集超时 (超过180秒)'}), 504
    except Exception as e:
        return jsonify({'ok': False, 'error': f'采集异常: {type(e).__name__}: {e}'}), 500

if __name__ == '__main__':
    print("🛡️ 保险商机情报系统 Web v2")
    print(f"📍 http://localhost:5200")
    print(f"📂 {DB_PATH}")
    print(f"✨ 政府/企业分类 | 保险关联度 | 时效过滤 | 商机理由")
    app.run(host='0.0.0.0', port=5200, debug=False)
