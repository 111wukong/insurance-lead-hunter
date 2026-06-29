#!/usr/bin/env python3
"""保险商机情报系统 - Insurance Lead Hunter v1.0
为四川巴中人保财险业务员打造的自动情报收集工具
"""

import argparse
import logging
import sys
import os

import yaml


def load_config(config_path: str = 'config.yaml') -> dict:
    """加载配置文件"""
    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def setup_logging(config: dict):
    """配置日志"""
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO'), logging.INFO)
    fmt = log_config.get('format', '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    logging.basicConfig(level=level, format=fmt, datefmt='%Y-%m-%d %H:%M:%S')


def cmd_run(args):
    """运行一次全量采集"""
    config = load_config(args.config)
    setup_logging(config)
    logger = logging.getLogger('main')

    # 延迟导入，避免未安装依赖时报错
    from core.engine import Engine

    engine = Engine(config)
    logger.info("开始全量采集...")

    if args.dry_run:
        logger.info("*** DRY RUN 模式（不写库不推送）***")

    stats = engine.run_all(dry_run=args.dry_run)

    print("\n" + "=" * 50)
    print("采集结果统计")
    print("=" * 50)
    print(f"总抓取数: {stats['total_fetched']}")
    print(f"新增线索: {stats['new_leads']}")
    print("\n各数据源:")
    for src, cnt in stats.get('by_source', {}).items():
        print(f"  - {src}: {cnt}")
    print("\n各分类:")
    for cat, cnt in stats.get('by_category', {}).items():
        print(f"  - {cat}: {cnt}")
    print("=" * 50)


def cmd_report(args):
    """生成日报"""
    config = load_config(args.config)
    setup_logging(config)
    logger = logging.getLogger('main')

    from core.engine import Engine

    engine = Engine(config)
    logger.info("生成日报...")

    if args.dry_run:
        logger.info("*** DRY RUN 模式（不推送）***")
        leads = engine.db.get_new_leads(limit=100)
        print(f"\n共 {len(leads)} 条待推送线索")
        for lead in leads:
            print(f"  [{lead.get('category', '')}] {lead.get('title', '')[:60]}")
    else:
        stats = engine.generate_report()
        print(f"\n日报已生成，共 {stats['new_leads']} 条线索")


def cmd_stats(args):
    """显示统计信息"""
    config = load_config(args.config)
    setup_logging(config)

    from core.engine import Engine

    engine = Engine(config)
    stats = engine.show_stats()

    print("\n" + "=" * 50)
    print("保险商机情报系统 - 统计信息")
    print("=" * 50)
    print(f"总线索数: {stats['total']}")
    print(f"  - 新线索: {stats['new']}")
    print(f"  - 跟进中: {stats['followed']}")
    print(f"  - 已关闭: {stats['closed']}")
    print(f"  - 近7天: {stats['recent_7d']}")
    print("\n按分类:")
    for cat, cnt in stats.get('by_category', {}).items():
        print(f"  {cat}: {cnt}")
    print("\n按数据源:")
    for src, cnt in stats.get('by_source', {}).items():
        print(f"  {src}: {cnt}")
    print("=" * 50)


def cmd_init(args):
    """初始化数据库"""
    config = load_config(args.config)
    setup_logging(config)
    logger = logging.getLogger('main')

    from core.engine import Engine

    engine = Engine(config)
    engine.init_db()
    print(f"\n数据库初始化完成！数据库文件: {config.get('database', {}).get('path', 'leads.db')}")


def cmd_clean(args):
    """清理旧数据"""
    config = load_config(args.config)
    setup_logging(config)
    logger = logging.getLogger('main')

    from core.engine import Engine

    engine = Engine(config)
    days = args.days or config.get('clean', {}).get('retention_days', 30)
    if not isinstance(days, int) or days < 1:
        print("错误: --days 必须为正整数")
        sys.exit(1)
    engine.db.clean_old_data(days)
    print(f"\n已清理 {days} 天前的数据")


def main():
    parser = argparse.ArgumentParser(
        description='保险商机情报系统 (Insurance Lead Hunter v1.0)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  python main.py init          # 初始化数据库
  python main.py run           # 运行全量采集
  python main.py run --dry-run # 干跑模式（不写库不推送）
  python main.py report        # 生成日报
  python main.py stats         # 查看统计
  python main.py clean         # 清理30天前数据
  python main.py clean --days 60  # 清理60天前数据
        '''
    )

    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )

    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # init
    subparsers.add_parser('init', help='初始化数据库')

    # run
    run_parser = subparsers.add_parser('run', help='运行一次全量采集')
    run_parser.add_argument('--dry-run', action='store_true', help='干跑模式')

    # report
    report_parser = subparsers.add_parser('report', help='生成日报')
    report_parser.add_argument('--dry-run', action='store_true', help='预览模式，不推送')

    # stats
    subparsers.add_parser('stats', help='显示统计信息')

    # clean
    clean_parser = subparsers.add_parser('clean', help='清理旧数据')
    clean_parser.add_argument('--days', type=int, help='保留天数 (默认从配置读取)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    commands = {
        'init': cmd_init,
        'run': cmd_run,
        'report': cmd_report,
        'stats': cmd_stats,
        'clean': cmd_clean,
    }

    commands[args.command](args)


if __name__ == '__main__':
    main()
