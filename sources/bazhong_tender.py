import logging
import time
from typing import List, Dict
from bs4 import BeautifulSoup
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

    def fetch(self) -> List[Dict]:
        results = []
        base_url = "https://www.bzsggzy.com"

        # 招标公告列表页
        urls_to_try = [
            f"{base_url}/jyxx/004001/004001001/",
            f"{base_url}/jyxx/004001/004001002/",
            f"{base_url}/jyxx/004001/",
        ]

        for list_url in urls_to_try:
            try:
                logger.info(f"[{self.name}] 正在请求: {list_url}")
                soup = self.get(list_url, timeout=30)
                if not soup:
                    continue

                # 尝试多种页面结构来提取公告列表
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
                href = link.get('href', '')
                if href and not href.startswith('http'):
                    href = base_url + (href if href.startswith('/') else '/' + href)
                span = li.find('span')
                date = span.get_text(strip=True) if span else ''
                items.append(self.make_lead(
                    title=title,
                    url=href,
                    date=date,
                    source_name=self.name,
                ))

        return items

    def _has_insurance_keyword(self, text: str) -> bool:
        keywords = ['保险', '保费', '投保', '承保', '理赔', '共保', '再保险',
                    '意外伤害', '补充医疗', '大病保险', '车险', '责任险',
                    '财产险', '财产保险', '公众责任', '雇主责任']
        return any(kw in text for kw in keywords)
