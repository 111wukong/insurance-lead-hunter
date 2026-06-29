import pytest
from core.classifier import Classifier


class TestClassifier:
    """Tests for core.classifier.Classifier"""

    def test_classify_engineering(self, sample_config):
        c = Classifier(sample_config)
        assert c.classify('某工程施工招标公告') == '工程类'

    def test_classify_vehicle(self, sample_config):
        c = Classifier(sample_config)
        assert c.classify('市政府车辆采购公告') == '车辆类'

    def test_classify_liability(self, sample_config):
        c = Classifier(sample_config)
        assert c.classify('雇主责任险采购公告') == '责任险类'

    def test_classify_government(self, sample_config):
        c = Classifier(sample_config)
        assert c.classify('政府采购信息公告') == '政府项目类'

    def test_classify_other_insurance(self, sample_config):
        c = Classifier(sample_config)
        assert c.classify('保险服务采购公告') == '其他保险'

    def test_classify_no_match_returns_other(self, sample_config):
        c = Classifier(sample_config)
        assert c.classify('天气预报今日晴') == '其他保险'

    def test_classify_uses_summary(self, sample_config):
        c = Classifier(sample_config)
        assert c.classify('公告', '施工单位信息') == '工程类'

    def test_classify_priority_non_other_first(self, sample_config):
        """When text matches both a specific category and '其他保险', the specific one wins."""
        c = Classifier(sample_config)
        result = c.classify('工程保险招标')
        assert result == '工程类'

    def test_default_categories_when_empty(self):
        c = Classifier({})
        assert len(c.categories) > 0
        assert c.classify('工程项目') == '工程类'

    def test_categories_from_list_format(self):
        """categories values can be plain lists instead of dicts."""
        config = {
            'categories': {
                '测试类': ['测试', '检查'],
            }
        }
        c = Classifier(config)
        assert c.classify('测试项目') == '测试类'
