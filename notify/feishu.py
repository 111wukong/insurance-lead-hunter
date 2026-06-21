import os
import json
import logging
import requests
from typing import List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书 Webhook 通知"""

    def __init__(self, config: dict):
        self.config = config
        webhook = os.environ.get('FEISHU_WEBHOOK', '')
        if not webhook:
            webhook = config.get('feishu', {}).get('webhook_url', '')
        self.webhook_url = webhook
        self.enabled = config.get('feishu', {}).get('enabled', False) and bool(self.webhook_url)

    def send_daily_report(self, leads: List[Dict], stats: Dict = None):
        """发送日报"""
        if not self.enabled:
            logger.info("飞书通知未启用或无 webhook URL")
            return

        card = self._build_card(leads, stats)
        try:
            resp = requests.post(
                self.webhook_url,
                json=card,
                headers={'Content-Type': 'application/json'},
                timeout=10,
            )
            if resp.status_code == 200:
                resp_data = resp.json()
                if resp_data.get('code') == 0:
                    logger.info("飞书消息发送成功")
                else:
                    logger.warning(f"飞书消息发送失败: {resp_data}")
            else:
                logger.warning(f"飞书 HTTP 错误: {resp.status_code}")
        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")

    def _build_card(self, leads: List[Dict], stats: Dict = None) -> dict:
        """构建飞书卡片消息"""
        today_str = datetime.now().strftime('%Y年%m月%d日')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        # 按分类分组
        groups = {}
        for lead in leads:
            cat = lead.get('category', '其他保险')
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(lead)

        # 标题
        total_new = stats.get('new_leads', len(leads)) if stats else len(leads)
        title_text = f"保险商机日报 - {today_str}"
        subtitle = f"今日发现 {total_new} 条新线索"

        elements = [
            {
                "tag": "markdown",
                "content": f"**{title_text}**\n<font color='grey'>{subtitle}</font>"
            },
            {"tag": "hr"},
        ]

        # 统计概览
        if stats:
            stats_text = "**统计概览**\n"
            for src, cnt in stats.get('by_source', {}).items():
                cnt_str = str(cnt) if isinstance(cnt, int) else cnt
                stats_text += f"- {src}: {cnt_str}\n"
            elements.append({
                "tag": "markdown",
                "content": stats_text,
            })
            elements.append({"tag": "hr"})

        # 按分类展示线索
        priority_order = ['工程类', '企业财产类', '车辆类', '责任险类',
                         '农险类', '健康险类', '政府项目类', '其他保险']

        for cat in priority_order:
            if cat not in groups:
                continue
            cat_leads = groups[cat][:10]  # 每类最多10条

            cat_text = f"**{cat}** ({len(cat_leads)}条)\n"
            for i, lead in enumerate(cat_leads):
                title = lead.get('title', '无标题')[:60]
                date = lead.get('date', lead.get('publish_date', ''))
                source = lead.get('source_name', '')

                # 标记高优先级
                is_high_priority = False
                if '招标' in title and date:
                    # 判断是否在3天内
                    try:
                        lead_date = date[:10]
                        if lead_date >= yesterday:
                            is_high_priority = True
                    except Exception:
                        pass

                if is_high_priority:
                    cat_text += f"<font color='red'>🔥 [{source}] {title}</font>\n"
                else:
                    cat_text += f"[{source}] {title}\n"

                if date:
                    cat_text += f"<font color='grey'>📅 {date}</font>\n"

            elements.append({
                "tag": "markdown",
                "content": cat_text,
            })

        # 提示
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": "<font color='grey'>💡 使用 `python main.py run` 采集最新数据</font>",
        })

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"保险商机情报 {today_str}"
                    },
                    "template": "blue"
                },
                "elements": elements,
            }
        }

        return card
