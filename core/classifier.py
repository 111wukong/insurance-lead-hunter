import logging

logger = logging.getLogger(__name__)


class Classifier:
    """关键词分类器"""

    def __init__(self, config: dict):
        self.categories = config.get('categories', {})
        if not self.categories:
            # 默认分类
            self.categories = {
                '工程类': {'keywords': ['工程', '施工', '建筑', '工地', '建设']},
                '企业财产类': {'keywords': ['企业财产', '财产险', '财产保险', '厂房']},
                '车辆类': {'keywords': ['车辆', '车险', '车队', '交通']},
                '责任险类': {'keywords': ['责任险', '雇主', '公众责任', '食品安全']},
                '政府项目类': {'keywords': ['政府采购', '政府购买', '财政']},
                '其他保险': {'keywords': ['保险']},
            }

    def classify(self, title: str, summary: str = '') -> str:
        """对一条线索进行分类"""
        text = title + ' ' + summary

        # 按优先级排序：非"其他保险"类优先匹配
        sorted_cats = sorted(
            self.categories.items(),
            key=lambda x: 0 if x[0] == '其他保险' else 1,
            reverse=True
        )

        for cat_name, cat_config in sorted_cats:
            keywords = cat_config.get('keywords', []) if isinstance(cat_config, dict) else cat_config
            if any(kw in text for kw in keywords):
                return cat_name

        return '其他保险'
