import os
import sys
import pytest

# Ensure project root is on sys.path so that `from core…`, `from storage…`, etc. work.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def sample_config():
    """Minimal configuration dict used across tests."""
    return {
        'database': {'path': ':memory:'},
        'request': {
            'user_agent': 'TestAgent/1.0',
            'timeout': 5,
            'interval': 0,
        },
        'categories': {
            '工程类': {'keywords': ['工程', '施工', '建筑'], 'priority': 'high'},
            '车辆类': {'keywords': ['车辆', '车险'], 'priority': 'high'},
            '责任险类': {'keywords': ['责任险', '雇主'], 'priority': 'high'},
            '政府项目类': {'keywords': ['政府采购', '政府购买'], 'priority': 'medium'},
            '其他保险': {'keywords': ['保险', '保费'], 'priority': 'low'},
        },
        'feishu': {'enabled': False},
        'clean': {'retention_days': 30},
        'logging': {'level': 'WARNING'},
    }


@pytest.fixture
def in_memory_db(sample_config):
    """Return a Database instance backed by an in-memory SQLite database."""
    from storage.db import Database

    db = Database(sample_config)
    db.init_db()
    yield db
    db.close()


@pytest.fixture
def sample_lead():
    """A single lead dict used across tests."""
    return {
        'title': '巴中市某工程施工招标公告',
        'url': 'https://example.com/tender/123',
        'date': '2026-06-28',
        'summary': '某建筑工程项目施工招标',
        'source_name': '巴中公共资源交易平台',
        'category': '工程类',
    }
