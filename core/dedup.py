import hashlib
import logging
from storage.db import Database

logger = logging.getLogger(__name__)


class Deduplicator:
    """基于 URL MD5 哈希的去重器"""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    def is_new(self, url: str) -> bool:
        """检查 URL 是否为新（未抓取过）"""
        url_hash = self.hash_url(url)
        return not self.db.is_url_seen(url_hash)

    def mark_seen(self, url: str):
        """标记 URL 为已抓取"""
        url_hash = self.hash_url(url)
        self.db.insert_url(url_hash, url)
