# 保险商机情报系统 (Insurance Lead Hunter v1.0)

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

为四川巴中人保财险业务员打造的自动情报收集工具，监控巴中市（重点平昌县）的保险商机信号。

## 功能特性

- **多源采集**: 自动抓取巴中公共资源交易平台、平昌县人民政府网、天府阳光采购平台、四川政府采购网的招标/采购公告
- **智能筛选**: 基于保险关键词自动筛选相关商机（工程险、财产险、车辆险、责任险、农险、健康险等）
- **自动分类**: 按业务类型自动分类线索，方便快速定位
- **去重存储**: 基于URL MD5哈希去重，SQLite本地存储
- **飞书推送**: 支持飞书Webhook推送日报，卡片格式按分类展示，高优先级线索标红
- **命令行工具**: 完善的CLI，支持采集、日报、统计、清理等操作

## 项目结构

```
insurance-lead-hunter/
├── main.py                 # CLI入口
├── config.yaml             # 配置文件
├── requirements.txt        # 依赖
├── README.md
├── sources/                # 数据源模块
│   ├── __init__.py
│   ├── base.py             # 抽象基类
│   ├── bazhong_tender.py   # 巴中公共资源交易平台
│   ├── pingchang_gov.py    # 平昌县人民政府网
│   ├── tianfu_tender.py    # 天府阳光采购平台
│   └── sichuan_procure.py  # 四川政府采购网
├── core/                   # 核心模块
│   ├── __init__.py
│   ├── engine.py           # 采集引擎
│   ├── dedup.py            # 去重器
│   └── classifier.py       # 分类器
├── storage/                # 存储模块
│   ├── __init__.py
│   └── db.py               # SQLite数据库
└── notify/                 # 通知模块
    ├── __init__.py
    └── feishu.py           # 飞书推送
```

## 安装方法

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd insurance-lead-hunter
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python main.py init
```

### 4. 配置飞书推送（可选）

设置环境变量：
```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-url"
```

或在 `config.yaml` 中配置：
```yaml
feishu:
  enabled: true
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-url"
```

## 配置说明

编辑 `config.yaml` 可自定义：

- **categories**: 关键词分类规则，可按需增删改
- **request**: 请求配置（User-Agent、超时、重试次数、请求间隔）
- **feishu**: 飞书通知配置
- **clean**: 数据保留天数
- **logging**: 日志级别和格式

## 使用示例

```bash
# 初始化数据库
python main.py init

# 运行一次全量采集
python main.py run

# 干跑模式（不写库、不推送，仅查看结果）
python main.py run --dry-run

# 生成日报并推送飞书
python main.py report

# 预览日报（不推送）
python main.py report --dry-run

# 查看统计信息
python main.py stats

# 清理30天前的旧数据
python main.py clean

# 清理指定天数前的数据
python main.py clean --days 60
```

### 设置定时任务（crontab）

```bash
# 每天早上9点采集并推送日报
0 9 * * * cd /path/to/insurance-lead-hunter && python main.py run && python main.py report
```

## 分类说明

| 分类 | 关键词示例 | 优先级 |
|------|-----------|--------|
| 工程类 | 工程、施工、建筑、道路 | 高 |
| 企业财产类 | 企业财产、财产险、厂房 | 高 |
| 车辆类 | 车辆、车险、车队 | 高 |
| 责任险类 | 责任险、雇主、公众责任 | 高 |
| 农险类 | 农业、种植、养殖、生猪 | 高 |
| 健康险类 | 医疗、健康、补充医疗 | 高 |
| 政府项目类 | 政府采购、政府购买 | 中 |
| 其他保险 | 保险、保费、投保 | 低 |

## License

MIT License
