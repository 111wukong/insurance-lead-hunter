import logging
import time
from typing import List, Dict
from bs4 import BeautifulSoup
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

    def fetch(self) -> List[Dict]:
        results = []
        base_url = "http://www.ccgp-sichuan.gov.cn"

        # 巴中地区采购公告
        urls_to_try = [
            f"{base_url}/freecms/site/sichuan/bazhong/index.html",
            f"{base_url}/freecms/site/sichuan/bazhong/",
            f"{base_url}/freecms/site/sichuan/",
        ]

        for list_url in urls_to_try:
            try:
                logger.info(f"[{self.name}] 正在请求: {list_url}")
                soup = self.get(list_url, timeout=30)
                if not soup:
                    continue

                items = self._extract_items(soup, base_url)
                for item in items:
                    if self._has_insurance_keyword(item.get('title', '')):
                        item['source_name'] = self.name
                        results.append(item)

                time.sleep(self.config.get('request', {}).get('interval', 2))
            except Exception as e:
                logger.warning(f"[{self.name}] 请求 {list_url} 失败: {e}")
                continue

        logger.info(f"[{self.name}] 抓取到 {len(results)} 条保险相关数据")
        return results

    def _extract_items(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        items = []

        # 策略1: 在 class 含 info/list/news 的区域找列表
        for container in soup.find_all(['div', 'ul'], class_=lambda c: c and any(
                kw in str(c).lower() for kw in ['info', 'list', 'news', 'article'])):
            for li in container.find_all('li'):
                link = li.find('a')
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link.get('href', '')
                if href:
                    if not href.startswith('http'):
                        if href.startswith('/'):
                            href = base_url + href
                        elif href.startswith('./'):
                            href = base_url + href[1:]
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

        # 策略2: 遍历所有链接
        for link in soup.find_all('a', href=True):
            title = link.get_text(strip=True)
            if len(title) < 5:
                continue
            href = link['href']
            if not href.startswith('http'):
                if href.startswith('/'):
                    href = base_url + href
                else:
                    href = base_url + '/' + href
            items.append(self.make_lead(
                title=title,
                url=href,
                date='',
                source_name=self.name,
            ))

        return items

    def _has_insurance_keyword(self, text: str) -> bool:
        keywords = [
            '保险', '保费', '投保', '承保', '理赔', '共保',
            '意外伤害保险', '补充医疗保险', '大病保险',
            '政府采购保险', '政府购买保险', '车辆保险',
            '公众责任险', '雇主责任险', '财产保险',
            '农业保险', '健康保险',
        ]
        return any(kw in text for kw in keywords)
