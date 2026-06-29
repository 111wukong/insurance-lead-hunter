"""
线索分析器 - 政府/企业分类 + 保险关联度 + 时效性检测
"""

import os
import re
import sys
from datetime import datetime, timedelta
from typing import Tuple, Optional

# Ensure project root is on path for shared imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.utils import has_keyword_match

# 政府机构关键词
GOV_KEYWORDS = [
    '局', '政府', '中心', '委员会', '办公室', '院', '队', '站', '所',
    '街道', '镇', '乡', '村', '社区',
    '财政', '公共资源', '政务', '住建', '水利', '教育', '卫生', '民政',
    '公安', '交通', '环境', '规划', '城管', '人社', '发改', '经信',
    '农业', '林业', '审计', '监察', '应急', '消防', '退役军人',
    '人民武装', '纪检', '组织', '宣传', '党校',
]

# 企业关键词
ENTERPRISE_KEYWORDS = [
    '公司', '集团', '有限', '实业', '厂', '酒店', '物业', '置业',
    '投资', '贸易', '商行', '合作社', '合伙', '个体',
]

# 保险相关度关键词（权重降序）
INSURANCE_KEYWORDS_HIGH = [
    '保险', '投保', '承保', '共保', '再保险', '保费',
    '意外伤害', '补充医疗', '大病保险', '责任险',
    '财产险', '工程险', '学平险', '车险', '健康险',
]

INSURANCE_KEYWORDS_MEDIUM = [
    '工程', '施工', '建设', '建筑', '道路', '桥梁', '水利', '改造',
    '采购', '招标', '监理', '安全', '检测', '监测', '评估',
    '车辆', '运输', '物流', '设备', '安装',
]

INSURANCE_KEYWORDS_LOW = [
    '维护', '维修', '保养', '租赁', '劳务', '咨询', '审计',
    '设计', '规划', '勘察', '物业', '保洁', '保安',
]

def classify_project_type(title: str, summary: str = '') -> str:
    """分类：政府项目 / 企业项目 / 其他"""
    text = title + summary

    gov_score = sum(1 for kw in GOV_KEYWORDS if kw in text)
    ent_score = sum(1 for kw in ENTERPRISE_KEYWORDS if kw in text)

    if gov_score > ent_score:
        return '政府项目'
    elif ent_score > gov_score:
        return '企业项目'
    elif gov_score > 0:
        return '政府项目'
    elif ent_score > 0:
        return '企业项目'
    return '其他'

def classify_insurance_relevance(title: str, summary: str = '') -> str:
    """保险关联度：高 / 中 / 低"""
    text = title + summary

    if has_keyword_match(text, INSURANCE_KEYWORDS_HIGH):
        return '高'
    if has_keyword_match(text, INSURANCE_KEYWORDS_MEDIUM):
        return '中'
    if has_keyword_match(text, INSURANCE_KEYWORDS_LOW):
        return '低'
    return '低'

def is_fresh(date_str: str, max_days: int = 30) -> Tuple[bool, Optional[datetime]]:
    """检查是否在 max_days 天内"""
    if not date_str:
        return True, None
    
    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']:
        try:
            d = datetime.strptime(date_str.strip(), fmt)
            return (datetime.now() - d).days <= max_days, d
        except:
            pass
    
    # Try regex extraction
    m = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', date_str)
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return (datetime.now() - d).days <= max_days, d
        except:
            pass
    
    return True, None

def analyze_lead(title: str, summary: str = '', date: str = '', 
                 deadline: str = '', amount: str = '') -> dict:
    """综合分析一条线索"""
    fresh, parsed_date = is_fresh(date)
    days_left = None
    if parsed_date:
        days_left = 30 - (datetime.now() - parsed_date).days
    
    deadline_fresh = True
    deadline_days = None
    if deadline:
        try:
            dl = datetime.strptime(deadline.strip(), '%Y-%m-%d')
            deadline_days = (dl - datetime.now()).days
            deadline_fresh = deadline_days >= 0
        except:
            pass
    
    return {
        'project_type': classify_project_type(title, summary),
        'insurance_relevance': classify_insurance_relevance(title, summary),
        'is_fresh': fresh and deadline_fresh,
        'days_since_publish': days_left,
        'days_to_deadline': deadline_days,
    }

# Opportunity mapping: keywords -> insurance reason
_OPPORTUNITY_RULES = [
    (['工程', '施工', '建设', '建筑', '道路', '桥梁'], '工程一切险/第三方责任险'),
    (['车辆', '运输', '客车', '货车', '物流'], '车辆保险'),
    (['采购', '设备', '物资', '材料', '货物'], '货物运输险'),
    (['安全', '检测', '监测', '监理', '评估'], '安全生产责任险/职业责任险'),
    (['物业', '保洁', '保安', '管理服务'], '公众责任险/雇主责任险'),
    (['医疗', '健康', '医院', '卫生'], '医疗责任险/健康险'),
    (['农业', '种植', '养殖', '粮食', '森林'], '农业保险'),
    (['保险', '投保', '承保', '共保'], '直接保险采购需求'),
    (['老旧', '改造', '修缮', '装修'], '建工一切险'),
]


def insurance_opportunity_reason(title: str, summary: str = '') -> str:
    """生成保险商机理由"""
    text = title + summary
    reasons = [
        reason for keywords, reason in _OPPORTUNITY_RULES
        if has_keyword_match(text, keywords)
    ]
    return '、'.join(reasons) if reasons else '潜在保险需求'
