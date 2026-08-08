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
_RATE = {"consecutive_fails": 0, "max_workers": 3}

def _get_max_workers():
    """根据失败率动态调整批量并发数：
       0 次失败 → 默认并发 3（配合全局 600ms 节流，出站仍 1.67 次/秒，与已验证稳定的频率一致）
       1~2 次失败 → 降到 2
       ≥3 次失败 → 降到 1（完全串行，最稳）
       每次成功会递减失败计数，自动逐步恢复并发。"""
    fails = _RATE["consecutive_fails"]
    if fails >= 3:
        return 1
    elif fails >= 1:
        return 2
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

def _query_api(isbn, cookie_str, quality_filter=""):
    """
    执行 API 请求：sortType=5 总价升序，仅第 1 页。
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

# 运费模板缓存：shopId → (mould_id, 模板费率, 时间戳)
_FREIGHT_CACHE = {}
_FREIGHT_TTL = 3600  # 1 小时

# 运费接口专用 HTTP 连接（独立，避免与搜索连接池混淆）
_FREIGHT_CONN = threading.local()

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


def _get_freight_conn():
    """运费接口的连接（复用线程本地连接）"""
    c = getattr(_FREIGHT_CONN, 'conn', None)
    if c is None:
        c = http.client.HTTPSConnection("book.kongfz.com", timeout=15,
                                        context=ssl.create_default_context())
        _FREIGHT_CONN.conn = c
    return c


def get_shop_freight_mould(cookie_str, item):
    """获取单个商品的运费模板（按 shopId 缓存）。

    搜索 API 不返回 mouldId，需要额外抓商品详情页提取，
    再调 getFreightInfo 拿运费模板。

    返回 mould dict 或 None。
    """
    shop_id = item.get("shopId")
    item_id = item.get("itemId")
    mould_id = item.get("mouldId")

    # 1. 尝试从缓存取（按 shopId，同店复用）
    if shop_id:
        cached = _FREIGHT_CACHE.get(f"s{shop_id}")
        if cached and time.time() - cached[2] < _FREIGHT_TTL:
            return cached[0]

    # 2. 没有 mouldId → 抓详情页提取
    if not mould_id and item_id and shop_id:
        try:
            _throttle()
            conn = _get_freight_conn()
            dpath = f"/{shop_id}/{item_id}/"
            conn.request("GET", dpath, headers={**HEADERS, "Cookie": cookie_str,
                                                "Referer": "https://book.kongfz.com/{shop_id}/{item_id}/"})
            dresp = conn.getresponse()
            dbody = dresp.read().decode("utf-8", errors="replace")
            m = re.search(r'mouldId["\']?\s*[:=]\s*["\']?(\d+)', dbody)
            if m:
                mould_id = m.group(1)
                item["mouldId"] = mould_id
            # 顺带提取 weight
            wm = re.search(r'weight["\']?\s*[:=]\s*["\']?([\d.]+)', dbody)
            if wm and "weight" not in item:
                item["weight"] = wm.group(1)
        except Exception:
            return None

    if not mould_id:
        return None

    # 3. 调 getFreightInfo 拿模板
    try:
        _throttle()
        conn = _get_freight_conn()
        path = f"/Pc/Ajax/getFreightInfo?mouldId={urllib.parse.quote(str(mould_id))}"
        conn.request("GET", path, headers={**HEADERS, "Cookie": cookie_str,
                                           "Referer": "https://book.kongfz.com/"})
        resp = conn.getresponse()
        body = resp.read()
        data = json.loads(body.decode("utf-8"))
        if data.get("status") != 1:
            return None
        mould = data.get("result", {}).get("mouldInfo", {})
        # 按 shopId 缓存
        cache_key = f"s{shop_id}" if shop_id else str(mould_id)
        _FREIGHT_CACHE[cache_key] = (mould, shop_id, time.time())
        # 缓存清理
        if len(_FREIGHT_CACHE) > 2000:
            for k in list(_FREIGHT_CACHE.keys())[:500]:
                del _FREIGHT_CACHE[k]
        return mould
    except Exception:
        return None


def calc_real_freight(cookie_str, item, province):
    """按收货省份计算单个商品的真实运费。

    返回 (真实运费, 是否命中) 或 (None, False)。
    """
    mould = get_shop_freight_mould(cookie_str, item)
    if not mould:
        return None, False
    fee_list = mould.get("feeList") or {}
    express = fee_list.get("express") or {}
    specials = express.get("special") or []

    # 匹配收货省份所在的费率组
    matched = None
    for spec in specials:
        for area in spec.get("area") or []:
            if area.get("provName") == province:
                matched = spec
                break
        if matched:
            break

    if matched is None:
        # 无匹配 → 用默认费率
        default = express.get("default")
        matched = default

    if not matched:
        return None, False

    try:
        initial_fee = float(matched.get("initialFee", 0))
        add_fee = float(matched.get("addFee", 0))
        initial_num = float(matched.get("initialNum", 0)) or 1
    except (TypeError, ValueError):
        return initial_fee, True

    # 书通常 1 件 0.5kg，多数在首重内；超首重按续重计（weight 为 0.5 一般不会）
    weight = item.get("weight") or 0.5
    try:
        weight = float(weight)
    except (TypeError, ValueError):
        weight = 0.5
    weight = max(weight, 0.1)

    total_fee = initial_fee
    if weight > initial_num and add_fee > 0:
        extra = weight - initial_num
        total_fee += add_fee * max(1, int(extra // 0.5) + (1 if extra % 0.5 else 0))
    return round(total_fee, 1), True


def query_isbn_by_address(isbn, cookie_str, province, quality_filter="", top_n=5):
    """
    按收货地址省份查询单本 ISBN 的最低总价。

    流程：
      1. 搜索该 ISBN 的商品（sortType=5 总价升序）
      2. 对总价靠前的 top_n 条商品，调 getFreightInfo 拿真实运费
      3. 重算总价（书价 + 真实运费）→ 按真实总价排序 → 返回最低

    参数：
        isbn:           ISBN
        cookie_str:     Cookie
        province:       收货省份（如"重庆"）
        quality_filter: 品相过滤
        top_n:          只对前 N 条算真实运费（性能优化）

    返回：与 query_isbn 相同结构的 result，额外含 real_freight 字段。
    """
    isbn = isbn.strip().replace("-", "").replace(" ", "")
    if not re.match(r'^\d{10,13}$', isbn):
        return {"isbn": isbn, "title": "—", "error": "格式不对"}

    # 1. 搜索
    items, total = _query_api(isbn, cookie_str, quality_filter)
    if items is None:
        return {"isbn": isbn, "title": "—", "error": total}
    if not items:
        return {"isbn": isbn, "title": "—", "error": "无在售记录", "count": total}

    # 2. 先解析全部商品基本信息
    parsed_all = []
    for item in items:
        if item.get("shopIsHoliday") or item.get("shop30DaysNotLogin"):
            continue
        r = _parse_item(item)
        if r is None:
            continue
        r["_item"] = item  # 保留原始 item 用于取 mouldId/weight
        # 先按搜索接口的运费估一个初始总价，用于排序挑前 top_n
        parsed_all.append(r)

    if not parsed_all:
        return {"isbn": isbn, "title": "—", "error": "未解析到商品"}

    # 3. 按搜索接口的（书价+固定运费）排序，取前 top_n 算真实运费
    parsed_all.sort(key=lambda x: x["total"])
    candidates = parsed_all[:top_n]

    # 4. 对候选商品算真实运费
    for r in candidates:
        real_fee, hit = calc_real_freight(cookie_str, r["_item"], province)
        if hit:
            r["real_freight"] = real_fee
            r["real_total"] = round(r["price"] + real_fee, 1)
            # 重设运费字段为真实值
            r["shipping"] = real_fee
            r["total"] = r["real_total"]
        else:
            r["real_freight"] = r.get("shipping", 0)
            r["real_total"] = r["total"]

    # 5. 按真实总价排序
    candidates.sort(key=lambda x: x["real_total"])
    top = candidates[:5]
    cheapest = top[0]

    # 书名/作者/出版社
    book_title = book_author = book_press = None
    for item in items:
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
        if book_title and book_author and book_press:
            break

    all_prices = [r["price"] for r in parsed_all]

    return {
        "isbn": isbn,
        "title": book_title or "—",
        "author": book_author or "",
        "press": book_press or "",
        "count": len(candidates),
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
        "real_freight_mode": True,
    }


def batch_query_by_address(isbns, cookie_str, province, quality_filter="", top_n=5):
    """按收货地址批量查价（串行，复用节流）。"""
    uniq_indices = {}
    for i, isbn in enumerate(isbns):
        key = isbn.strip().replace("-", "").replace(" ", "")
        uniq_indices.setdefault(key, []).append(i)
    uniq_isbns = list(uniq_indices.keys())

    uniq_results = {}
    for isbn in uniq_isbns:
        try:
            uniq_results[isbn] = query_isbn_by_address(
                isbn, cookie_str, province, quality_filter, top_n)
        except Exception as e:
            uniq_results[isbn] = {"isbn": isbn, "title": "—", "error": str(e)[:40]}

    return [uniq_results[isbn] for isbn in isbns]
