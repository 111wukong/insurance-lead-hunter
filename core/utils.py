"""Shared utility functions for the insurance-lead-hunter project."""

import hashlib
from typing import List
from urllib.parse import urljoin


def url_hash(url: str) -> str:
    """Generate MD5 hash for a URL (used for deduplication)."""
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def normalize_url(href: str, base_url: str) -> str:
    """Normalize a relative URL to an absolute URL.

    Handles common patterns: absolute URLs returned as-is,
    relative paths resolved against base_url.
    """
    if not href:
        return href
    if href.startswith('http'):
        return href
    if href.startswith('./'):
        href = href[1:]
    if not href.startswith('/'):
        href = '/' + href
    return base_url.rstrip('/') + href


def has_keyword_match(text: str, keywords: List[str]) -> bool:
    """Check if any keyword appears in text."""
    return any(kw in text for kw in keywords)


# Default insurance keywords used across sources for filtering
INSURANCE_KEYWORDS = [
    '保险', '保费', '投保', '承保', '理赔', '共保', '再保险',
    '意外伤害', '补充医疗', '大病保险', '车险', '责任险',
    '财产险', '财产保险', '公众责任', '雇主责任', '车辆保险',
    '建筑工程一切险', '安装工程一切险', '安全生产责任险',
    '政府采购保险', '政府购买保险', '健康保险', '农业保险',
]
