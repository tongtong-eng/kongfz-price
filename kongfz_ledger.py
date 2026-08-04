#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子查价 · 记账模块（进/销单，差价盈利）
====================================
- 按单记：进货单 / 卖出单，一单一种书（可多本）
- 盈利 = 数量×售价 − 数量×成本（只算差价）
- 数据存 JSON 文件，上限 500 条
"""
import json
import os
import time
from datetime import date, datetime, timedelta

# 数据文件（测试可覆盖为临时文件）
LEDGER_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "kongfz_ledger.json"
)
LEDGER_MAX = 500  # 记录上限


def _round2(x):
    return round(x, 2)


def load_ledger():
    """读取全部记录，文件损坏时重置为空"""
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("records"), list):
                return data
        except Exception:
            pass
    return {"records": []}


def save_ledger(data):
    os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_record(type_, book, isbn, qty, unit, cost, date_str=None):
    """
    记一笔。type_='in' 进货 / 'out' 卖出。
    - 进货：cost（总成本）= qty × unit
    - 卖出：cost（总成本）= qty × cost，sale（销售额）= qty × unit，profit = sale − cost
    返回新记录 dict。
    """
    type_ = type_ if type_ in ("in", "out") else "in"
    qty = int(qty)
    unit = float(unit)
    if not date_str:
        date_str = date.today().strftime("%Y-%m-%d")
    rec = {
        "id": f"{'IN' if type_ == 'in' else 'OUT'}_{int(time.time() * 1000)}",
        "type": type_,
        "book": str(book or "").strip(),
        "isbn": str(isbn or "").strip(),
        "qty": qty,
        "unit": unit,
        "date": str(date_str),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if type_ == "in":
        rec["cost"] = _round2(qty * unit)
    else:
        cost = float(cost)
        rec["cost"] = _round2(qty * cost)
        rec["sale"] = _round2(qty * unit)
        rec["profit"] = _round2(rec["sale"] - rec["cost"])

    data = load_ledger()
    data["records"].insert(0, rec)
    if len(data["records"]) > LEDGER_MAX:
        data["records"] = data["records"][:LEDGER_MAX]
    save_ledger(data)
    return rec


def list_records(limit=20, type_filter=""):
    """明细列表（按写入顺序倒序），可选按 in/out 过滤"""
    records = load_ledger()["records"]
    if type_filter in ("in", "out"):
        records = [r for r in records if r["type"] == type_filter]
    return records[:limit]


def delete_record(rid):
    """删除一笔，存在且被删除返回 True"""
    data = load_ledger()
    before = len(data["records"])
    data["records"] = [r for r in data["records"] if r["id"] != rid]
    if len(data["records"]) != before:
        save_ledger(data)
        return True
    return False


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _sum_range(records, start, end):
    """统计 [start, end] 日期范围内进货/销售/盈利"""
    in_cost = out_sale = profit = 0
    in_count = out_count = 0
    for r in records:
        d = _parse_date(r.get("date", ""))
        if d is None or not (start <= d <= end):
            continue
        if r.get("type") == "out":
            out_sale += r.get("sale", 0)
            profit += r.get("profit", 0)
            out_count += 1
        else:
            in_cost += r.get("cost", 0)
            in_count += 1
    return {
        "in_cost": _round2(in_cost),
        "out_sale": _round2(out_sale),
        "profit": _round2(profit),
        "in_count": in_count,
        "out_count": out_count,
    }


def summary(scope="today"):
    """今日/本周/本月汇总。scope: today | week | month"""
    t = date.today()
    if scope == "week":
        start = t - timedelta(days=t.weekday())  # 本周一
    elif scope == "month":
        start = t.replace(day=1)  # 本月 1 号
    else:
        start = t
    agg = _sum_range(load_ledger()["records"], start, t)
    agg["scope"] = scope
    return agg


def trends(weeks=8, months=6):
    """返回最近 N 周、最近 N 月聚合，供前端滚动表格展示"""
    t = date.today()
    week_list = []
    for i in range(weeks - 1, -1, -1):
        ws = t - timedelta(days=t.weekday() + 7 * i)
        we = ws + timedelta(days=6)
        agg = _sum_range(load_ledger()["records"], ws, we)
        agg["label"] = f"{ws.month}月{ws.day}日-{we.month}月{we.day}日"
        week_list.append(agg)

    month_list = []
    for i in range(months - 1, -1, -1):
        y, m = t.year, t.month - i
        while m <= 0:
            y -= 1
            m += 12
        ms = date(y, m, 1)
        me = date(y + 1, 1, 1) - timedelta(days=1) if m == 12 else date(y, m + 1, 1) - timedelta(days=1)
        agg = _sum_range(load_ledger()["records"], ms, me)
        agg["label"] = f"{y}年{m}月"
        month_list.append(agg)

    return {"weekly": week_list, "monthly": month_list}
