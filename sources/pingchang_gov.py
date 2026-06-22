import logging
import time
from typing import List, Dict
from bs4 import BeautifulSoup
from sources.base import BaseSource

logger = logging.getLogger(__name__)


class PingchangGovSource(BaseSource):
    """平昌县人民政府网"""

    @property
    def name(self) -> str:
        return "平昌县人民政府网"

    @property
    def source_url(self) -> str:
        return "http://www.scpc.gov.cn"

    def fetch(self) -> List[Dict]:
        results = []
        base_url = "http://www.scpc.gov.cn"

        # 公示公告 & 政务公开
        paths = [
            "/public/column/6603621?type=4&action=list",
            "/public/column/6603621?type=4&catId=506",
            "/clxx/",
        ]

        for path in paths:
            try:
                list_url = base_url + path
                logger.info(f"[{self.name}] 正在请求: {list_url}")
                soup = self.get(list_url, timeout=30)
                if not soup:
                    continue

                items = self._extract_items(soup, base_url)
                for item in items:
                    if self._is_relevant(item.get('title', ''), item.get('summary', '')):
                        item['source_name'] = self.name
                        results.append(item)

                time.sleep(self.config.get('request', {}).get('interval', 2))
            except Exception as e:
                logger.warning(f"[{self.name}] 请求 {list_url} 失败: {e}")
                continue

        logger.info(f"[{self.name}] 抓取到 {len(results)} 条相关数据")
        return results

    def _extract_items(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        items = []

        # 策略1: 查找class含list的ul
        for ul_tag in soup.find_all(['ul', 'div'], class_=lambda c: c and 'list' in str(c).lower()):
            for li in ul_tag.find_all('li'):
                link = li.find('a')
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link.get('href', '')
                if href and not href.startswith('http'):
                    if href.startswith('/'):
                        href = base_url + href
                    else:
                        href = base_url + '/' + href
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
            href = link.get('href', '')
            if href and not href.startswith('http'):
                if href.startswith('/'):
                    href = base_url + href
                else:
                    href = base_url + '/' + href
            date_span = li.find('span')
            date = date_span.get_text(strip=True) if date_span else ''
            items.append(self.make_lead(
                title=title,
                url=href,
                date=date,
                source_name=self.name,
            ))

        return items

    def _is_relevant(self, title: str, summary: str = '') -> bool:
        text = title + summary
        keywords = [
            '工程', '施工', '建筑', '工地', '建设', '招标', '采购',
            '项目', '保险', '车辆', '交通', '农业', '医疗',
            '公示', '公告', '中标', '成交',
        ]
        # 过滤掉纯新闻（不含招标/采购/项目等商业关键词的）
        commercial_kw = ['招标', '采购', '项目', '工程', '建设', '中标', '成交', '公告']
        has_commercial = any(kw in text for kw in commercial_kw)
        has_keyword = any(kw in text for kw in keywords)
        return has_commercial and has_keyword
