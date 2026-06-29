import logging
from typing import List, Dict

from bs4 import BeautifulSoup

from core.utils import normalize_url
from sources.base import BaseSource

logger = logging.getLogger(__name__)


class BazhongTenderSource(BaseSource):
    """巴中市公共资源交易平台"""

    @property
    def name(self) -> str:
        return "巴中公共资源交易平台"

    @property
    def source_url(self) -> str:
        return "https://www.bzsggzy.com"

    def get_list_urls(self) -> List[str]:
        base_url = self.source_url
        return [
            f"{base_url}/jyxx/004001/004001001/",
            f"{base_url}/jyxx/004001/004001002/",
            f"{base_url}/jyxx/004001/",
        ]

    def extract_items(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """使用多种策略提取公告列表"""
        items = []

        # 策略1: 查找 table 中的公告列表
        tables = soup.find_all('table')
        for table in tables:
            for tr in table.find_all('tr')[1:]:  # 跳过表头
                tds = tr.find_all('td')
                if len(tds) < 2:
                    continue
                link = tr.find('a')
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = normalize_url(link.get('href', ''), base_url)
                date = tds[-1].get_text(strip=True) if tds else ''
                items.append(self.make_lead(
                    title=title,
                    url=href,
                    date=date,
                    source_name=self.name,
                ))
        if items:
            return items

        # 策略2: 查找 li 列表
        ul = soup.find('ul', class_=lambda c: c and ('list' in c or 'news' in c))
        if not ul:
            ul = soup.find('ul')
        if ul:
            for li in ul.find_all('li'):
                link = li.find('a')
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = normalize_url(link.get('href', ''), base_url)
                span = li.find('span')
                date = span.get_text(strip=True) if span else ''
                items.append(self.make_lead(
                    title=title,
                    url=href,
                    date=date,
                    source_name=self.name,
                ))

        return items
