import logging

from core.utils import url_hash
from storage.db import Database

logger = logging.getLogger(__name__)


class Deduplicator:
    """基于 URL MD5 哈希的去重器"""

    def __init__(self, db: Database):
        self.db = db

    def is_new(self, url: str) -> bool:
        """检查 URL 是否为新（未抓取过）"""
        return not self.db.is_url_seen(url_hash(url))

    def mark_seen(self, url: str):
        """标记 URL 为已抓取"""
        self.db.insert_url(url_hash(url), url)
