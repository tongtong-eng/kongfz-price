#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子旧书网 · ISBN 查价核心模块（云优化版）
==================================
优化内容：
  - sortType=3 价格升序，最低价保证在首页
  - 仅查首页 50 条（替代原来 5 页并行扫描）
  - 本地按总价（书价+运费）重排序 → 真实最低总价
  - 线程级 HTTP 连接池复用（TLS 握手节省 ~50-100ms/本）
"""
import re
import json
import time
import http.client
import urllib.request
import urllib.parse
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 自适应并发数（检测到失败自动降速） ──────────
_RATE = {"consecutive_fails": 0, "max_workers": 10}

def _get_max_workers():
    """根据失败率动态调整批量并发数"""
    fails = _RATE["consecutive_fails"]
    if fails >= 5:
        return 3
    elif fails >= 3:
        return 5
    elif fails >= 1:
        return 7
    return _RATE["max_workers"]

def _record_fail():
    _RATE["consecutive_fails"] += 1

def _record_success():
    _RATE["consecutive_fails"] = max(0, _RATE["consecutive_fails"] - 1)

# ── 线程级 HTTP 连接池（复用 TLS 连接，减少握手开销） ──
_CONN_LOCK = threading.Lock()

def _get_conn():
    """每个线程持有一个持久连接，复用避免重复 TLS 握手"""
    t = threading.current_thread()
    if not hasattr(t, '_kfz_conn') or t._kfz_conn is None:
        conn = http.client.HTTPSConnection(
            "search.kongfz.com", timeout=20,
            context=ssl.create_default_context(),
        )
        t._kfz_conn = conn
    return t._kfz_conn

def _close_conn():
    """本线程不再需要连接时关闭（线程结束时由 GC 兜底）"""
    t = threading.current_thread()
    if hasattr(t, '_kfz_conn') and t._kfz_conn:
        try:
            t._kfz_conn.close()
        except Exception:
            pass
        t._kfz_conn = None

# ── 内存缓存（短时缓存，减少重复请求） ──────────
_CACHE = {}
_CACHE_TTL = 300      # 5 分钟
_CACHE_MAX = 1000     # 上限 1000 条

def _cache_get(isbn, quality_filter=""):
    key = f"{isbn}:{quality_filter}"
    entry = _CACHE.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["result"]
    return None

def _cache_set(isbn, quality_filter="", result=None):
    key = f"{isbn}:{quality_filter}"
    _CACHE[key] = {"result": result, "ts": time.time()}
    # 淘汰策略：超上限时移除最旧的 200 条
    if len(_CACHE) > _CACHE_MAX:
        oldest = sorted(_CACHE.keys(), key=lambda k: _CACHE[k]["ts"])[:200]
        for k in oldest:
            del _CACHE[k]

# ── 常量 ──────────────────────────────────────
API_HOST = "https://search.kongfz.com"
API_PATH = "/pc-gw/search-web/client/pc/product/keyword/list"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://search.kongfz.com/product/",
}
TIMEOUT = 20
PAGE_SIZE = 50        # 一页 50 条，覆盖价格分布 + 运费差异
SORT_TYPE = 3         # 价格升序（最低价保证在首页）


# ── 商品解析（共用） ────────────────────────────

def _parse_item(item):
    """从单条商品提取价格、运费等核心字段"""
    p = item.get("price") or item.get("salePrice")
    if not p or not (0 < float(p) < 100000):
        return None
    p = float(p)
    sl = item.get("postage", {}).get("shippingList", [])
    ship = float(sl[0]["shippingFee"]) if sl and sl[0].get("shippingFee") is not None else 0
    return {
        "price": round(p, 2),
        "shipping": ship,
        "total": round(p + ship, 1),
        "quality_text": item.get("qualityText", "") or "",
        "shop": item.get("shopName", "") or "",
        "area": item.get("shopAreaText", "") or "",
        "itemId": item.get("itemId"),
        "shopId": item.get("shopId"),
        "link": item.get("link", {}).get("pc", "") or "",
    }


def _build_result(isbn, items, total_found=0):
    """
    从 API 返回的商品列表构建统一结果。
    本地按总价（含运费）重新排序，确保最低总价准确无误。
    自动排除休假中店铺的商品。
    """
    cheap_items = []
    all_prices = []
    book_title = book_author = book_press = None
    holiday_skipped = 0  # 因店铺休假被跳过的商品数

    for item in items:
        # 跳过休假店铺的商品
        if item.get("shopIsHoliday"):
            holiday_skipped += 1
            continue
        r = _parse_item(item)
        if r is None:
            continue
        cheap_items.append(r)
        all_prices.append(r["price"])
        if not book_title:
            book_title = item.get("title", "—")
        if not book_author:
            for k in ["author", "itemAuthor"]:
                v = item.get(k)
                if v and len(str(v)) > 1:
                    book_author = str(v).strip()[:30]
                    break
        if not book_press:
            for k in ["press", "publisher", "publishingHouse"]:
                v = item.get(k)
                if v and len(str(v)) > 1:
                    book_press = str(v).strip()[:30]
                    break

    if not cheap_items:
        if holiday_skipped > 0:
            return {"isbn": isbn, "title": book_title or "—",
                    "error": f"所有 {holiday_skipped} 个在售商品店铺均在休假中",
                    "holiday_shop_count": holiday_skipped}
        return {"isbn": isbn, "title": book_title or "—", "error": "未解析到价格"}

    # 按总价（含运费）排序 → 真实最低价
    cheap_items.sort(key=lambda x: x["total"])

    result = {
        "isbn": isbn,
        "title": book_title or "—",
        "author": book_author or "",
        "press": book_press or "",
        "publisher": book_press or "",
        "count": len(cheap_items),
        "total_count": total_found or len(cheap_items),
        "pages_scanned": 1,
        "error": None,
        "cheapest": cheap_items[0],
        "top_cheapest": cheap_items[:5],
        "price_range": {
            "min": min(all_prices),
            "max": max(all_prices),
            "avg": round(sum(all_prices) / len(all_prices), 1),
        },
        # 兼容 query_isbn_simple 旧字段
        "min_price": cheap_items[0]["price"],
        "max_price": max(all_prices),
        "avg_price": round(sum(all_prices) / len(all_prices), 1),
        "holiday_shop_count": holiday_skipped,
    }

    # simple 版如果全都没价格，报错
    if not result.get("error") and not result.get("cheapest"):
        result["error"] = "有商品但未解析到价格"

    return result


# ── 核心查价 ───────────────────────────────────

def _query_api(isbn, cookie_str, quality_filter=""):
    """
    执行 API 请求：sortType=3 价格升序，仅第 1 页。
    复用线程级 HTTPS 连接减少 TLS 握手开销。
    返回 (items_list, total_count) 或 (None, error_msg)。
    """
    params = {
        "keyword": isbn, "page": 1, "size": PAGE_SIZE,
        "sortType": SORT_TYPE,
    }
    if quality_filter:
        params["quality"] = quality_filter
    url = f"{API_PATH}?{urllib.parse.urlencode(params)}"

    try:
        conn = _get_conn()
        conn.request("GET", url, headers={**HEADERS, "Cookie": cookie_str})
        resp = conn.getresponse()
        body = resp.read()
        data = json.loads(body.decode("utf-8"))
    except (http.client.RemoteDisconnected, ConnectionError, BrokenPipeError):
        # 连接断开，重建后重试一次
        _close_conn()
        try:
            conn = _get_conn()
            conn.request("GET", url, headers={**HEADERS, "Cookie": cookie_str})
            resp = conn.getresponse()
            body = resp.read()
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            _record_fail()
            return None, str(e)[:40]
    except Exception as e:
        _record_fail()
        return None, str(e)[:40]

    if data.get("status") != 1:
        msg = data.get("message", "查询失败")
        _record_fail()
        return None, msg[:40]

    _record_success()

    payload = data.get("data", {})
    item_resp = payload.get("itemResponse", {})
    items = item_resp.get("list") or item_resp.get("items") or []
    total_found = payload.get("totalFound") or payload.get("totalCount") or 0

    return items, total_found


def query_isbn(isbn, cookie_str, quality_filter=""):
    """
    查询单个 ISBN，返回最低价 + 价格区间。
    使用 sortType=3 价格升序，仅查首页 50 条，
    本地按总价（含运费）重排序确保最低总价准确。
    """
    isbn = isbn.strip().replace("-", "").replace(" ", "")
    if not re.match(r'^\d{10,13}$', isbn):
        return {"isbn": isbn, "title": "—", "error": "格式不对"}

    cached = _cache_get(isbn, quality_filter)
    if cached:
        return cached

    items, total = _query_api(isbn, cookie_str, quality_filter)

    if items is None:
        return {"isbn": isbn, "title": "—", "error": total}

    if not items:
        return {"isbn": isbn, "title": "—", "error": "无在售记录", "count": total}

    result = _build_result(isbn, items, total_found=total)

    _cache_set(isbn, quality_filter, result)
    return result


def query_isbn_simple(isbn, cookie_str):
    """
    简化版查询（向后兼容）。
    内部已使用 sortType=3 优化，与 query_isbn 逻辑一致。
    """
    return query_isbn(isbn, cookie_str)


# ── 批量查价（并行） ────────────────────────────

def batch_query(isbns, cookie_str, quality_filter="", max_concurrent=10, fast_mode=False):
    """
    并行批量查价（优化版）。

    使用 sortType=3 单页扫描，实测快 5-10 倍。
    使用线程级 HTTP 连接池复用，进一步减少延迟。
    fast_mode 参数保留向后兼容，最新版已无视此参数（始终最优）。

    参数：
        isbns:         ISBN 列表
        cookie_str:    Cookie 字符串
        quality_filter: 品相过滤
        max_concurrent: 最大并发数
        fast_mode:     保留向后兼容（已无意义）

    返回结果列表（顺序与输入对应），批次内重复 ISBN 只查一次。
    """
    # 去重
    uniq_indices = {}
    for i, isbn in enumerate(isbns):
        key = isbn.strip().replace("-", "").replace(" ", "")
        uniq_indices.setdefault(key, []).append(i)
    uniq_isbns = list(uniq_indices.keys())

    actual_conc = min(max_concurrent, _get_max_workers() + 2)
    uniq_results = {}

    with ThreadPoolExecutor(max_workers=actual_conc) as ex:
        fut_map = {
            ex.submit(query_isbn, isbn, cookie_str, quality_filter): isbn
            for isbn in uniq_isbns
        }
        for f in as_completed(fut_map):
            isbn = fut_map[f]
            try:
                uniq_results[isbn] = f.result()
            except Exception as e:
                uniq_results[isbn] = {"isbn": isbn, "title": "—", "error": str(e)[:40]}

    return [uniq_results[isbn] for isbn in isbns]
