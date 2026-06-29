import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from core.engine import Engine


@pytest.fixture
def engine_config(tmp_path):
    """Config with a file-based DB (Engine opens its own connection)."""
    return {
        'database': {'path': str(tmp_path / 'test.db')},
        'request': {'user_agent': 'Test/1.0', 'timeout': 5, 'interval': 0},
        'categories': {
            '工程类': {'keywords': ['工程', '施工'], 'priority': 'high'},
            '其他保险': {'keywords': ['保险'], 'priority': 'low'},
        },
        'feishu': {'enabled': False},
        'clean': {'retention_days': 30},
        'logging': {'level': 'WARNING'},
    }


def _make_engine(config):
    """Create an Engine and initialize the database."""
    engine = Engine(config)
    engine.init_db()
    return engine


class TestEngine:
    def test_init_db(self, engine_config):
        engine = _make_engine(engine_config)
        stats = engine.show_stats()
        assert stats['total'] == 0
        engine.db.close()

    def test_show_stats(self, engine_config):
        engine = _make_engine(engine_config)
        stats = engine.show_stats()
        assert 'total' in stats
        assert 'new' in stats
        assert 'by_category' in stats
        engine.db.close()

    def test_clean_old_data(self, engine_config):
        engine = _make_engine(engine_config)
        engine.clean_old_data()  # should not raise on empty db
        engine.db.close()

    @patch('core.engine.BazhongTenderSource')
    @patch('core.engine.PingchangGovSource')
    @patch('core.engine.TianfuTenderSource')
    @patch('core.engine.SichuanProcureSource')
    def test_run_all_dry_run(self, MockSichuan, MockTianfu,
                              MockPingchang, MockBazhong, engine_config):
        """dry_run should not persist leads."""
        mock_source = MagicMock()
        mock_source.name = '测试源'
        mock_source.fetch.return_value = [
            {'title': '工程施工招标', 'url': 'https://example.com/1',
             'summary': '', 'source_name': '测试源', 'category': ''},
        ]
        MockBazhong.return_value = mock_source
        MockPingchang.return_value = MagicMock(name='src2', fetch=MagicMock(return_value=[]))
        MockTianfu.return_value = MagicMock(name='src3', fetch=MagicMock(return_value=[]))
        MockSichuan.return_value = MagicMock(name='src4', fetch=MagicMock(return_value=[]))

        # Set name property on mock sources
        MockPingchang.return_value.name = '平昌'
        MockTianfu.return_value.name = '天府'
        MockSichuan.return_value.name = '四川'

        engine = _make_engine(engine_config)
        stats = engine.run_all(dry_run=True)
        assert stats['total_fetched'] == 1
        assert stats['new_leads'] == 1

        # Verify nothing was persisted
        db_leads = engine.db.get_new_leads()
        assert len(db_leads) == 0
        engine.db.close()

    @patch('core.engine.BazhongTenderSource')
    @patch('core.engine.PingchangGovSource')
    @patch('core.engine.TianfuTenderSource')
    @patch('core.engine.SichuanProcureSource')
    def test_run_all_persists_leads(self, MockSichuan, MockTianfu,
                                     MockPingchang, MockBazhong, engine_config):
        mock_source = MagicMock()
        mock_source.name = '测试源'
        mock_source.fetch.return_value = [
            {'title': '保险采购公告', 'url': 'https://example.com/ins1',
             'summary': '', 'source_name': '测试源', 'category': ''},
        ]
        MockBazhong.return_value = mock_source
        MockPingchang.return_value = MagicMock(name='src2', fetch=MagicMock(return_value=[]))
        MockTianfu.return_value = MagicMock(name='src3', fetch=MagicMock(return_value=[]))
        MockSichuan.return_value = MagicMock(name='src4', fetch=MagicMock(return_value=[]))
        MockPingchang.return_value.name = '平昌'
        MockTianfu.return_value.name = '天府'
        MockSichuan.return_value.name = '四川'

        engine = _make_engine(engine_config)
        stats = engine.run_all(dry_run=False)
        assert stats['new_leads'] == 1

        db_leads = engine.db.get_new_leads()
        assert len(db_leads) == 1
        assert db_leads[0]['category'] == '其他保险'
        engine.db.close()

    @patch('core.engine.BazhongTenderSource')
    @patch('core.engine.PingchangGovSource')
    @patch('core.engine.TianfuTenderSource')
    @patch('core.engine.SichuanProcureSource')
    def test_run_all_dedup(self, MockSichuan, MockTianfu,
                           MockPingchang, MockBazhong, engine_config):
        """Running twice should not duplicate leads."""
        mock_source = MagicMock()
        mock_source.name = '测试源'
        mock_source.fetch.return_value = [
            {'title': '重复公告', 'url': 'https://example.com/dup',
             'summary': '', 'source_name': '测试源', 'category': ''},
        ]
        MockBazhong.return_value = mock_source
        MockPingchang.return_value = MagicMock(name='p', fetch=MagicMock(return_value=[]))
        MockTianfu.return_value = MagicMock(name='t', fetch=MagicMock(return_value=[]))
        MockSichuan.return_value = MagicMock(name='s', fetch=MagicMock(return_value=[]))
        MockPingchang.return_value.name = '平昌'
        MockTianfu.return_value.name = '天府'
        MockSichuan.return_value.name = '四川'

        engine = _make_engine(engine_config)
        engine.run_all(dry_run=False)
        stats2 = engine.run_all(dry_run=False)
        assert stats2['new_leads'] == 0
        engine.db.close()

    @patch('core.engine.BazhongTenderSource')
    @patch('core.engine.PingchangGovSource')
    @patch('core.engine.TianfuTenderSource')
    @patch('core.engine.SichuanProcureSource')
    def test_run_all_source_exception(self, MockSichuan, MockTianfu,
                                       MockPingchang, MockBazhong, engine_config):
        """A failing source should not crash the engine."""
        mock_source = MagicMock()
        mock_source.name = '坏源'
        mock_source.fetch.side_effect = Exception('network error')
        MockBazhong.return_value = mock_source
        MockPingchang.return_value = MagicMock(name='p', fetch=MagicMock(return_value=[]))
        MockTianfu.return_value = MagicMock(name='t', fetch=MagicMock(return_value=[]))
        MockSichuan.return_value = MagicMock(name='s', fetch=MagicMock(return_value=[]))
        MockPingchang.return_value.name = '平昌'
        MockTianfu.return_value.name = '天府'
        MockSichuan.return_value.name = '四川'

        engine = _make_engine(engine_config)
        stats = engine.run_all()
        assert 'ERROR' in str(stats['by_source'].get('坏源', ''))
        engine.db.close()

    def test_generate_report_empty(self, engine_config):
        engine = _make_engine(engine_config)
        stats = engine.generate_report()
        assert stats['new_leads'] == 0
        engine.db.close()

    def test_generate_report_with_data(self, engine_config):
        engine = _make_engine(engine_config)
        engine.db.insert_lead({
            'title': '工程施工招标', 'url': 'https://example.com/1',
            'summary': '', 'source_name': '测试源', 'category': '工程类',
            'date': '2026-06-28', 'amount': '', 'contact_info': '',
        })
        stats = engine.generate_report()
        assert stats['new_leads'] == 1
        assert '工程类' in stats['by_category']
        engine.db.close()

    def test_send_notification_disabled(self, engine_config):
        engine = _make_engine(engine_config)
        # Should not raise even with leads
        engine._send_notification([{'title': 'test'}], {'new_leads': 1})
        engine.db.close()

    def test_send_notification_enabled_calls_notifier(self, engine_config):
        engine_config['feishu'] = {'enabled': True, 'webhook_url': 'https://test/hook'}
        engine = _make_engine(engine_config)
        with patch.object(engine.notifier, 'send_daily_report') as mock_send:
            engine._send_notification([{'title': 'test'}], {'new_leads': 1})
            mock_send.assert_called_once()
        engine.db.close()

    @patch('core.engine.BazhongTenderSource')
    @patch('core.engine.PingchangGovSource')
    @patch('core.engine.TianfuTenderSource')
    @patch('core.engine.SichuanProcureSource')
    def test_run_all_uses_existing_category(self, MockSichuan, MockTianfu,
                                             MockPingchang, MockBazhong, engine_config):
        """When lead already has a category, don't re-classify."""
        mock_source = MagicMock()
        mock_source.name = '测试源'
        mock_source.fetch.return_value = [
            {'title': '公告', 'url': 'https://example.com/cat',
             'summary': '', 'source_name': '测试源', 'category': '已有分类'},
        ]
        MockBazhong.return_value = mock_source
        MockPingchang.return_value = MagicMock(name='p', fetch=MagicMock(return_value=[]))
        MockTianfu.return_value = MagicMock(name='t', fetch=MagicMock(return_value=[]))
        MockSichuan.return_value = MagicMock(name='s', fetch=MagicMock(return_value=[]))
        MockPingchang.return_value.name = '平昌'
        MockTianfu.return_value.name = '天府'
        MockSichuan.return_value.name = '四川'

        engine = _make_engine(engine_config)
        stats = engine.run_all(dry_run=False)
        assert stats['by_category'].get('已有分类') == 1
        engine.db.close()
