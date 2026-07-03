"""
kongfz_inventory.py — 孔夫子旧书网共享库存模块

提供基于 JSON 文件的库存 CRUD 和统计功能。
纯 Python 标准库，零外部依赖。
"""

import json
import os
from datetime import date
from typing import Optional

MAX_ITEMS = 1000


# ─── 读写 ───────────────────────────────────────────────────────


def load_inventory(storage_path: str) -> dict:
    """读取库存 JSON 文件，不存在或损坏时返回空结构。"""
    if not os.path.isfile(storage_path):
        return {"next_id": 1, "items": []}
    try:
        with open(storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 确保必要字段存在
        if "next_id" not in data:
            data["next_id"] = 1
        if "items" not in data:
            data["items"] = []
        return data
    except (json.JSONDecodeError, OSError):
        return {"next_id": 1, "items": []}


def save_inventory(data: dict, storage_path: str) -> None:
    """写入库存 JSON 文件，自动创建目录。"""
    os.makedirs(os.path.dirname(os.path.abspath(storage_path)), exist_ok=True)
    with open(storage_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── CRUD ───────────────────────────────────────────────────────


def add_item(
    isbn: str,
    title: str,
    author: str,
    cost_price: float,
    shipping: float,
    source_batch: str,
    storage_path: str,
) -> dict:
    """添加一条库存记录。

    自动计算 total_cost、设置当天 buy_date，插入到列表最前面。
    超 1000 条时移除最旧记录。
    """
    data = load_inventory(storage_path)

    item = {
        "id": data["next_id"],
        "isbn": isbn,
        "title": title,
        "author": author,
        "cost_price": round(cost_price, 2),
        "shipping": round(shipping, 2),
        "total_cost": round(cost_price + shipping, 2),
        "buy_date": date.today().isoformat(),
        "source_batch": source_batch,
        "status": "in_stock",
        "sale_price": None,
        "sale_date": None,
    }

    data["items"].insert(0, item)

    # 限制最大条目数
    if len(data["items"]) > MAX_ITEMS:
        data["items"] = data["items"][:MAX_ITEMS]

    data["next_id"] += 1
    save_inventory(data, storage_path)
    return item


def _find_item(data: dict, item_id: int) -> Optional[dict]:
    """在 data["items"] 中按 id 查找条目。"""
    for item in data["items"]:
        if item["id"] == item_id:
            return item
    return None


def sell_item(item_id: int, sale_price: float, storage_path: str) -> bool:
    """标记商品为已售。"""
    data = load_inventory(storage_path)
    item = _find_item(data, item_id)
    if item is None or item["status"] != "in_stock":
        return False

    item["status"] = "sold"
    item["sale_price"] = round(sale_price, 2)
    item["sale_date"] = date.today().isoformat()
    save_inventory(data, storage_path)
    return True


def update_sale_price(item_id: int, sale_price: float, storage_path: str) -> bool:
    """修改已售记录的价格（卖错了更正）。"""
    data = load_inventory(storage_path)
    item = _find_item(data, item_id)
    if item is None or item["status"] != "sold":
        return False

    item["sale_price"] = round(sale_price, 2)
    save_inventory(data, storage_path)
    return True


def delete_item(item_id: int, storage_path: str) -> bool:
    """从列表中删除记录。"""
    data = load_inventory(storage_path)
    for i, item in enumerate(data["items"]):
        if item["id"] == item_id:
            del data["items"][i]
            save_inventory(data, storage_path)
            return True
    return False


# ─── 统计 ───────────────────────────────────────────────────────


def get_stats(items: list, period: Optional[str] = None) -> dict:
    """统计盈亏数据。

    period:
      None  — 全部
      "2026-07" — 某月
      "2026"    — 某年

    只统计 status="sold" 且有 sale_date 的记录。
    """
    # 筛选已售且有 sale_date 的记录
    sold = [it for it in items if it["status"] == "sold" and it.get("sale_date")]

    if period:
        sold = [it for it in sold if it["sale_date"].startswith(period)]

    if not sold:
        return {
            "period": period,
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "profit": 0.0,
            "margin": 0.0,
            "sold_count": 0,
            "in_stock_count": sum(
                1 for it in items if it["status"] == "in_stock"
            ),
            "best_book": None,
        }

    total_revenue = round(sum(it["sale_price"] for it in sold), 2)
    total_cost = round(sum(it["total_cost"] for it in sold), 2)
    profit = round(total_revenue - total_cost, 2)
    margin = round((profit / total_revenue * 100) if total_revenue > 0 else 0.0, 2)

    # 最赚钱的书
    best_book = max(sold, key=lambda it: it["sale_price"] - it["total_cost"])
    best_book_info = {
        "id": best_book["id"],
        "title": best_book["title"],
        "profit": round(best_book["sale_price"] - best_book["total_cost"], 2),
    }

    return {
        "period": period,
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "profit": profit,
        "margin": margin,
        "sold_count": len(sold),
        "in_stock_count": sum(1 for it in items if it["status"] == "in_stock"),
        "best_book": best_book_info,
    }
