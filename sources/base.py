from abc import ABC, abstractmethod
from typing import List, Dict


class BaseSource(ABC):
    """抽象基类，所有数据源必须继承此类"""

    def __init__(self, config: dict):
        self.config = config
        self._session = None

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass

    @property
    @abstractmethod
    def source_url(self) -> str:
        """数据源首页 URL"""
        pass

    @abstractmethod
    def fetch(self) -> List[Dict]:
        """爬取数据，返回列表，每个元素为 dict：
        {
            'title': str,
            'url': str,
            'date': str,
            'summary': str,
            'source_name': str,
            'category': str  # 可选，默认留空由 classifier 处理
        }
        """
        pass

    @property
    def session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            ua = self.config.get('request', {}).get(
                'user_agent',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            timeout = self.config.get('request', {}).get('timeout', 30)
            self._session.headers.update({'User-Agent': ua})
            self._session.timeout = timeout
        return self._session

    @staticmethod
    def make_lead(title: str, url: str, date: str = '',
                  summary: str = '', source_name: str = '',
                  category: str = '') -> Dict:
        return {
            'title': title.strip(),
            'url': url.strip(),
            'date': date.strip(),
            'summary': summary.strip(),
            'source_name': source_name.strip(),
            'category': category.strip(),
        }
