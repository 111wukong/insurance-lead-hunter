import pytest
from datetime import datetime, timedelta
from webapp.analyzer import (
    classify_project_type,
    classify_insurance_relevance,
    is_fresh,
    analyze_lead,
    insurance_opportunity_reason,
)


class TestClassifyProjectType:
    def test_government_keywords(self):
        assert classify_project_type('市政府采购公告') == '政府项目'

    def test_enterprise_keywords(self):
        assert classify_project_type('某某公司设备采购') == '企业项目'

    def test_government_wins_on_tie(self):
        """When gov and enterprise scores are tied but both > 0, government wins."""
        result = classify_project_type('局公司')
        assert result == '政府项目'

    def test_no_keywords_returns_other(self):
        assert classify_project_type('天气预报') == '其他'

    def test_uses_summary(self):
        assert classify_project_type('公告', '住建局发布') == '政府项目'

    def test_enterprise_higher_score(self):
        result = classify_project_type('某有限公司实业集团采购')
        assert result == '企业项目'


class TestClassifyInsuranceRelevance:
    def test_high_relevance(self):
        assert classify_insurance_relevance('保险采购公告') == '高'

    def test_high_relevance_specific(self):
        assert classify_insurance_relevance('财产险投标') == '高'

    def test_medium_relevance(self):
        assert classify_insurance_relevance('道路建设工程') == '中'

    def test_low_relevance(self):
        assert classify_insurance_relevance('物业维护项目') == '低'

    def test_no_match_returns_low(self):
        assert classify_insurance_relevance('天气预报') == '低'

    def test_uses_summary(self):
        assert classify_insurance_relevance('公告', '保险投标须知') == '高'


class TestIsFresh:
    def test_empty_date_returns_true(self):
        fresh, parsed = is_fresh('')
        assert fresh is True
        assert parsed is None

    def test_recent_date_is_fresh(self):
        recent = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        fresh, parsed = is_fresh(recent)
        assert fresh is True
        assert parsed is not None

    def test_old_date_not_fresh(self):
        old = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        fresh, parsed = is_fresh(old, max_days=30)
        assert fresh is False

    def test_slash_format(self):
        recent = (datetime.now() - timedelta(days=3)).strftime('%Y/%m/%d')
        fresh, parsed = is_fresh(recent)
        assert fresh is True

    def test_dot_format(self):
        recent = (datetime.now() - timedelta(days=3)).strftime('%Y.%m.%d')
        fresh, parsed = is_fresh(recent)
        assert fresh is True

    def test_regex_extraction(self):
        recent = (datetime.now() - timedelta(days=2)).strftime('发布日期：%Y-%m-%d')
        fresh, parsed = is_fresh(recent)
        assert fresh is True

    def test_unparseable_returns_true(self):
        fresh, parsed = is_fresh('not a date')
        assert fresh is True
        assert parsed is None

    def test_custom_max_days(self):
        date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        fresh, _ = is_fresh(date, max_days=5)
        assert fresh is False

        fresh2, _ = is_fresh(date, max_days=15)
        assert fresh2 is True


class TestAnalyzeLead:
    def test_basic_analysis(self):
        result = analyze_lead('保险招标公告', summary='施工', date='', deadline='')
        assert result['insurance_relevance'] == '高'
        assert 'project_type' in result
        assert 'is_fresh' in result

    def test_with_deadline_in_future(self):
        future = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
        result = analyze_lead('项目公告', deadline=future)
        assert result['is_fresh'] is True
        assert result['days_to_deadline'] >= 9

    def test_with_deadline_in_past(self):
        past = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        result = analyze_lead('项目公告', deadline=past)
        assert result['is_fresh'] is False
        assert result['days_to_deadline'] < 0

    def test_unparseable_deadline(self):
        result = analyze_lead('公告', deadline='尽快')
        assert result['days_to_deadline'] is None


class TestInsuranceOpportunityReason:
    def test_engineering(self):
        reason = insurance_opportunity_reason('道路工程施工')
        assert '工程一切险' in reason

    def test_vehicle(self):
        reason = insurance_opportunity_reason('车辆运输项目')
        assert '车辆保险' in reason

    def test_procurement(self):
        reason = insurance_opportunity_reason('设备采购项目')
        assert '货物运输险' in reason

    def test_safety(self):
        reason = insurance_opportunity_reason('安全检测项目')
        assert '安全生产责任险' in reason or '职业责任险' in reason

    def test_property(self):
        reason = insurance_opportunity_reason('物业保洁服务')
        assert '公众责任险' in reason or '雇主责任险' in reason

    def test_medical(self):
        reason = insurance_opportunity_reason('医疗健康服务')
        assert '医疗责任险' in reason or '健康险' in reason

    def test_agriculture(self):
        reason = insurance_opportunity_reason('农业种植项目')
        assert '农业保险' in reason

    def test_direct_insurance(self):
        reason = insurance_opportunity_reason('保险采购投保')
        assert '直接保险采购需求' in reason

    def test_renovation(self):
        reason = insurance_opportunity_reason('老旧小区改造')
        assert '建工一切险' in reason

    def test_no_match(self):
        reason = insurance_opportunity_reason('天气预报')
        assert reason == '潜在保险需求'

    def test_multiple_reasons(self):
        reason = insurance_opportunity_reason('车辆运输工程施工')
        assert '、' in reason  # multiple reasons joined
