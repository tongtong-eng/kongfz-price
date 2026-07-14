#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子旧书网 · ISBN 查价核心模块
==============================
提取自 web 版的多页并行查价逻辑，供 CLI / Web / 云服务共用。
"""
import re
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 内存缓存（短时缓存查价结果，减少重复请求） ──────────────
_CACHE = {}          # key: "isbn:quality" → result
_CACHE_TTL = 300     # 缓存有效期 5 分钟

def _cache_get(isbn, quality_filter=""):
    key = f"{isbn}:{quality_filter}"
    entry = _CACHE.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["result"]
    return None

def _cache_set(isbn, quality_filter="", result=None):
    key = f"{isbn}:{quality_filter}"
    _CACHE[key] = {"result": result, "ts": time.time()}

# ── 常量 ──────────────────────────────────────────────────
API_HOST = "https://search.kongfz.com"
API_PATH = "/pc-gw/search-web/client/pc/product/keyword/list"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://search.kongfz.com/product/",
}
TIMEOUT = 20
PAGE_SIZE = 30
MAX_PAGES = 5          # 最多扫描 5 页（150 条）
MAX_WORKERS = 4         # 并行翻页线程数


# ── 核心查价 ───────────────────────────────────────────────

def query_isbn(isbn, cookie_str, quality_filter=""):
    """查询单个 ISBN，返回价格信息（含多页并行扫描）"""
    isbn = isbn.strip().replace("-", "").replace(" ", "")
    if not re.match(r'^\d{8,13}$', isbn):
        return {"isbn": isbn, "title": "—", "error": "格式不对"}

    cached = _cache_get(isbn, quality_filter)
    if cached:
        return cached

    # 第 1 页：获取书名 + 总量 + 商品列表
    params_dict = {"keyword": isbn, "page": 1, "size": PAGE_SIZE}
    if quality_filter:
        params_dict["quality"] = quality_filter
    url = f"{API_HOST}{API_PATH}?{urllib.parse.urlencode(params_dict)}"

    try:
        req = urllib.request.Request(url, headers={**HEADERS, "Cookie": cookie_str})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"isbn": isbn, "title": "—", "error": str(e)[:30]}

    if data.get("status") != 1:
        msg = data.get("message", "查询失败")
        return {"isbn": isbn, "title": "—", "error": msg[:30]}

    payload = data.get("data", {})
    item_resp = payload.get("itemResponse", {})
    total = payload.get("totalFound") or payload.get("totalCount") or 0
    items = item_resp.get("list") or item_resp.get("items") or []
    if not items:
        return {"isbn": isbn, "title": "—", "error": "无在售记录", "count": total}

    title = items[0].get("title", "—")
    author = items[0].get("author", "")
    press = items[0].get("press", "")

    # 翻页扫描：第 1 页已获取，第 2~MAX_PAGES 页并行请求
    all_items = list(items)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    max_pages = min(total_pages, MAX_PAGES)

    if max_pages > 1:
        page_urls = {}
        for page in range(2, max_pages + 1):
            pd = {"keyword": isbn, "page": page, "size": PAGE_SIZE}
            if quality_filter:
                pd["quality"] = quality_filter
            page_urls[page] = f"{API_HOST}{API_PATH}?{urllib.parse.urlencode(pd)}"

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            fut_map = {}
            for page, pu in page_urls.items():
                req2 = urllib.request.Request(pu, headers={**HEADERS, "Cookie": cookie_str})
                fut = ex.submit(
                    lambda r: json.loads(
                        urllib.request.urlopen(r, timeout=15).read().decode("utf-8")
                    ),
                    req2,
                )
                fut_map[fut] = page
            for f in as_completed(fut_map):
                try:
                    d2 = f.result()
                    more = d2.get("data", {}).get("itemResponse", {}).get("list") or []
                    all_items.extend(more)
                except Exception:
                    pass

    # 解析价格
    cheap_items = []
    all_prices = []
    for item in all_items:
        p = item.get("price") or item.get("salePrice")
        if not p or not (0 < float(p) < 100000):
            continue
        p = float(p)
        ship_fee = 0
        sl = item.get("postage", {}).get("shippingList", [])
        if sl and sl[0].get("shippingFee") is not None:
            ship_fee = float(sl[0]["shippingFee"])

        cheap_items.append({
            "price": round(p, 2),
            "shipping": ship_fee,
            "total": round(p + ship_fee, 1),
            "quality_text": item.get("qualityText", "") or "",
            "shop": item.get("shopName", "") or "",
            "area": item.get("shopAreaText", "") or "",
            "itemId": item.get("itemId"),
            "shopId": item.get("shopId"),
            "link": item.get("link", {}).get("pc", "") or "",
        })
        all_prices.append(p)

    if not cheap_items:
        return {"isbn": isbn, "title": title, "error": "未解析到价格", "count": total}

    cheap_items.sort(key=lambda x: x["total"])
    cheapest = cheap_items[0]

    result = {
        "isbn": isbn,
        "title": title,
        "author": author[:20],
        "press": press[:20],
        "count": len(cheap_items),
        "total_count": total,
        "pages_scanned": max_pages,
        "error": None,
        "cheapest": cheapest,
        "top_cheapest": cheap_items[:5],
        "price_range": {
            "min": min(all_prices),
            "max": max(all_prices),
            "avg": round(sum(all_prices) / len(all_prices), 1),
        },
    }
    _cache_set(isbn, quality_filter, result)
    return result


def query_isbn_simple(isbn, cookie_str):
    """简化版查询（仅第 1 页，无运费解析），供 CLI 快速查价用"""
    isbn = isbn.strip().replace("-", "").replace(" ", "")
    if not re.match(r'^\d{10,13}$', isbn):
        return {"isbn": isbn, "error": "ISBN 格式不正确"}

    cached = _cache_get(isbn)
    if cached:
        return cached

    params = urllib.parse.urlencode({"keyword": isbn, "page": 1, "size": 20})
    url = f"{API_HOST}{API_PATH}?{params}"

    try:
        req = urllib.request.Request(url, headers={**HEADERS, "Cookie": cookie_str})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"isbn": isbn, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"isbn": isbn, "error": str(e)[:60]}

    if data.get("status") != 1:
        msg = data.get("message", "")
        if "登录" in msg:
            return {"isbn": isbn, "error": "Cookie 失效，请重新 --login"}
        return {"isbn": isbn, "error": msg[:40]}

    payload = data.get("data", {})
    items = []
    item_resp = payload.get("itemResponse")
    if isinstance(item_resp, dict):
        items = item_resp.get("list") or item_resp.get("items") or []
    if not items:
        for key in ["items", "list", "productList", "result", "records"]:
            candidate = payload.get(key)
            if candidate:
                if isinstance(candidate, dict):
                    items = candidate.get("list") or candidate.get("items") or []
                elif isinstance(candidate, list):
                    items = candidate
                break
    if not items:
        for key in payload:
            if isinstance(payload[key], list) and len(payload[key]) > 0:
                items = payload[key]
                break

    # 总量
    total_count = 0
    pager = payload.get("pager", {})
    if pager:
        total_count = pager.get("totalCount") or pager.get("total") or pager.get("count") or 0
    elif payload.get("totalCount"):
        total_count = payload["totalCount"]
    elif payload.get("totalFound"):
        total_count = payload["totalFound"]
    else:
        total_count = len(items)

    # 提取价格 + 运费
    cheap_items = []
    all_prices = []
    titles = set()
    book_title = book_author = book_press = None

    for item in items:
        if not isinstance(item, dict):
            continue
        # 标题
        for k in ["title", "itemName", "bookName", "name", "productName"]:
            v = item.get(k)
            if v and len(str(v)) > 3:
                t = re.sub(r'<[^>]+>', '', str(v)).strip()
                if t and t not in titles:
                    titles.add(t)
                    book_title = book_title or t

        # 价格
        price_val = None
        for k in ["price", "salePrice", "currentPrice", "showPrice", "itemPrice"]:
            v = item.get(k)
            if v is not None:
                try:
                    price_val = float(v)
                    break
                except (ValueError, TypeError):
                    pass
        if price_val is None:
            for k in ["priceText", "priceStr", "showPriceText"]:
                v = item.get(k)
                if v:
                    m = re.search(r'(\d+\.?\d*)', str(v))
                    if m:
                        price_val = float(m.group(1))
                        break
        if not price_val or not (0 < price_val < 100000):
            continue

        # 运费（与 query_isbn 同样的解析逻辑）
        ship_fee = 0
        sl = item.get("postage", {}).get("shippingList", [])
        if sl and sl[0].get("shippingFee") is not None:
            ship_fee = float(sl[0]["shippingFee"])

        cheap_items.append({
            "price": round(price_val, 2),
            "shipping": ship_fee,
            "total": round(price_val + ship_fee, 1),
            "quality_text": item.get("qualityText", "") or "",
            "shop": item.get("shopName", "") or "",
            "area": item.get("shopAreaText", "") or "",
            "itemId": item.get("itemId"),
            "shopId": item.get("shopId"),
            "link": item.get("link", {}).get("pc", "") or "",
        })
        all_prices.append(price_val)

        if not book_author:
            for k in ["author", "itemAuthor"]:
                v = item.get(k)
                if v and len(str(v)) > 1:
                    book_author = str(v).strip()[:30]
        if not book_press:
            for k in ["press", "publisher", "publishingHouse"]:
                v = item.get(k)
                if v and len(str(v)) > 1:
                    book_press = str(v).strip()[:30]

    # 按总价（含运费）排序
    cheap_items.sort(key=lambda x: x["total"])
    prices = [c["price"] for c in cheap_items]

    result = {
        "isbn": isbn,
        "title": book_title,
        "author": book_author,
        "publisher": book_press,
        "press": book_press,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
        "count": total_count or len(items),
        "total_count": total_count or len(items),
        "pages_scanned": 1,
        "error": None,
        "price_range": {
            "min": min(prices) if prices else 0,
            "max": max(prices) if prices else 0,
            "avg": round(sum(prices) / len(prices), 1) if prices else 0,
        },
    }

    # 添加 cheapest（含运费），使前端渲染能正常工作
    if cheap_items:
        result["cheapest"] = cheap_items[0]
        result["top_cheapest"] = cheap_items[:5]

    if not prices and total_count > 0:
        result["error"] = "有商品但未解析到价格"
    elif not prices:
        result["error"] = "孔夫子无在售记录"

    _cache_set(isbn, result=result)
    return result


# ── 批量查价（并行） ────────────────────────────────────────

def batch_query(isbns, cookie_str, quality_filter="", max_concurrent=10, fast_mode=False):
    """
    并行批量查价。

    参数：
        isbns:        ISBN 列表
        cookie_str:   Cookie 字符串
        quality_filter: 品相过滤
        max_concurrent: 最大并发数
        fast_mode:    True = 仅第 1 页（更快，最低价通常在首页）
                      False = 扫最多 5 页（更全，含价格区间统计）

    返回结果列表（顺序与输入对应），批次内重复 ISBN 只查一次。
    """
    # 去重：批次内相同 ISBN 只查一次，结果复制
    uniq_indices = {}
    for i, isbn in enumerate(isbns):
        uniq_indices.setdefault(isbn, []).append(i)
    uniq_isbns = list(uniq_indices.keys())

    query_fn = query_isbn_simple if fast_mode else query_isbn
    kwargs = {"cookie_str": cookie_str}
    if not fast_mode:
        kwargs["quality_filter"] = quality_filter

    uniq_results = {}
    with ThreadPoolExecutor(max_workers=max_concurrent) as ex:
        fut_map = {
            ex.submit(query_fn, isbn, **kwargs): isbn
            for isbn in uniq_isbns
        }
        for f in as_completed(fut_map):
            isbn = fut_map[f]
            try:
                uniq_results[isbn] = f.result()
            except Exception as e:
                uniq_results[isbn] = {"isbn": isbn, "title": "—", "error": str(e)[:40]}

    # 结果按原始顺序排列
    results = []
    for isbn in isbns:
        results.append(uniq_results[isbn])
    return results
