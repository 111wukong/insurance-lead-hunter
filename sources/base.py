import logging
import subprocess
import time
from abc import ABC, abstractmethod
from typing import List, Dict

from bs4 import BeautifulSoup

from core.utils import INSURANCE_KEYWORDS, has_keyword_match, normalize_url

logger = logging.getLogger(__name__)


class BaseSource(ABC):
    """抽象基类，使用 curl 绕过 geo-block"""

    def __init__(self, config: dict):
        self.config = config
        self.ua = config.get('request', {}).get(
            'user_agent',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        self.timeout = config.get('request', {}).get('timeout', 30)
        self.interval = config.get('request', {}).get('interval', 2)

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def source_url(self) -> str:
        pass

    @abstractmethod
    def get_list_urls(self) -> List[str]:
        """Return the list of URLs to crawl for this source."""
        pass

    @abstractmethod
    def extract_items(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract lead items from a parsed page."""
        pass

    def is_relevant(self, item: Dict) -> bool:
        """Filter items for relevance. Default: check insurance keywords in title."""
        return has_insurance_keyword(item.get('title', ''))

    def fetch(self) -> List[Dict]:
        """Template method: iterate list URLs, extract items, filter, return results."""
        results = []
        base_url = self.source_url

        for list_url in self.get_list_urls():
            try:
                logger.info(f"[{self.name}] 正在请求: {list_url}")
                soup = self.get(list_url, timeout=self.timeout)
                if not soup:
                    continue

                items = self.extract_items(soup, base_url)
                for item in items:
                    if self.is_relevant(item):
                        item['source_name'] = self.name
                        results.append(item)

                time.sleep(self.interval)
            except Exception as e:
                logger.warning(f"[{self.name}] 请求 {list_url} 失败: {e}")
                continue

        logger.info(f"[{self.name}] 抓取到 {len(results)} 条相关数据")
        return results

    def get(self, url: str, timeout: int = None) -> BeautifulSoup:
        """使用 curl 获取页面（绕过 geo-block）"""
        t = timeout or self.timeout
        try:
            result = subprocess.run([
                'curl', '-s', '-L',
                '-H', f'User-Agent: {self.ua}',
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                '-H', 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
                '--connect-timeout', str(t),
                '--max-time', str(t + 5),
                url
            ], capture_output=True, text=True, timeout=t + 10)
            if result.returncode == 0 and len(result.stdout) > 500:
                return BeautifulSoup(result.stdout, 'lxml')
            logger.warning(f"[{self.name}] curl failed for {url}: code={result.returncode}, len={len(result.stdout)}")
            return None
        except Exception as e:
            logger.warning(f"[{self.name}] curl error for {url}: {e}")
            return None

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


def has_insurance_keyword(text: str) -> bool:
    """Check if text contains any insurance-related keyword."""
    return has_keyword_match(text, INSURANCE_KEYWORDS)
