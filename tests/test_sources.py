import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from sources.base import BaseSource
from sources.bazhong_tender import BazhongTenderSource
from sources.pingchang_gov import PingchangGovSource
from sources.tianfu_tender import TianfuTenderSource
from sources.sichuan_procure import SichuanProcureSource


# ---------- BaseSource ----------

class ConcreteSource(BaseSource):
    """Concrete subclass for testing the abstract BaseSource."""

    @property
    def name(self) -> str:
        return 'TestSource'

    @property
    def source_url(self) -> str:
        return 'https://test.example.com'

    def fetch(self):
        return []


class TestBaseSource:
    def test_make_lead(self):
        lead = BaseSource.make_lead(
            title='  Test Title  ', url='  https://example.com  ',
            date='  2026-01-01  ', summary='  Summary  ',
            source_name='  Src  ', category='  Cat  ',
        )
        assert lead['title'] == 'Test Title'
        assert lead['url'] == 'https://example.com'
        assert lead['date'] == '2026-01-01'
        assert lead['summary'] == 'Summary'

    def test_properties(self, sample_config):
        src = ConcreteSource(sample_config)
        assert src.name == 'TestSource'
        assert src.source_url == 'https://test.example.com'
        assert src.ua == sample_config['request']['user_agent']
        assert src.timeout == sample_config['request']['timeout']

    @patch('sources.base.subprocess.run')
    def test_get_success(self, mock_run, sample_config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='<html><body>' + 'x' * 600 + '</body></html>',
        )
        src = ConcreteSource(sample_config)
        soup = src.get('https://test.example.com')
        assert soup is not None
        assert isinstance(soup, BeautifulSoup)

    @patch('sources.base.subprocess.run')
    def test_get_failure_short_response(self, mock_run, sample_config):
        mock_run.return_value = MagicMock(returncode=0, stdout='short')
        src = ConcreteSource(sample_config)
        result = src.get('https://test.example.com')
        assert result is None

    @patch('sources.base.subprocess.run')
    def test_get_failure_nonzero_return(self, mock_run, sample_config):
        mock_run.return_value = MagicMock(returncode=1, stdout='error' * 200)
        src = ConcreteSource(sample_config)
        result = src.get('https://test.example.com')
        assert result is None

    @patch('sources.base.subprocess.run', side_effect=Exception('timeout'))
    def test_get_exception(self, mock_run, sample_config):
        src = ConcreteSource(sample_config)
        result = src.get('https://test.example.com')
        assert result is None


# ---------- BazhongTenderSource ----------

class TestBazhongTenderSource:
    def test_name_and_url(self, sample_config):
        src = BazhongTenderSource(sample_config)
        assert src.name == '巴中公共资源交易平台'
        assert 'bzsggzy' in src.source_url

    def test_has_insurance_keyword_true(self, sample_config):
        src = BazhongTenderSource(sample_config)
        assert src._has_insurance_keyword('保险服务采购') is True
        assert src._has_insurance_keyword('车险投标') is True

    def test_has_insurance_keyword_false(self, sample_config):
        src = BazhongTenderSource(sample_config)
        assert src._has_insurance_keyword('天气预报') is False

    def test_extract_items_from_table(self, sample_config):
        html = '''
        <html><body>
        <table>
            <tr><th>标题</th><th>日期</th></tr>
            <tr><td><a href="/tender/1">保险采购公告</a></td><td>2026-06-28</td></tr>
            <tr><td><a href="https://example.com/2">车险招标</a></td><td>2026-06-27</td></tr>
        </table>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = BazhongTenderSource(sample_config)
        items = src._extract_items(soup, 'https://www.bzsggzy.com')
        assert len(items) == 2
        assert items[0]['url'].startswith('https://www.bzsggzy.com/')
        assert items[1]['url'] == 'https://example.com/2'

    def test_extract_items_from_ul(self, sample_config):
        html = '''
        <html><body>
        <ul class="news-list">
            <li><a href="/item/1">工程保险招标</a><span>2026-06-28</span></li>
        </ul>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = BazhongTenderSource(sample_config)
        items = src._extract_items(soup, 'https://www.bzsggzy.com')
        assert len(items) == 1
        assert items[0]['date'] == '2026-06-28'

    @patch.object(BazhongTenderSource, 'get', return_value=None)
    def test_fetch_returns_empty_on_failure(self, mock_get, sample_config):
        src = BazhongTenderSource(sample_config)
        result = src.fetch()
        assert result == []


# ---------- PingchangGovSource ----------

