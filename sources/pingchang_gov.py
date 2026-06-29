import logging
from typing import List, Dict

from bs4 import BeautifulSoup

from core.utils import has_keyword_match, normalize_url
from sources.base import BaseSource

logger = logging.getLogger(__name__)

# Commercial keywords required for relevance
_COMMERCIAL_KEYWORDS = ['招标', '采购', '项目', '工程', '建设', '中标', '成交', '公告']
_GENERAL_KEYWORDS = [
    '工程', '施工', '建筑', '工地', '建设', '招标', '采购',
    '项目', '保险', '车辆', '交通', '农业', '医疗',
    '公示', '公告', '中标', '成交',
]


class PingchangGovSource(BaseSource):
    """平昌县人民政府网"""

    @property
    def name(self) -> str:
        return "平昌县人民政府网"

    @property
    def source_url(self) -> str:
        return "http://www.scpc.gov.cn"

    def get_list_urls(self) -> List[str]:
        base_url = self.source_url
        paths = [
            "/public/column/6603621?type=4&action=list",
            "/public/column/6603621?type=4&catId=506",
            "/clxx/",
        ]
        return [base_url + path for path in paths]

    def is_relevant(self, item: Dict) -> bool:
        """Filter: must have both a commercial keyword and a general keyword."""
        text = item.get('title', '') + item.get('summary', '')
        has_commercial = has_keyword_match(text, _COMMERCIAL_KEYWORDS)
        has_general = has_keyword_match(text, _GENERAL_KEYWORDS)
        return has_commercial and has_general

    def extract_items(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        items = []

        # 策略1: 查找class含list的ul
        for ul_tag in soup.find_all(['ul', 'div'], class_=lambda c: c and 'list' in str(c).lower()):
            for li in ul_tag.find_all('li'):
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

        # 策略2: 查找所有含链接的li
        for li in soup.find_all('li'):
            link = li.find('a')
            if not link:
                continue
            title = link.get_text(strip=True)
            if len(title) < 5:
                continue
            href = normalize_url(link.get('href', ''), base_url)
            date_span = li.find('span')
            date = date_span.get_text(strip=True) if date_span else ''
            items.append(self.make_lead(
                title=title,
                url=href,
                date=date,
                source_name=self.name,
            ))

        return items
