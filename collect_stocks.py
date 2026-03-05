#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日股票行情收集脚本
收集美股和 A 股行情数据，生成 Markdown 报告
"""

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# 配置
WORKSPACE = Path(__file__).parent
DATA_DIR = WORKSPACE / "data"
REPORTS_DIR = WORKSPACE / "reports"
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# Tavily API 配置
TAVILY_API_KEY = "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"


def run_shell(cmd: str) -> str:
    """执行 shell 命令"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"


def get_tavily_news(query: str, max_results: int = 5) -> list:
    """从 Tavily 获取相关新闻"""
    try:
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TAVILY_API_KEY}"
        }
        data = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
        
        news_list = []
        for item in result.get("results", [])[:max_results]:
            news_list.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", "")[:200] + "..." if len(item.get("content", "")) > 200 else item.get("content", "")
            })
        
        return news_list
    except Exception as e:
        return [{"title": f"获取失败：{str(e)}", "url": "", "content": ""}]


def get_us_stocks() -> dict:
    """获取美股数据（Stooq API）"""
    stocks = {}
    
    # 三大指数
    indices = {
        "^DJI": "道琼斯",
        "^SPX": "标普 500",
        "^IXIC": "纳斯达克"
    }
    
    for symbol, name in indices.items():
        # Get two lines (header + data), take the second line
        data = run_shell(f'curl -sL "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h=x&t=x" 2>/dev/null | tail -1')
        if data and "N/D" not in data and data.strip():
            parts = data.split(",")
            # Format: Symbol,Date,Time,Open,High,Low,Close,Volume
            if len(parts) >= 7:
                stocks[name] = {
                    "symbol": symbol,
                    "date": parts[1],
                    "close": parts[6],
                    "open": parts[3],
                    "high": parts[4],
                    "low": parts[5],
                    "volume": parts[7] if len(parts) > 7 else "-"
                }
    
    # 七姐妹个股
    tech_stocks = {
        "AAPL.US": "苹果",
        "MSFT.US": "微软",
        "GOOGL.US": "谷歌",
        "AMZN.US": "亚马逊",
        "NVDA.US": "英伟达",
        "META.US": "Meta",
        "TSLA.US": "特斯拉"
    }
    
    for symbol, name in tech_stocks.items():
        # Get two lines (header + data), take the second line
        data = run_shell(f'curl -sL "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h=x&t=x" 2>/dev/null | tail -1')
        if data and "N/D" not in data and data.strip():
            parts = data.split(",")
            # Format: Symbol,Date,Time,Open,High,Low,Close,Volume
            if len(parts) >= 7:
                stocks[name] = {
                    "symbol": symbol.replace(".US", ""),
                    "date": parts[1],
                    "close": parts[6],
                    "open": parts[3],
                    "high": parts[4],
                    "low": parts[5],
                    "volume": parts[7] if len(parts) > 7 else "-"
                }
    
    return stocks


def get_cn_stocks() -> dict:
    """获取 A 股数据（腾讯财经 API）"""
    stocks = {}
    
    # 三大指数 - 腾讯代码：sh=沪市，sz=深市
    indices = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指"
    }
    
    for code, name in indices.items():
        try:
            result = subprocess.run(
                f'curl -sL --connect-timeout 10 "https://qt.gtimg.cn/q={code}"',
                shell=True, capture_output=True, timeout=15
            )
            # 腾讯 API 返回 GBK 编码
            data = result.stdout.decode('gbk', errors='ignore').strip()
            if data and '=' in data and '~' in data:
                content = data.split('"')[1]
                parts = content.split('~')
                if len(parts) >= 45:
                    # 腾讯 API 字段：3=当前，4=昨收，5=最高，6=成交量
                    # 31=涨跌额，32=涨跌幅%，34=今开，42=最低
                    stocks[name] = {
                        "symbol": parts[2],
                        "close": parts[3] if parts[3] else "-",
                        "open": parts[34] if len(parts) > 34 and parts[34] else "-",
                        "high": parts[5] if parts[5] else "-",
                        "low": parts[42] if len(parts) > 42 and parts[42] else "-",
                        "change": f"{parts[32]}%" if len(parts) > 32 and parts[32] else "-"
                    }
        except Exception as e:
            stocks[name] = {"error": str(e)}
    
    return stocks