class TestPingchangGovSource:
    def test_name(self, sample_config):
        src = PingchangGovSource(sample_config)
        assert src.name == '平昌县人民政府网'

    def test_is_relevant_true(self, sample_config):
        src = PingchangGovSource(sample_config)
        assert src._is_relevant('工程招标公告') is True
        assert src._is_relevant('政府采购项目公示') is True

    def test_is_relevant_false(self, sample_config):
        src = PingchangGovSource(sample_config)
        assert src._is_relevant('天气预报通知') is False

    def test_is_relevant_needs_commercial_keyword(self, sample_config):
        src = PingchangGovSource(sample_config)
        # Has keyword '保险' but no commercial keyword
        assert src._is_relevant('保险知识科普') is False

    def test_extract_items_from_list_div(self, sample_config):
        html = '''
        <html><body>
        <div class="info-list">
            <li><a href="/news/1">招标公告</a><span>2026-06-28</span></li>
        </div>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = PingchangGovSource(sample_config)
        items = src._extract_items(soup, 'http://www.scpc.gov.cn')
        assert len(items) == 1

    def test_extract_items_fallback_strategy(self, sample_config):
        html = '''
        <html><body>
        <li><a href="/page/1">这是一条较长的公告标题用于测试</a><span>2026-06-28</span></li>
        <li><a href="/page/2">短</a></li>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = PingchangGovSource(sample_config)
        items = src._extract_items(soup, 'http://www.scpc.gov.cn')
        # Only the item with title >= 5 chars should be included
        assert len(items) == 1

    @patch.object(PingchangGovSource, 'get', return_value=None)
    def test_fetch_returns_empty_on_failure(self, mock_get, sample_config):
        src = PingchangGovSource(sample_config)
        result = src.fetch()
        assert result == []


# ---------- TianfuTenderSource ----------

class TestTianfuTenderSource:
    def test_name(self, sample_config):
        src = TianfuTenderSource(sample_config)
        assert '天府' in src.name

    def test_has_insurance_keyword_true(self, sample_config):
        src = TianfuTenderSource(sample_config)
        assert src._has_insurance_keyword('建筑工程一切险招标') is True

    def test_has_insurance_keyword_false(self, sample_config):
        src = TianfuTenderSource(sample_config)
        assert src._has_insurance_keyword('办公用品采购') is False

    def test_extract_items_from_table(self, sample_config):
        html = '''
        <html><body>
        <table>
            <tr><th>项目</th><th>日期</th></tr>
            <tr><td><a href="/detail/1">保险采购</a></td><td>2026-06-28</td></tr>
        </table>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = TianfuTenderSource(sample_config)
        items = src._extract_items(soup, 'https://bazhong.tfygcgfw.com')
        assert len(items) == 1

    def test_extract_items_fallback_links(self, sample_config):
        html = '''
        <html><body>
        <a href="/bulletindetail/123">这是一条较长的采购公告标题</a>
        <a href="/short">短</a>
        <a href="javascript:void(0)">不是有效链接但足够长的文字</a>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = TianfuTenderSource(sample_config)
        items = src._extract_items(soup, 'https://bazhong.tfygcgfw.com')
        assert len(items) >= 1

    @patch.object(TianfuTenderSource, 'get', return_value=None)
    def test_fetch_returns_empty_on_failure(self, mock_get, sample_config):
        src = TianfuTenderSource(sample_config)
        result = src.fetch()
        assert result == []


# ---------- SichuanProcureSource ----------

class TestSichuanProcureSource:
    def test_name(self, sample_config):
        src = SichuanProcureSource(sample_config)
        assert '四川' in src.name

    def test_has_insurance_keyword_true(self, sample_config):
        src = SichuanProcureSource(sample_config)
        assert src._has_insurance_keyword('政府采购保险服务') is True

    def test_has_insurance_keyword_false(self, sample_config):
        src = SichuanProcureSource(sample_config)
        assert src._has_insurance_keyword('办公家具采购') is False

    def test_extract_items_from_info_list(self, sample_config):
        html = '''
        <html><body>
        <div class="info-list">
            <li><a href="/page/1">公众责任险采购公告</a><span>2026-06-28</span></li>
        </div>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = SichuanProcureSource(sample_config)
        items = src._extract_items(soup, 'http://www.ccgp-sichuan.gov.cn')
        assert len(items) == 1

    def test_extract_items_relative_url_handling(self, sample_config):
        html = '''
        <html><body>
        <ul class="news-list">
            <li><a href="./detail/1">保险公告</a></li>
            <li><a href="detail/2">另一条</a></li>
            <li><a href="/abs/3">绝对路径</a></li>
        </ul>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = SichuanProcureSource(sample_config)
        base = 'http://www.ccgp-sichuan.gov.cn'
        items = src._extract_items(soup, base)
        assert len(items) == 3
        # Check URL normalization
        assert items[0]['url'].startswith(base)
        assert items[1]['url'].startswith(base)
        assert items[2]['url'] == base + '/abs/3'

    def test_extract_items_fallback_links(self, sample_config):
        html = '''
        <html><body>
        <a href="/page/abc">这是一条非常长的公告链接标题</a>
        <a href="/x">短</a>
        </body></html>
        '''
        soup = BeautifulSoup(html, 'lxml')
        src = SichuanProcureSource(sample_config)
        items = src._extract_items(soup, 'http://www.ccgp-sichuan.gov.cn')
        assert len(items) >= 1

    @patch.object(SichuanProcureSource, 'get', return_value=None)
    def test_fetch_returns_empty_on_failure(self, mock_get, sample_config):
        src = SichuanProcureSource(sample_config)
        result = src.fetch()
        assert result == []
