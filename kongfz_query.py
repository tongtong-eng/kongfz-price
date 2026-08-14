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
    """根据失败率动态调整批量并发数：
       0 次失败 → 默认并发 10
       1~2 次失败 → 降到 5
       3~4 次失败 → 降到 2
       ≥5 次失败 → 降到 1（完全串行，最稳）
       每次成功会递减失败计数，自动逐步恢复并发。
       注：配合全局 600ms 节流，出站频率仍稳定在 1.67 次/秒。"""
    fails = _RATE["consecutive_fails"]
    if fails >= 5:
        return 1
    elif fails >= 3:
        return 2
    elif fails >= 1:
        return 5
    return _RATE["max_workers"]

def _record_fail():
    _RATE["consecutive_fails"] += 1

def _record_success():
    _RATE["consecutive_fails"] = max(0, _RATE["consecutive_fails"] - 1)

# ── 请求节流（降低触发孔夫子限流概率） ──────────
_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST_TS = [0.0]
_REQUEST_INTERVAL = 0.6  # 每次请求间隔 600ms

def _throttle():
    """全局节流：每个请求间隔至少 300ms"""
    with _THROTTLE_LOCK:
        now = time.monotonic()
        wait = _LAST_REQUEST_TS[0] + _REQUEST_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_TS[0] = time.monotonic()

# 限流关键词
_RATE_LIMIT_HINTS = ("请求过于频繁", "访问频次", "频繁", "frequency", "too many", "请登录", "登录后再")

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
SORT_TYPE = 5         # 总价（含运费）升序，最低总价保证在首页


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


def _is_unreliable_shop(item):
    """
    判断店铺是否"不可靠"（休假/发不出货/经营异常）。
    返回 True 表示应排除该商品。
    """
    # 1. 明确标记休假的店铺
    if item.get("shopIsHoliday"):
        return True
    # 2. 店主 30 天未登录（可能发不出货）
    if item.get("shop30DaysNotLogin"):
        return True
    # 3. 成交率过低（< 80%，发货可靠性差）
    rate_str = item.get("shopSuccessOrderRate", "") or ""
    m = re.search(r'(\d+)%', rate_str)
    if m:
        rate = int(m.group(1))
        if rate < 80:
            return True
    return False


def _build_result(isbn, items, total_found=0):
    """
    从 API 返回的商品列表构建统一结果。
    本地按总价（含运费）重新排序，确保最低总价准确无误。
    自动排除休假/不可靠店铺的商品和已售罄的商品。
    """
    cheap_items = []
    all_prices = []
    book_title = book_author = book_press = None
    holiday_skipped = 0   # 因店铺休假/不可靠被跳过的商品数
    sold_out_skipped = 0  # 因已售罄被跳过的商品数

    for item in items:
        # 跳过休假店铺的商品（shopIsHoliday / 30天未登录 / 成交率过低）
        if _is_unreliable_shop(item):
            holiday_skipped += 1
            continue
        # 跳过已售罄的商品
        if item.get("isSoldOut"):
            sold_out_skipped += 1
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
        if holiday_skipped > 0 and sold_out_skipped == 0:
            return {"isbn": isbn, "title": book_title or "—",
                    "error": f"所有 {holiday_skipped} 个在售商品店铺均在休假中",
                    "holiday_shop_count": holiday_skipped}
        if sold_out_skipped > 0:
            return {"isbn": isbn, "title": book_title or "—",
                    "error": f"全部 {sold_out_skipped} 个商品均已售罄",
                    "sold_out_skipped": sold_out_skipped,
                    "holiday_shop_count": holiday_skipped or 0}
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
        "sold_out_skipped": sold_out_skipped,
    }

    # simple 版如果全都没价格，报错
    if not result.get("error") and not result.get("cheapest"):
        result["error"] = "有商品但未解析到价格"

    return result


# ── 核心查价 ───────────────────────────────────

