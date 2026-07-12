#!/usr/bin/env python3
"""
Trade Nothing v0.9 — Catalyst Calendar (催化剂日历)

Auto-fetches macro economic calendar and industry key events to answer "Why Now?".
Supports: global macro events, A-share earnings calendar, sector policy windows.

Usage:
  python3 catalyst_calendar.py --sector solar
  python3 catalyst_calendar.py --code 300118
  python3 catalyst_calendar.py --macro
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import clean_proxy_env

clean_proxy_env()


SECTOR_CATALYSTS = {
    "solar": {
        "display_name": "光伏 / Solar Energy",
        "recurring_events": [
            {"event": "SNEC 上海光伏展", "typical_month": 6, "impact": "新技术路线发布、订单预期"},
            {"event": "中国光伏行业协会年会", "typical_month": 12, "impact": "产业政策风向"},
            {"event": "IEA World Energy Outlook", "typical_month": 10, "impact": "全球能源转型预期调整"},
            {"event": "光伏组件招标季 (央企/国企)", "typical_month": 3, "impact": "技术路线选择信号 (TOPCon vs HJT)"},
        ],
        "watch_list": [
            "SpaceX Starlink V3 卫星发射进度",
            "中国电价市场化改革政策",
            "硅料产能投放节奏 (供给侧)",
            "欧盟碳关税 (CBAM) 实施进度",
        ]
    },
    "semiconductor": {
        "display_name": "半导体 / Semiconductor",
        "recurring_events": [
            {"event": "TSMC 法说会", "typical_month": 1, "impact": "全球半导体景气度风向标"},
            {"event": "SEMICON China", "typical_month": 3, "impact": "设备/材料国产化进展"},
            {"event": "美国半导体出口管制更新", "typical_month": None, "impact": "国产替代加速/受阻"},
            {"event": "消费电子旺季备货 (Q3)", "typical_month": 7, "impact": "需求端拐点信号"},
        ],
        "watch_list": [
            "AI 算力芯片出口管制变化",
            "中国存储芯片 (CXMT/YMTC) 量产进度",
            "车规级芯片需求变化",
            "HBM/先进封装产能瓶颈",
        ]
    },
    "ai": {
        "display_name": "人工智能 / AI",
        "recurring_events": [
            {"event": "NVIDIA GTC 大会", "typical_month": 3, "impact": "新架构/芯片发布，算力需求预期"},
            {"event": "OpenAI/Google 模型发布节奏", "typical_month": None, "impact": "推理需求量级跳跃"},
            {"event": "中国 AI 政策 (两会/国务院)", "typical_month": 3, "impact": "产业扶持力度"},
        ],
        "watch_list": [
            "推理成本下降曲线 (DeepSeek 效应)",
            "端侧 AI 部署进度 (手机/PC/汽车)",
            "数据中心电力供应瓶颈",
            "AI 应用 DAU/MAU 增长 (ToC 变现)",
        ]
    },
    "energy": {
        "display_name": "能源 / Energy",
        "recurring_events": [
            {"event": "OPEC+ 部长级会议", "typical_month": None, "impact": "原油供给预期"},
            {"event": "EIA 周度库存报告", "typical_month": None, "impact": "短期供需平衡"},
            {"event": "北半球冬季供暖季", "typical_month": 11, "impact": "天然气/煤炭需求高峰"},
            {"event": "中国发改委能源价格调整", "typical_month": None, "impact": "国内能源价格预期"},
        ],
        "watch_list": [
            "地缘政治风险 (中东/俄乌)",
            "美国页岩油产量变化",
            "中国战略石油储备动态",
            "全球 LNG 新增产能投放",
        ]
    },
}


def get_macro_calendar() -> list:
    """获取全球宏观经济日历中的关键事件"""
    macro_events = [
        {"event": "美联储 FOMC 利率决议", "frequency": "~6周/次", "next_approx": "查询 Fed 官网",
         "impact": "全球流动性之锚", "relevance": "所有资产类别"},
        {"event": "中国 PMI (官方+财新)", "frequency": "月度", "typical_day": "月末/月初",
         "impact": "中国经济景气度", "relevance": "A股/港股/大宗商品"},
        {"event": "中国社融/M2 数据", "frequency": "月度", "typical_day": "10-15日",
         "impact": "信用脉冲", "relevance": "A股整体估值"},
        {"event": "美国非农就业", "frequency": "月度", "typical_day": "首个周五",
         "impact": "美联储政策预期", "relevance": "美元/美股/全球风险偏好"},
        {"event": "美国 CPI", "frequency": "月度", "typical_day": "10-13日",
         "impact": "通胀预期 → 利率预期", "relevance": "全球资产定价"},
        {"event": "中国 GDP (季度)", "frequency": "季度", "typical_day": "1/4/7/10月中旬",
         "impact": "经济基本面锚定", "relevance": "A股/人民币"},
    ]

    try:
        import akshare as ak
        df = ak.news_economic_baidu(symbol="美国")
        if df is not None and not df.empty:
            for _, row in df.head(10).iterrows():
                macro_events.append({
                    "event": row.get("事件", ""),
                    "date": str(row.get("日期", "")),
                    "impact": row.get("重要性", ""),
                    "source": "AkShare_Baidu"
                })
    except Exception as e:
        print(f"[INFO] AkShare macro calendar unavailable: {e}", file=sys.stderr)

    return macro_events


def get_earnings_calendar(code: str) -> dict:
    """获取个股财报披露日历"""
    result = {
        "code": code,
        "upcoming_events": [],
        "source": "estimated"
    }

    year = datetime.now().year

    result["upcoming_events"] = [
        {"event": f"{year}年一季报披露", "window": f"{year}-04-01 ~ {year}-04-30",
         "impact": "验证全年业绩趋势"},
        {"event": f"{year}年中报披露", "window": f"{year}-07-01 ~ {year}-08-31",
         "impact": "半年维度业绩兑现"},
        {"event": f"{year}年三季报披露", "window": f"{year}-10-01 ~ {year}-10-31",
         "impact": "全年业绩基本确定"},
        {"event": f"{year-1}年年报 + {year}年一季报预告", "window": f"{year}-01-01 ~ {year}-04-30",
         "impact": "年度总结 + 新年展望"},
    ]

    try:
        import akshare as ak
        df = ak.stock_report_disclosure_szse(date=str(year))
        if df is not None and not df.empty:
            match = df[df["证券代码"].astype(str).str.contains(code)]
            if not match.empty:
                result["actual_disclosure"] = match.to_dict("records")
                result["source"] = "AkShare_SZSE"
    except Exception as e:
        result["note"] = f"Disclosure calendar lookup failed: {e}. Using estimates."

    return result


def main():
    parser = argparse.ArgumentParser(description="Catalyst Calendar")
    parser.add_argument("--sector", help="Industry sector (solar/semiconductor/ai/energy)")
    parser.add_argument("--code", help="Stock code for earnings calendar")
    parser.add_argument("--macro", action="store_true", help="Show global macro calendar")
    args = parser.parse_args()

    output = {"timestamp": datetime.now().isoformat(), "catalysts": {}}

    if args.macro:
        output["catalysts"]["macro"] = get_macro_calendar()

    if args.sector:
        sector = args.sector.lower()
        if sector in SECTOR_CATALYSTS:
            output["catalysts"]["sector"] = SECTOR_CATALYSTS[sector]
        else:
            output["catalysts"]["sector"] = {
                "error": f"Unknown sector '{sector}'. Available: {list(SECTOR_CATALYSTS.keys())}"
            }

    if args.code:
        output["catalysts"]["earnings"] = get_earnings_calendar(args.code)

    if not any([args.sector, args.code, args.macro]):
        output["catalysts"]["macro"] = get_macro_calendar()
        output["note"] = "No specific query — showing macro calendar. Use --sector or --code for targeted results."

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
