import logging
from typing import List, Dict

from bs4 import BeautifulSoup

from core.utils import normalize_url
from sources.base import BaseSource

logger = logging.getLogger(__name__)


class SichuanProcureSource(BaseSource):
    """四川省政府采购网 - 巴中分站"""

    @property
    def name(self) -> str:
        return "四川政府采购网(巴中)"

    @property
    def source_url(self) -> str:
        return "http://www.ccgp-sichuan.gov.cn"

    def get_list_urls(self) -> List[str]:
        base_url = self.source_url
        return [
            f"{base_url}/freecms/site/sichuan/bazhong/index.html",
            f"{base_url}/freecms/site/sichuan/bazhong/",
            f"{base_url}/freecms/site/sichuan/",
        ]

    def extract_items(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        items = []

        # 策略1: 在 class 含 info/list/news 的区域找列表
        for container in soup.find_all(['div', 'ul'], class_=lambda c: c and any(
                kw in str(c).lower() for kw in ['info', 'list', 'news', 'article'])):
            for li in container.find_all('li'):
                link = li.find('a')
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = normalize_url(link.get('href', ''), base_url)
                date_span = li.find('span')
                date = date_span.get_text(strip=True) if date_span else ''
                items.append(self.make_lead(
                    title=title,
                    url=href,
                    date=date,
                    source_name=self.name,
                ))

        if items:
            return items

        # 策略2: 遍历所有链接
        for link in soup.find_all('a', href=True):
            title = link.get_text(strip=True)
            if len(title) < 5:
                continue
            href = normalize_url(link['href'], base_url)
            items.append(self.make_lead(
                title=title,
                url=href,
                date='',
                source_name=self.name,
            ))

        return items
