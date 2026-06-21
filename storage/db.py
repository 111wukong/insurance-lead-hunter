import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Database:
    """SQLite 数据库管理"""

    def __init__(self, config: dict):
        db_path = config.get('database', {}).get('path', 'leads.db')
        self.db_path = db_path
        self.conn = None

    def _get_conn(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                url_hash TEXT NOT NULL,
                summary TEXT DEFAULT '',
                source_name TEXT DEFAULT '',
                category TEXT DEFAULT '',
                publish_date TEXT DEFAULT '',
                amount TEXT DEFAULT '',
                contact_info TEXT DEFAULT '',
                raw_data TEXT DEFAULT '{}',
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_urls_hash ON urls(url_hash)
        ''')

        conn.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")

    def is_url_seen(self, url_hash: str) -> bool:
        """检查 URL 是否已存在"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM urls WHERE url_hash = ?', (url_hash,))
        return cursor.fetchone()[0] > 0

    def insert_url(self, url_hash: str, url: str):
        """插入 URL 记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO urls (url_hash, url) VALUES (?, ?)',
            (url_hash, url)
        )
        conn.commit()

    def insert_lead(self, lead: Dict):
        """插入单条线索"""
        import hashlib
        url_hash = hashlib.md5(lead['url'].encode('utf-8')).hexdigest()
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO leads
            (title, url, url_hash, summary, source_name, category,
             publish_date, amount, contact_info, raw_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lead.get('title', ''),
            lead.get('url', ''),
            url_hash,
            lead.get('summary', ''),
            lead.get('source_name', ''),
            lead.get('category', ''),
            lead.get('date', ''),
            lead.get('amount', ''),
            lead.get('contact_info', ''),
            json.dumps(lead, ensure_ascii=False),
            'new',
        ))
        conn.commit()
        self.insert_url(url_hash, lead.get('url', ''))

    def insert_leads(self, leads: List[Dict]):
        """批量插入线索"""
        for lead in leads:
            try:
                self.insert_lead(lead)
            except Exception as e:
                logger.warning(f"插入线索失败 [{lead.get('title', '')[:20]}]: {e}")

    def get_new_leads(self, limit: int = 100) -> List[Dict]:
        """获取最新线索"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC LIMIT ?',
            ('new', limit)
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_status(self, lead_id: int, status: str):
        """更新线索状态"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE leads SET status = ? WHERE id = ?',
            (status, lead_id)
        )
        conn.commit()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        conn = self._get_conn()
        cursor = conn.cursor()

        total = cursor.execute('SELECT COUNT(*) FROM leads').fetchone()[0]
        new_count = cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'new'"
        ).fetchone()[0]
        followed = cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'followed'"
        ).fetchone()[0]
        closed = cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'closed'"
        ).fetchone()[0]

        by_category = {}
        cat_rows = cursor.execute(
            'SELECT category, COUNT(*) as cnt FROM leads GROUP BY category ORDER BY cnt DESC'
        ).fetchall()
        for row in cat_rows:
            by_category[row['category']] = row['cnt']

        by_source = {}
        src_rows = cursor.execute(
            'SELECT source_name, COUNT(*) as cnt FROM leads GROUP BY source_name ORDER BY cnt DESC'
        ).fetchall()
        for row in src_rows:
            by_source[row['source_name']] = row['cnt']

        recent = cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()[0]

        return {
            'total': total,
            'new': new_count,
            'followed': followed,
            'closed': closed,
            'recent_7d': recent,
            'by_category': by_category,
            'by_source': by_source,
        }

    def clean_old_data(self, retention_days: int = 30):
        """清理旧数据"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM leads WHERE created_at < datetime('now', '-{retention_days} days')"
        )
        deleted = cursor.rowcount
        conn.commit()
        logger.info(f"清理了 {deleted} 条过期线索")

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
