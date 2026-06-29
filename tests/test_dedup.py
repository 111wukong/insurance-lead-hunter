import hashlib
import pytest
from core.dedup import Deduplicator


class TestDeduplicator:
    """Tests for core.dedup.Deduplicator"""

    def test_hash_url_deterministic(self):
        url = 'https://example.com/page'
        expected = hashlib.md5(url.encode('utf-8')).hexdigest()
        assert Deduplicator.hash_url(url) == expected

    def test_hash_url_different_for_different_urls(self):
        assert Deduplicator.hash_url('http://a.com') != Deduplicator.hash_url('http://b.com')

    def test_is_new_for_unseen_url(self, in_memory_db):
        dedup = Deduplicator(in_memory_db)
        assert dedup.is_new('https://example.com/new') is True

    def test_is_new_false_after_mark_seen(self, in_memory_db):
        dedup = Deduplicator(in_memory_db)
        url = 'https://example.com/seen'
        dedup.mark_seen(url)
        assert dedup.is_new(url) is False

    def test_mark_seen_idempotent(self, in_memory_db):
        dedup = Deduplicator(in_memory_db)
        url = 'https://example.com/dup'
        dedup.mark_seen(url)
        dedup.mark_seen(url)  # should not raise
        assert dedup.is_new(url) is False

    def test_different_urls_independent(self, in_memory_db):
        dedup = Deduplicator(in_memory_db)
        dedup.mark_seen('https://example.com/a')
        assert dedup.is_new('https://example.com/b') is True

    def test_hash_url_handles_unicode(self):
        url = 'https://example.com/中文路径'
        h = Deduplicator.hash_url(url)
        assert len(h) == 32  # md5 hex length
