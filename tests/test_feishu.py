import os
import pytest
from unittest.mock import patch, MagicMock
from notify.feishu import FeishuNotifier, NotificationError


class TestFeishuNotifier:
    """Tests for notify.feishu.FeishuNotifier"""

    def test_disabled_when_no_webhook(self):
        config = {'feishu': {'enabled': True}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)
        assert notifier.enabled is False

    def test_enabled_with_env_webhook(self):
        config = {'feishu': {'enabled': True}}
        with patch.dict(os.environ, {'FEISHU_WEBHOOK': 'https://feishu.test/hook'}):
            notifier = FeishuNotifier(config)
        assert notifier.enabled is True
        assert notifier.webhook_url == 'https://feishu.test/hook'

    def test_enabled_with_config_webhook(self):
        config = {
            'feishu': {
                'enabled': True,
                'webhook_url': 'https://feishu.test/hook-config',
            }
        }
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)
        assert notifier.enabled is True
        assert notifier.webhook_url == 'https://feishu.test/hook-config'

    def test_env_webhook_takes_priority(self):
        config = {
            'feishu': {
                'enabled': True,
                'webhook_url': 'https://feishu.test/config',
            }
        }
        with patch.dict(os.environ, {'FEISHU_WEBHOOK': 'https://feishu.test/env'}):
            notifier = FeishuNotifier(config)
        assert notifier.webhook_url == 'https://feishu.test/env'

    def test_send_daily_report_disabled_skips(self):
        config = {'feishu': {'enabled': False}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)
        notifier.send_daily_report([], {})  # should not raise

    @patch('notify.feishu.requests.post')
    def test_send_daily_report_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'code': 0}
        mock_post.return_value = mock_resp

        config = {'feishu': {'enabled': True, 'webhook_url': 'https://feishu.test/hook'}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)

        leads = [
            {'title': '工程施工招标', 'category': '工程类', 'date': '2026-06-28',
             'source_name': '测试源', 'url': 'https://example.com/1'},
        ]
        stats = {
            'new_leads': 1,
            'by_source': {'测试源': 1},
        }
        notifier.send_daily_report(leads, stats)
        mock_post.assert_called_once()

    @patch('notify.feishu.requests.post')
    def test_send_daily_report_http_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = 'Internal Server Error'
        mock_post.return_value = mock_resp

        config = {'feishu': {'enabled': True, 'webhook_url': 'https://feishu.test/hook'}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)

        with pytest.raises(NotificationError, match='HTTP'):
            notifier.send_daily_report([], {})

    @patch('notify.feishu.requests.post',
           side_effect=__import__('requests').ConnectionError('network error'))
    def test_send_daily_report_exception(self, mock_post):
        config = {'feishu': {'enabled': True, 'webhook_url': 'https://feishu.test/hook'}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)

        with pytest.raises(NotificationError, match='网络错误'):
            notifier.send_daily_report([], {})

    def test_build_card_structure(self):
        config = {'feishu': {'enabled': True, 'webhook_url': 'https://feishu.test/hook'}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)

        leads = [
            {'title': '工程施工招标', 'category': '工程类', 'date': '2026-06-28',
             'source_name': '测试源', 'url': 'https://example.com/1'},
            {'title': '车辆采购公告', 'category': '车辆类', 'date': '',
             'source_name': '测试源', 'url': 'https://example.com/2'},
        ]
        stats = {'new_leads': 2, 'by_source': {'测试源': 2}}
        card = notifier._build_card(leads, stats)

        assert card['msg_type'] == 'interactive'
        assert 'card' in card
        assert 'header' in card['card']
        assert 'elements' in card['card']
        assert card['card']['header']['template'] == 'blue'

    def test_build_card_with_no_stats(self):
        config = {'feishu': {'enabled': True, 'webhook_url': 'https://feishu.test/hook'}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)

        leads = [
            {'title': '测试标题', 'category': '工程类', 'date': '',
             'source_name': 'src', 'url': 'https://example.com/1'},
        ]
        card = notifier._build_card(leads, None)
        assert card['msg_type'] == 'interactive'

    def test_build_card_empty_leads(self):
        config = {'feishu': {'enabled': True, 'webhook_url': 'https://feishu.test/hook'}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)

        card = notifier._build_card([], {})
        assert card['msg_type'] == 'interactive'

    @patch('notify.feishu.requests.post')
    def test_build_card_high_priority_recent_bid(self, mock_post):
        """A lead with '招标' in title and a recent date should be marked high-priority."""
        from datetime import datetime

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'code': 0}
        mock_post.return_value = mock_resp

        config = {'feishu': {'enabled': True, 'webhook_url': 'https://feishu.test/hook'}}
        with patch.dict(os.environ, {}, clear=True):
            notifier = FeishuNotifier(config)

        today = datetime.now().strftime('%Y-%m-%d')
        leads = [
            {'title': '工程招标公告', 'category': '工程类', 'date': today,
             'source_name': 'src', 'url': 'https://example.com/1'},
        ]
        card = notifier._build_card(leads, {'new_leads': 1, 'by_source': {'src': 1}})
        # Verify high-priority marker appears in the card elements
        card_text = str(card)
        assert '🔥' in card_text
