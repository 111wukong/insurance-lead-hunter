import logging
import time
from typing import List, Dict
from sources.base import BaseSource
from sources.bazhong_tender import BazhongTenderSource
from sources.pingchang_gov import PingchangGovSource
from sources.tianfu_tender import TianfuTenderSource
from sources.sichuan_procure import SichuanProcureSource
from core.dedup import Deduplicator
from core.classifier import Classifier
from storage.db import Database
from notify.feishu import FeishuNotifier, NotificationError

logger = logging.getLogger(__name__)


class Engine:
    """采集引擎，管理所有 source 的生命周期"""

    def __init__(self, config: dict):
        self.config = config
        self.db = Database(config)
        self.dedup = Deduplicator(self.db)
        self.classifier = Classifier(config)
        self.notifier = FeishuNotifier(config)
        self.sources = self._load_sources()

    def _load_sources(self) -> List[BaseSource]:
        return [
            BazhongTenderSource(self.config),
            PingchangGovSource(self.config),
            TianfuTenderSource(self.config),
            SichuanProcureSource(self.config),
        ]

    def run_all(self, dry_run: bool = False) -> Dict:
        """运行所有数据源采集。返回统计信息，包含错误详情。"""
        all_leads = []
        stats = {
            'total_fetched': 0,
            'new_leads': 0,
            'by_source': {},
            'by_category': {},
            'errors': [],
            'notification_error': None,
        }

        for source in self.sources:
            source_name = source.name
            logger.info(f"====== 开始采集: {source_name} ======")
            try:
                leads = source.fetch()
                stats['total_fetched'] += len(leads)
                stats['by_source'][source_name] = len(leads)
                logger.info(f"[{source_name}] 抓取到 {len(leads)} 条")

                new_count = 0
                for lead in leads:
                    if self.dedup.is_new(lead['url']):
                        category = lead.get('category', '') or self.classifier.classify(
                            lead.get('title', ''),
                            lead.get('summary', '')
                        )
                        lead['category'] = category
                        all_leads.append(lead)
                        new_count += 1

                        # 统计分类
                        if category not in stats['by_category']:
                            stats['by_category'][category] = 0
                        stats['by_category'][category] += 1

                stats['new_leads'] += new_count
                logger.info(f"[{source_name}] 新增 {new_count} 条")

                if not dry_run and new_count > 0:
                    leads_to_save = [l for l in leads if self.dedup.is_new(l['url'])]
                    insert_result = self.db.insert_leads(leads_to_save)
                    if insert_result['failed'] > 0:
                        error_msg = (
                            f"[{source_name}] 部分线索入库失败: "
                            f"{insert_result['failed']}/{insert_result['failed'] + insert_result['success']}"
                        )
                        stats['errors'].append(error_msg)
                        logger.warning(error_msg)

            except Exception as e:
                error_msg = f"[{source_name}] 采集异常: {e}"
                logger.error(error_msg, exc_info=True)
                stats['by_source'][source_name] = f"ERROR: {e}"
                stats['errors'].append(error_msg)

            time.sleep(self.config.get('request', {}).get('interval', 1))

        # 推送通知
        if not dry_run and stats['new_leads'] > 0:
            self._send_notification(all_leads, stats)

        return stats

    def _send_notification(self, leads: List[Dict], stats: Dict):
        """发送飞书通知，失败信息记录到 stats"""
        if not self.config.get('feishu', {}).get('enabled', False):
            return
        try:
            self.notifier.send_daily_report(leads, stats)
            logger.info("飞书通知已发送")
        except NotificationError as e:
            error_msg = f"飞书通知发送失败: {e}"
            logger.error(error_msg)
            stats['notification_error'] = str(e)
            stats['errors'].append(error_msg)
        except Exception as e:
            error_msg = f"飞书通知发送未知错误: {e}"
            logger.error(error_msg, exc_info=True)
            stats['notification_error'] = str(e)
            stats['errors'].append(error_msg)

    def generate_report(self) -> Dict:
        """用已有数据生成日报（不采集）。返回含错误详情的统计。"""
        leads = self.db.get_new_leads(limit=100)
        stats = {
            'total_fetched': len(leads),
            'new_leads': len(leads),
            'by_source': {},
            'by_category': {},
            'errors': [],
            'notification_error': None,
        }
        for lead in leads:
            src = lead.get('source_name', 'unknown')
            cat = lead.get('category', '其他保险')
            stats['by_source'][src] = stats['by_source'].get(src, 0) + 1
            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1

        if leads:
            self._send_notification(leads, stats)
        return stats

    def show_stats(self) -> Dict:
        """显示统计信息"""
        return self.db.get_stats()

    def init_db(self):
        """初始化数据库"""
        self.db.init_db()
        logger.info("数据库初始化完成")

    def clean_old_data(self):
        """清理过期数据"""
        retention = self.config.get('clean', {}).get('retention_days', 30)
        self.db.clean_old_data(retention)
        logger.info(f"已清理 {retention} 天前的数据")