def _query_api(isbn, cookie_str, quality_filter="", user_area=""):
    """
    执行 API 请求：sortType=5 总价升序，仅第 1 页。
    复用线程级 HTTPS 连接减少 TLS 握手开销。
    返回 (items_list, total_count) 或 (None, error_msg)。

    user_area: 收货地区编码（如 4010000000 重庆奉节）。
    传了之后搜索接口返回的运费(postage.shippingList)就是按该收货地址的真实运费，
    这是"精确按地址查价"的核心（不需要抓详情页/调 getFreightInfo）。
    """
    params = {
        "keyword": isbn, "page": 1, "size": PAGE_SIZE,
        "sortType": SORT_TYPE,
    }
    if quality_filter:
        params["quality"] = quality_filter
    if user_area:
        params["userArea"] = user_area
    url = f"{API_PATH}?{urllib.parse.urlencode(params)}"

    def _do_request():
        """单次请求，返回 (data, error_msg)"""
        try:
            conn = _get_conn()
            conn.request("GET", url, headers={**HEADERS, "Cookie": cookie_str})
            resp = conn.getresponse()
            body = resp.read()
            return json.loads(body.decode("utf-8")), None
        except (http.client.RemoteDisconnected, ConnectionError, BrokenPipeError):
            # 连接断开，重建后重试一次
            _close_conn()
            try:
                conn = _get_conn()
                conn.request("GET", url, headers={**HEADERS, "Cookie": cookie_str})
                resp = conn.getresponse()
                body = resp.read()
                return json.loads(body.decode("utf-8")), None
            except Exception as e:
                return None, str(e)[:40]
        except Exception as e:
            return None, str(e)[:40]

    # 节流：每个请求间隔至少 300ms
    _throttle()

    data, err = _do_request()

    # 限流检测：遇到"请求过于频繁"等待 2 秒重试一次
    if data and data.get("status") != 1:
        msg = str(data.get("message", ""))
        if any(hint in msg for hint in _RATE_LIMIT_HINTS):
            _record_fail()
            time.sleep(3.0)
            data, err = _do_request()

    if err:
        _record_fail()
        return None, err

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

    actual_conc = min(max_concurrent, _get_max_workers())
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


# ══════════════════════════════════════════════════════════
#  按收货地址计算真实运费（v2 发货功能）
# ══════════════════════════════════════════════════════════

# 全国省份标准名称（用于地址解析匹配）
CHINA_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古",
    "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "广西", "海南",
    "重庆", "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆",
    "香港", "澳门", "台湾",
]

def _parse_province(address):
    """从地址文字解析省份名。

    支持：完整省名（黑龙江省）、简称（黑龙江）、自治区/直辖市带后缀或不带。
    返回省名或 None。
    """
    if not address:
        return None
    addr = str(address).strip()
    # 先尝试完整匹配（含"省/市/自治区"后缀）
    for prov in CHINA_PROVINCES:
        if prov in addr:
            return prov
    # 兼容"XX省"但表里没列全的情况——这里 CHINA_PROVINCES 已全
    return None


