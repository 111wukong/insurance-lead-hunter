import logging
from typing import List, Dict

from bs4 import BeautifulSoup

from core.utils import normalize_url
from sources.base import BaseSource

logger = logging.getLogger(__name__)


class TianfuTenderSource(BaseSource):
    """天府阳光采购服务平台 - 巴中分站"""

    @property
    def name(self) -> str:
        return "天府阳光采购平台(巴中)"

    @property
    def source_url(self) -> str:
        return "https://bazhong.tfygcgfw.com"

    def get_list_urls(self) -> List[str]:
        base_url = self.source_url
        return [
            f"{base_url}/bulletins",
            f"{base_url}/bulletins?category=ZBGG",
            f"{base_url}/",
        ]

    def extract_items(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        items = []

        # 策略1: 查找表格
        tables = soup.find_all('table')
        for table in tables:
            for tr in table.find_all('tr')[1:]:
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

        # 策略2: 遍历链接
        for link in soup.find_all('a', href=True):
            title = link.get_text(strip=True)
            if len(title) < 5:
                continue
            href = link['href']
            if any(kw in href.lower() for kw in ['bulletindetail', 'bulletin', 'detail', 'news']):
                href = normalize_url(href, base_url)
                items.append(self.make_lead(
                    title=title,
                    url=href,
                    date='',
                    source_name=self.name,
                ))

        return items
