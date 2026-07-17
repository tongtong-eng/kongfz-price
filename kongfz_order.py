"""
kongfz_order.py — 孔夫子订单/快递追踪模块

从 order.kongfz.com 拉取买家订单数据，
支持按手机号搜索订单、快递单号、到货状态。

依赖：
  - kongfz_cookie（获取已保存的 Cookie）
"""
import json
import urllib.request
import urllib.parse
import gzip
import time

# ── 常量 ──────────────────────────────────────
ORDER_HOST = "https://order.kongfz.com"
ORDER_API = "/pc-gw/order-web/pc/v1/buyer/order/list"
ORDER_COUNT_API = "/pc-gw/order-web/pc/v1/buyer/order/count"
HEADERS_TEMPLATE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5.2 Safari/605.1.15",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Origin": "https://order.kongfz.com",
    "Referer": "https://order.kongfz.com/order-views/management/buyer/list",
    "Content-Type": "application/json",
}
TIMEOUT = 20

# 本地缓存（减少重复请求）
_CACHE = {}
_CACHE_TTL = 120  # 2 分钟

def _get_headers(cookie_str):
    """组装完整请求头"""
    return {**HEADERS_TEMPLATE, "Cookie": cookie_str}

def _call_api(cookie_str, body):
    """调用孔夫子订单列表 API，返回 JSON"""
    url = ORDER_HOST + ORDER_API
    data_bytes = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=_get_headers(cookie_str), method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        raw = resp.read()
        if "gzip" in resp.headers.get("Content-Encoding", ""):
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return {"status": False, "errMessage": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"status": False, "errMessage": str(e)[:80]}


def search_by_phone(cookie_str, phone, page=1, page_size=50):
    """
    按手机号搜索订单。

    参数：
        cookie_str: 登录 Cookie
        phone:      手机号
        page:       页码（从1开始）
        page_size:  每页条数

    返回：
        {
            "orders": [ 每条订单简化后的关键字段 ],
            "total": N,
            "page": page,
            "page_size": page_size,
        }
    """
    body = {"mobile": phone, "page": page, "pageSize": page_size}
    data = _call_api(cookie_str, body)

    if not data.get("status"):
        return {"error": data.get("errMessage", "查询失败"), "orders": [], "total": 0}

    raw_orders = data.get("result", {}).get("list", [])
    total = data.get("result", {}).get("totalCount") or len(raw_orders)

    orders = []
    for o in raw_orders:
        items = o.get("items", [])
        order = {
            "order_id": o.get("orderId"),
            "shop_name": o.get("shopName", ""),
            "status": o.get("orderStatusName", o.get("orderStatus", "")),
            "order_status": o.get("orderStatus", ""),
            "receiver_name": o.get("receiverName", ""),
            "mobile": o.get("mobile", ""),
            "address": o.get("provName", "") + o.get("cityName", "") + o.get("areaName", "") + o.get("address", ""),
            "shipping_company": o.get("shippingCom", ""),
            "shipment_num": o.get("shipmentNum", ""),
            "shipping_status": o.get("shippingStatus", ""),
            "created_time": o.get("createdTime", 0),
            "paid_amount": o.get("paidOrderAmount", "0"),
            "items": [
                {
                    "name": i.get("itemName", ""),
                    "isbn": i.get("isbn", "") or i.get("itemSn", ""),
                    "price": i.get("price", "0"),
                    "quality": i.get("quality", ""),
                }
                for i in items
            ],
            "logistic": o.get("logistic", []),
        }
        # 如果有物流列表但没精简 logistic，用 logistic
        if not order["logistic"] and o.get("logisticList"):
            order["logistic"] = [
                {"ftime": "", "context": f"{l.get('companyName','')} {l.get('num','')}", "time": "", "status": "", "code": 0, "location": ""}
                for l in o.get("logisticList", [])
            ]
        orders.append(order)

    return {"orders": orders, "total": total, "page": page, "page_size": page_size}


def get_order_count(cookie_str):
    """获取订单总数"""
    data = _call_api(cookie_str, {"withDelete": False})
    if data.get("status"):
        return data.get("result", {})
    return {}