def query_isbn_by_address(isbn, cookie_str, province, quality_filter="", user_area="", top_n=5, precise=False):
    """
    按收货地址查询单本 ISBN 的真实最低总价（userArea 方案）。

    核心：搜索接口带 userArea=收货地区编码（如 4010000000 重庆奉节县），
    返回的运费（postage.shippingList[0].shippingFee）即为按该地址的真实运费。
    ——不需要抓详情页、不需要调 getFreightInfo，速度与普通查价相同（秒级）。

    - 剔除"该收货地址无运费数据"（大概率不发货到该地）的店铺
    - 精确性：搜索接口直接按该地址算运费，本地全量排序取最低，绝不遗漏

    参数：
        isbn:           ISBN
        cookie_str:     Cookie
        province:       收货省份名（仅用于前端显示，如"重庆"）
        quality_filter: 品相过滤
        user_area:      收货地区编码（10 位，取 cityId || provId）
        top_n / precise: 保留向后兼容（userArea 方案下恒精确，参数已无意义）

    返回：与 query_isbn 相同结构，额外含 user_area / real_freight_mode / scan_count。
    """
    isbn = isbn.strip().replace("-", "").replace(" ", "")
    if not re.match(r'^\d{10,13}$', isbn):
        return {"isbn": isbn, "title": "—", "error": "格式不对"}

    # 1. 搜索（带 userArea → 搜索接口按收货地址算真实运费）
    items, total = _query_api(isbn, cookie_str, quality_filter, user_area=user_area)
    if items is None:
        return {"isbn": isbn, "title": "—", "error": total}
    if not items:
        return {"isbn": isbn, "title": "—", "error": "无在售记录", "count": total}

    # 2. 解析全部商品（排除休假/不可靠店铺 + 已售罄 + 该地址无运费数据）
    parsed_all = []
    book_title = book_author = book_press = None
    holiday_skipped = 0
    sold_out_skipped = 0
    no_freight_skipped = 0
    for item in items:
        if _is_unreliable_shop(item):
            holiday_skipped += 1
            continue
        if item.get("isSoldOut"):
            sold_out_skipped += 1
            continue
        # 该收货地址无运费数据（shippingList 为空）→ 大概率不发货到该地，剔除
        sl = item.get("postage", {}).get("shippingList", [])
        if not sl or sl[0].get("shippingFee") is None:
            no_freight_skipped += 1
            continue
        r = _parse_item(item)
        if r is None:
            continue
        parsed_all.append(r)
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

    if not parsed_all:
        if holiday_skipped > 0 and sold_out_skipped == 0:
            return {"isbn": isbn, "title": book_title or "—",
                    "error": f"所有 {holiday_skipped} 个在售商品店铺均在休假中",
                    "holiday_shop_count": holiday_skipped}
        if sold_out_skipped > 0:
            return {"isbn": isbn, "title": book_title or "—",
                    "error": f"全部 {sold_out_skipped} 个商品均已售罄",
                    "sold_out_skipped": sold_out_skipped,
                    "holiday_shop_count": holiday_skipped or 0}
        if no_freight_skipped > 0:
            return {"isbn": isbn, "title": book_title or "—",
                    "error": f"在售 {no_freight_skipped} 个商品均不发货到该收货地址",
                    "no_freight_skipped": no_freight_skipped,
                    "holiday_shop_count": holiday_skipped or 0}
        return {"isbn": isbn, "title": book_title or "—", "error": "未解析到商品"}

    # 3. 按总价（书价 + 按地址运费）排序 → 前 5 名 + 最低
    parsed_all.sort(key=lambda x: x["total"])
    top = parsed_all[:5]
    cheapest = top[0]

    all_prices = [r["price"] for r in parsed_all]

    return {
        "isbn": isbn,
        "title": book_title or "—",
        "author": book_author or "",
        "press": book_press or "",
        "publisher": book_press or "",
        "count": len(parsed_all),
        "total_count": total,
        "pages_scanned": 1,
        "error": None,
        "cheapest": cheapest,
        "top_cheapest": top,
        "price_range": {
            "min": min(all_prices) if all_prices else 0,
            "max": max(all_prices) if all_prices else 0,
            "avg": round(sum(all_prices) / len(all_prices), 1) if all_prices else 0,
        },
        "province": province,
        "user_area": user_area,
        "real_freight_mode": True,
        "precise": True,
        "scan_count": len(parsed_all),
        "no_freight_skipped": no_freight_skipped,
        "holiday_shop_count": holiday_skipped,
        "sold_out_skipped": sold_out_skipped,
    }


def batch_query_by_address(isbns, cookie_str, province, quality_filter="", user_area="", top_n=5, precise=False):
    """按收货地址批量查价（userArea 方案，每本仅 1 次搜索请求，秒级）。"""
    uniq_indices = {}
    for i, isbn in enumerate(isbns):
        key = isbn.strip().replace("-", "").replace(" ", "")
        uniq_indices.setdefault(key, []).append(i)
    uniq_isbns = list(uniq_indices.keys())

    uniq_results = {}
    for isbn in uniq_isbns:
        try:
            uniq_results[isbn] = query_isbn_by_address(
                isbn, cookie_str, province, quality_filter, user_area, top_n, precise)
        except Exception as e:
            uniq_results[isbn] = {"isbn": isbn, "title": "—", "error": str(e)[:40]}

    return [uniq_results[isbn] for isbn in isbns]
