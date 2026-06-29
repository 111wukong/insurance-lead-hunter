import pytest
from storage.db import Database


class TestDatabase:
    """Tests for storage.db.Database"""

    def test_init_db_creates_tables(self, in_memory_db):
        conn = in_memory_db._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row['name'] for row in tables}
        assert 'urls' in table_names
        assert 'leads' in table_names

    def test_insert_url_and_is_url_seen(self, in_memory_db):
        in_memory_db.insert_url('abc123', 'https://example.com')
        assert in_memory_db.is_url_seen('abc123') is True
        assert in_memory_db.is_url_seen('xyz789') is False

    def test_insert_url_duplicate_ignored(self, in_memory_db):
        in_memory_db.insert_url('dup', 'https://example.com')
        in_memory_db.insert_url('dup', 'https://example.com')
        conn = in_memory_db._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM urls WHERE url_hash='dup'").fetchone()[0]
        assert count == 1

    def test_insert_lead_and_get_new_leads(self, in_memory_db, sample_lead):
        in_memory_db.insert_lead(sample_lead)
        leads = in_memory_db.get_new_leads()
        assert len(leads) == 1
        assert leads[0]['title'] == sample_lead['title']
        assert leads[0]['status'] == 'new'

    def test_insert_lead_also_records_url(self, in_memory_db, sample_lead):
        in_memory_db.insert_lead(sample_lead)
        import hashlib
        url_hash = hashlib.md5(sample_lead['url'].encode('utf-8')).hexdigest()
        assert in_memory_db.is_url_seen(url_hash) is True

    def test_insert_leads_batch(self, in_memory_db):
        leads = [
            {'title': f'Lead {i}', 'url': f'https://example.com/{i}',
             'summary': '', 'source_name': 'test', 'category': '工程类',
             'date': '', 'amount': '', 'contact_info': ''}
            for i in range(5)
        ]
        in_memory_db.insert_leads(leads)
        result = in_memory_db.get_new_leads(limit=10)
        assert len(result) == 5

    def test_insert_leads_handles_failure_gracefully(self, in_memory_db):
        """A bad lead in the batch should not stop others."""
        good_lead = {
            'title': 'Good', 'url': 'https://example.com/good',
            'summary': '', 'source_name': 'test', 'category': '工程类',
            'date': '', 'amount': '', 'contact_info': '',
        }
        bad_lead = {}  # missing 'url' key
        in_memory_db.insert_leads([good_lead, bad_lead])
        result = in_memory_db.get_new_leads()
        assert len(result) >= 1

    def test_mark_status(self, in_memory_db, sample_lead):
        in_memory_db.insert_lead(sample_lead)
        leads = in_memory_db.get_new_leads()
        lead_id = leads[0]['id']

        in_memory_db.mark_status(lead_id, 'followed')

        conn = in_memory_db._get_conn()
        row = conn.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()
        assert row['status'] == 'followed'

    def test_get_new_leads_limit(self, in_memory_db):
        for i in range(10):
            in_memory_db.insert_lead({
                'title': f'Lead {i}', 'url': f'https://example.com/{i}',
                'summary': '', 'source_name': 'test', 'category': '',
                'date': '', 'amount': '', 'contact_info': '',
            })
        result = in_memory_db.get_new_leads(limit=3)
        assert len(result) == 3

    def test_get_stats_empty_db(self, in_memory_db):
        stats = in_memory_db.get_stats()
        assert stats['total'] == 0
        assert stats['new'] == 0
        assert stats['followed'] == 0
        assert stats['closed'] == 0
        assert stats['recent_7d'] == 0
        assert stats['by_category'] == {}
        assert stats['by_source'] == {}

    def test_get_stats_with_data(self, in_memory_db, sample_lead):
        in_memory_db.insert_lead(sample_lead)
        stats = in_memory_db.get_stats()
        assert stats['total'] == 1
        assert stats['new'] == 1
        assert '工程类' in stats['by_category']
        assert stats['by_category']['工程类'] == 1

    def test_clean_old_data(self, in_memory_db, sample_lead):
        in_memory_db.insert_lead(sample_lead)

        # Manually backdate the record
        conn = in_memory_db._get_conn()
        conn.execute("UPDATE leads SET created_at = datetime('now', '-60 days')")
        conn.commit()

        in_memory_db.clean_old_data(retention_days=30)
        leads = in_memory_db.get_new_leads()
        assert len(leads) == 0

    def test_clean_old_data_keeps_recent(self, in_memory_db, sample_lead):
        in_memory_db.insert_lead(sample_lead)
        in_memory_db.clean_old_data(retention_days=30)
        leads = in_memory_db.get_new_leads()
        assert len(leads) == 1

    def test_close_sets_conn_none(self, in_memory_db):
        assert in_memory_db.conn is not None
        in_memory_db.close()
        assert in_memory_db.conn is None

    def test_close_idempotent(self, in_memory_db):
        in_memory_db.close()
        in_memory_db.close()  # should not raise

    def test_reopen_file_db(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        config = {'database': {'path': db_path}}
        db = Database(config)
        db.init_db()
        db.insert_url('test', 'https://example.com')
        db.close()

        # Reopen and verify data persisted
        db2 = Database(config)
        assert db2.is_url_seen('test') is True
        db2.close()
