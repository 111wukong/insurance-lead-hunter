import logging
import time
from typing import List, Dict
from bs4 import BeautifulSoup
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

    def fetch(self) -> List[Dict]:
        results = []
        base_url = "https://bazhong.tfygcgfw.com"

        # 招标公告列表页
        urls_to_try = [
            f"{base_url}/bulletins",
            f"{base_url}/bulletins?category=ZBGG",
            f"{base_url}/",
        ]

        for list_url in urls_to_try:
            try:
                logger.info(f"[{self.name}] 正在请求: {list_url}")
                resp = self.session.get(list_url, timeout=30)
                resp.encoding = resp.apparent_encoding or 'utf-8'
                soup = BeautifulSoup(resp.text, 'lxml')

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
                href = link.get('href', '')
                if href and not href.startswith('http'):
                    href = base_url + (href if href.startswith('/') else '/' + href)
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
                if not href.startswith('http'):
                    href = base_url + (href if href.startswith('/') else '/' + href)
                items.append(self.make_lead(
                    title=title,
                    url=href,
                    date='',
                    source_name=self.name,
                ))

        return items

    def _has_insurance_keyword(self, text: str) -> bool:
        keywords = [
            '保险', '保费', '投保', '承保', '理赔', '共保', '再保险',
            '意外伤害', '补充医疗', '大病保险', '车险', '责任险',
            '财产险', '财产保险', '公众责任', '雇主责任', '车辆保险',
            '建筑工程一切险', '安装工程一切险', '安全生产责任险',
        ]
        return any(kw in text for kw in keywords)