def get_market_news() -> dict:
    """从 Tavily 获取市场新闻"""
    news = {
        "us_news": [],
        "cn_news": [],
        "global_news": []
    }
    
    # 美股新闻
    us_query = "美股市场新闻 美联储 科技股 2026 年 2 月"
    news["us_news"] = get_tavily_news(us_query, max_results=3)
    
    # A 股新闻
    cn_query = "A 股市场新闻 中国证监会 沪深股市 2026 年 2 月"
    news["cn_news"] = get_tavily_news(cn_query, max_results=3)
    
    # 全球财经新闻
    global_query = "全球财经新闻 人工智能 AI 芯片 加密货币 2026 年"
    news["global_news"] = get_tavily_news(global_query, max_results=3)
    
    return news


def calc_change(current: str, prev: str) -> str:
    """计算涨跌幅"""
    try:
        curr = float(current)
        prev = float(prev)
        if prev == 0:
            return "0%"
        change = ((curr - prev) / prev) * 100
        return f"{change:+.2f}%"
    except:
        return "-"


def generate_report(date: str, us_data: dict, cn_data: dict, news_data: dict = None) -> str:
    """生成 Markdown 报告"""
    report = f"""# 📈 每日股票行情 | {date}

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (Asia/Shanghai)

---

## 🇺🇸 美股市场

### 三大指数

| 指数 | 代码 | 收盘价 | 开盘 | 最高 | 最低 | 成交量 |
|------|------|--------|------|------|------|--------|
"""
    
    us_indices = ["道琼斯", "标普 500", "纳斯达克"]
    for name in us_indices:
        if name in us_data:
            d = us_data[name]
            report += f"| {name} | {d['symbol']} | {d['close']} | {d['open']} | {d['high']} | {d['low']} | {d['volume']} |\n"
    
    report += """
### 科技七姐妹

| 公司 | 代码 | 收盘价 | 开盘 | 最高 | 最低 |
|------|------|--------|------|------|------|
"""
    
    tech = ["苹果", "微软", "谷歌", "亚马逊", "英伟达", "Meta", "特斯拉"]
    for name in tech:
        if name in us_data:
            d = us_data[name]
            report += f"| {name} | {d['symbol']} | ${d['close']} | ${d['open']} | ${d['high']} | ${d['low']} |\n"
    
    report += f"""
---

## 🇨🇳 A 股市场

### 三大指数

| 指数 | 代码 | 收盘价 | 开盘 | 最高 | 最低 | 涨跌幅 |
|------|------|--------|------|------|------|--------|
"""
    
    cn_indices = ["上证指数", "深证成指", "创业板指"]
    for name in cn_indices:
        if name in cn_data:
            d = cn_data[name]
            report += f"| {name} | {d.get('symbol', '-')} | {d.get('close', '-')} | {d.get('open', '-')} | {d.get('high', '-')} | {d.get('low', '-')} | {d.get('change', '-')} |\n"
    
    report += f"""
---

## 📰 市场新闻 (Tavily)

"""
    
    if news_data:
        # 美股新闻
        if news_data.get("us_news"):
            report += "### 🇺🇸 美股新闻\n\n"
            for news in news_data["us_news"]:
                if news.get("title") and "获取失败" not in news.get("title", ""):
                    report += f"- **{news['title']}**\n"
                    if news.get("url"):
                        report += f"  🔗 [{news['url']}]({news['url']})\n"
                    if news.get("content"):
                        report += f"  {news['content']}\n"
                    report += "\n"
        
        # A 股新闻
        if news_data.get("cn_news"):
            report += "### 🇨🇳 A 股新闻\n\n"
            for news in news_data["cn_news"]:
                if news.get("title") and "获取失败" not in news.get("title", ""):
                    report += f"- **{news['title']}**\n"
                    if news.get("url"):
                        report += f"  🔗 [{news['url']}]({news['url']})\n"
                    if news.get("content"):
                        report += f"  {news['content']}\n"
                    report += "\n"
        
        # 全球财经新闻
        if news_data.get("global_news"):
            report += "### 🌍 全球财经\n\n"
            for news in news_data["global_news"]:
                if news.get("title") and "获取失败" not in news.get("title", ""):
                    report += f"- **{news['title']}**\n"
                    if news.get("url"):
                        report += f"  🔗 [{news['url']}]({news['url']})\n"
                    if news.get("content"):
                        report += f"  {news['content']}\n"
                    report += "\n"
    else:
        report += "*今日新闻数据暂缺*\n\n"
    
    report += f"""---

## 📊 数据源

| 类型 | 数据源 | 说明 |
|------|--------|------|
| 美股行情 | Stooq | 公开免费 API，延迟 15-20 分钟 |
| A 股行情 | 新浪财经 | 公开免费 API，实时 |
| 市场新闻 | Tavily | AI 搜索引擎，实时资讯 |

---

*🤖 自动生成 | 数据仅供参考*
"""
    
    return report


