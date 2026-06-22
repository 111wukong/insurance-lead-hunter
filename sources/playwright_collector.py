#!/usr/bin/env python3
"""
保险商机采集 - Playwright 浏览器自动化采集器
采集: 巴中公共资源交易平台、四川省公共资源交易信息网、天府阳光采购平台
"""

import asyncio, hashlib, sqlite3, re, os, sys, json, random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PARENT, 'leads.db')

CATEGORIES = [
    ('工程类', ['工程', '施工', '建筑', '建设', '道路', '桥梁', '水利', '改造', '监理', '装修']),
    ('车辆类', ['车辆', '交通', '运输', '客车', '货车', '公交车', '车队']),
    ('责任险类', ['责任险', '安全生产', '食品安全', '雇主责任', '公众责任']),
    ('政府项目类', ['采购', '招标', '中标', '成交', '磋商', '谈判', '遴选']),
    ('农险类', ['农业', '种植', '养殖', '粮食', '水稻', '油菜', '森林', '农田']),
    ('健康险类', ['医疗', '健康保险', '补充医疗', '大病保险', '意外伤害', '学平险']),
    ('企业财产类', ['财产保险', '财产险', '厂房', '设备', '固定资产']),
]

def classify(text):
    for cat, kws in CATEGORIES:
        if any(kw in text for kw in kws):
            return cat
    return '其他保险'

def save_leads(leads):
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    new = 0
    for l in leads:
        url_hash = hashlib.md5(l['url'].encode()).hexdigest()
        if db.execute("SELECT id FROM leads WHERE url_hash=?", (url_hash,)).fetchone():
            continue
        cat = classify(l['title'] + l.get('summary', ''))
        db.execute("""INSERT INTO leads 
            (title,url,url_hash,summary,source_name,category,publish_date,amount,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,'new',datetime('now','localtime'))""",
            (l['title'], l['url'], url_hash, l.get('summary',''),
             l.get('source_name',''), cat, l.get('date',''), l.get('amount','')))
        new += 1
    db.commit(); db.close()
    return new

async def collect_all():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel='chrome',
            args=['--no-sandbox','--disable-blink-features=AutomationControlled'])
        ctx = await browser.new_context(
            viewport={'width':1920,'height':1080}, locale='zh-CN',
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        await ctx.add_init_script('''() => {
            Object.defineProperty(navigator,'webdriver',{get:()=>false});
            window.chrome={runtime:{}};
        }''')
        page = await ctx.new_page()
        all_leads = []
        
        # ---- 巴中公共资源交易平台 ----
        print("📡 巴中公共资源交易平台...")
        try:
            await page.goto('https://www.bzsggzy.cn/', wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(8)
            items = await page.evaluate('''() => {
                const body = document.body.innerText;
                const lines = body.split('\\n');
                const results = [];
                let currentTitle = '';
                for (const line of lines) {
                    const t = line.trim();
                    const dateMatch = t.match(/(\\d{4}[-/.]\\d{1,2}[-/.]\\d{1,2})/);
                    if (dateMatch && currentTitle) {
                        results.push({title: currentTitle.trim(), date: dateMatch[1]});
                        currentTitle = '';
                    } else if (t.length > 10 && !/^(首页|交易信息|工程建设|政府采购)/.test(t)) {
                        currentTitle += (currentTitle ? ' ' : '') + t;
                    }
                }
                return results;
            }''')
            for item in items:
                if any(kw in item['title'] for kw in ['招标','采购','公告','通知','保险','工程','项目']):
                    url_hash = hashlib.md5(item['title'].encode()).hexdigest()[:8]
                    all_leads.append({
                        'title': item['title'], 'date': item['date'],
                        'url': f"https://www.bzsggzy.cn/#/notice/{url_hash}",
                        'source_name': '巴中公共资源交易平台', 'summary': '',
                    })
        except Exception as e:
            print(f"  ⚠️ {e}")
        print(f"  找到 {len(all_leads)} 条")
        
        # ---- 四川省公共资源交易信息网 ----
        print("📡 四川省公共资源交易信息网...")
        try:
            await page.goto('http://ggzyjy.sc.gov.cn/jyxx/transactionInfo.html',
                          wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(5)
            items = await page.evaluate('''() => {
                const results = [];
                document.querySelectorAll('a').forEach(a => {
                    const t = a.textContent.trim();
                    const h = a.href;
                    if (t.length > 15 && h && !h.startsWith('javascript:') && h !== '#') {
                        let date = '';
                        let p = a.closest('li, tr, div');
                        if (p) {
                            const m = p.textContent.match(/(\\d{4}[-/.]\\d{1,2}[-/.]\\d{1,2})/);
                            if (m) date = m[1];
                        }
                        results.push({title: t, url: h, date: date});
                    }
                });
                return results.filter(r => /招标|采购|中标|施工|工程|保险|公告/.test(r.title));
            }''')
            for item in items:
                all_leads.append({
                    'title': item['title'], 'url': item['url'],
                    'date': item.get('date',''), 'source_name': '四川省公共资源交易信息网',
                    'summary': '',
                })
        except Exception as e:
            print(f"  ⚠️ {e}")
        print(f"  累计 {len(all_leads)} 条")
        
        await browser.close()
    
    new = save_leads(all_leads)
    print(f"\n✅ 入库 {new} 条新线索（共抓取 {len(all_leads)} 条）")
    
    db = sqlite3.connect(DB_PATH)
    total = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    db.close()
    print(f"📊 数据库总计: {total} 条")
    return new

if __name__ == '__main__':
    asyncio.run(collect_all())