def save_data(date: str, us_data: dict, cn_data: dict, news_data: dict = None):
    """保存原始数据到 JSON"""
    data = {
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "us_stocks": us_data,
        "cn_stocks": cn_data,
        "news": news_data
    }
    
    with open(DATA_DIR / f"{date}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    """主函数"""
    date = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")
    
    print(f"📊 开始收集 {date} ({weekday}) 的股票数据...")
    
    # 收集数据
    print("🇺🇸 收集美股数据...")
    us_data = get_us_stocks()
    print(f"   收集到 {len(us_data)} 条美股数据")
    
    print("🇨🇳 收集 A 股数据...")
    cn_data = get_cn_stocks()
    print(f"   收集到 {len(cn_data)} 条 A 股数据")
    
    print("📰 收集市场新闻 (Tavily)...")
    news_data = get_market_news()
    print(f"   收集到 {len(news_data.get('us_news', []))} 条美股新闻，{len(news_data.get('cn_news', []))} 条 A 股新闻")
    
    # 保存数据
    save_data(date, us_data, cn_data, news_data)
    print(f"💾 数据已保存到 {DATA_DIR}/{date}.json")
    
    # 生成报告
    report = generate_report(date, us_data, cn_data, news_data)
    report_path = REPORTS_DIR / f"{date}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📄 报告已生成：{report_path}")
    
    # 更新 README
    update_readme(date, us_data, cn_data)
    
    print("✅ 完成！")
    
    # 打印摘要
    print("\n📊 今日摘要:")
    if "道琼斯" in us_data:
        print(f"   道琼斯：{us_data['道琼斯']['close']}")
    if "上证指数" in cn_data:
        print(f"   上证指数：{cn_data['上证指数'].get('close', '-')}")


def update_readme(date: str, us_data: dict, cn_data: dict):
    """更新 README.md"""
    readme_path = WORKSPACE / "README.md"
    
    # 读取现有 README 或创建新的
    if readme_path.exists():
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = """# 📈 每日股票行情跟踪

自动收集美股和 A 股每日行情数据，生成 Markdown 报告。

## 数据源

- **美股**: Stooq (https://stooq.com)
- **A 股**: 新浪财经 (http://hq.sinajs.cn)

## 目录结构

```
stock-daily/
├── data/          # 原始 JSON 数据
├── reports/       # Markdown 报告
├── collect_stocks.py  # 数据收集脚本
└── README.md      # 本文件
```

## 定时任务

每天 08:30 (Asia/Shanghai) 自动运行，更新数据并推送到 GitHub。

## 最新行情

"""
    
    # 生成最新行情摘要
    latest = f"""### {date}

**美股**: """
    if "道琼斯" in us_data:
        latest += f"道琼斯 {us_data['道琼斯']['close']} | "
    if "标普 500" in us_data:
        latest += f"标普 {us_data['标普 500']['close']} | "
    if "纳斯达克" in us_data:
        latest += f"纳指 {us_data['纳斯达克']['close']}"
    
    latest += "\n\n**A 股**: "
    if "上证指数" in cn_data:
        latest += f"上证 {cn_data['上证指数'].get('close', '-')} | "
    if "深证成指" in cn_data:
        latest += f"深证 {cn_data['深证成指'].get('close', '-')} | "
    if "创业板指" in cn_data:
        latest += f"创业板 {cn_data['创业板指'].get('close', '-')}"
    
    latest += "\n\n---\n"
    
    # 插入到"## 最新行情"后面
    if "## 最新行情" in content:
        content = content.replace("## 最新行情\n", f"## 最新行情\n{latest}")
    else:
        content += f"\n## 最新行情\n{latest}"
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"📝 README 已更新")


if __name__ == "__main__":
    main()
