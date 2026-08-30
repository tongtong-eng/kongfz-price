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
    body = {"mobilePhone": phone, "page": page, "pageSize": page_size, "size": page_size}
    data = _call_api(cookie_str, body)

    if not data.get("status"):
        return {"error": data.get("errMessage", "查询失败"), "orders": [], "total": 0}

    raw_orders = data.get("result", {}).get("list", [])
    pager = data.get("result", {}).get("pager") or {}
    total = pager.get("total") or len(raw_orders)

    orders = []
    for o in raw_orders:
        items = o.get("items", [])
        order = {
            "order_id": o.get("orderId"),
            "shop_name": o.get("shopName", ""),
            "status": o.get("orderStatusName", o.get("orderStatus", "")),
            "order_status": o.get("orderStatus", ""),
            "receiver_name": o.get("receiverName", ""),
            "mobile": o.get("phoneNum", ""),
            "address": (o.get("provName") or "") + (o.get("cityName") or "") + (o.get("areaName") or "") + (o.get("address") or ""),
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
                    "number": i.get("number", 1) or 1,  # 本数（可能>1）
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


# 异常订单监控：自动翻页拉全量订单，识别"卖家取消"和"延迟发货"
CANCEL_STATUSES = ("SellerClosedBeforePay", "Canceled", "Closed", "PaidRefunded")
DELAY_THRESHOLD_SECONDS = 3 * 24 * 3600  # 超过3天未发货视为延迟


def _get_cancel_by(o):
    """判断取消订单的来源：seller=商家取消，buyer=买家(你)取消，other=其他。
    优先看 refundInfo.actionUserType；状态为 BuyerCancelledBeforePay 明确是买家取消。
    """
    status = o.get("orderStatus", "") or ""
    # 状态明确标买家取消
    if status == "BuyerCancelledBeforePay":
        return "buyer"
    ri = o.get("refundInfo") or {}
    action_type = ri.get("actionUserType") or ""
    if action_type == "seller":
        return "seller"
    if action_type == "buyer":
        return "buyer"
    if action_type == "sys":
        return "system"
    # 无法判断
    return "other"


def monitor_orders(cookie_str, delay_days=3, max_pages=88, page_size=50, lookback_months=2):
    """
    翻页拉取订单，识别异常：
      - 已取消：orderStatus 命中取消状态（卖家取消/退款完成）
      - 延迟发货：处于"等待卖家发货"且下单超过 delay_days 天

    只扫描最近 lookback_months 个月的订单（默认2个月），超过即停止翻页，
    避免全盘扫描 4400+ 单导致速度慢。订单API按时间倒序（最新在前）。

    返回：
      {
        "scanned": 扫描订单总数,
        "cancelled": [取消订单列表],
        "delayed":   [延迟发货订单列表],
        "ok_count": 正常订单数,
        "error":     出错信息(可选)
      }
    """
    from datetime import datetime
    cancel = []
    delayed = []
    scanned = 0
    # 2个月前的边界时间戳（本地时区）
    cutoff = time.time() - lookback_months * 30 * 24 * 3600
    _exceeded = False
    try:
        for page in range(1, max_pages + 1):
            body = {"page": page, "size": page_size, "mobilePhone": ""}
            data = _call_api(cookie_str, body)
            if not data.get("status"):
                return {"error": data.get("errMessage", "查询失败"), "scanned": scanned,
                        "cancelled": cancel, "delayed": delayed}
            raw = data.get("result", {}).get("list", [])
            if not raw:
                break  # 拉完了
            for o in raw:
                # 超过2个月：订单时间早于cutoff，停止翻页（订单按时间倒序）
                ct_raw = o.get("createdTime", 0)
                if ct_raw:
                    try:
                        ct_check = float(ct_raw)
                        if ct_check > 1e12:
                            ct_check = ct_check / 1000.0
                        if ct_check < cutoff:
                            _exceeded = True
                            break
                    except (TypeError, ValueError):
                        pass
                scanned += 1
                status = o.get("orderStatus", "") or ""
                status_name = o.get("orderStatusName", "") or ""
                order = {
                    "order_id": o.get("orderId"),
                    "shop_name": o.get("shopName", ""),
                    "status": status_name,
                    "order_status": status,
                    "receiver_name": o.get("receiverName", ""),
                    "created_time": o.get("createdTime", 0),
                    "amount": o.get("paidOrderAmount", ""),
                    "items": [
                        {"name": i.get("itemName", ""), "isbn": i.get("isbn") or i.get("itemSn", "")}
                        for i in o.get("items", [])
                    ],
                    # 取消来源：seller=商家取消，buyer=买家(你)取消，sys/other=系统或其他
                    "cancel_by": _get_cancel_by(o),
                }
                # 取消订单：状态命中取消集合 或 状态名含"取消/退款完成"
                if status in CANCEL_STATUSES or "取消" in status_name or "退款完成" in status_name:
                    cancel.append(order)
                    continue
                # 延迟发货：等待卖家发货 且 超时
                if status in ("PaidToShip",) or "等待卖家发货" in status_name:
                    ct = o.get("createdTime", 0)
                    if ct:
                        try:
                            ct_f = float(ct)
                            if ct_f > 1e12:  # 毫秒转秒
                                ct_f = ct_f / 1000.0
                            elapsed = time.time() - ct_f
                            if elapsed > delay_days * 24 * 3600:
                                order["delay_days"] = round(elapsed / 86400, 1)
                                delayed.append(order)
                        except (TypeError, ValueError):
                            pass
            # 到最后一页就停
            pager = data.get("result", {}).get("pager", {})
            if page >= (pager.get("pages") or max_pages):
                break
            # 已遇到超过2个月的订单（当前页最旧已到2个月前），停止翻页
            if _exceeded:
                break
    except Exception as e:
        return {"error": str(e)[:60], "scanned": scanned, "cancelled": cancel, "delayed": delayed}

    return {"scanned": scanned, "cancelled": cancel, "delayed": delayed,
            "ok_count": scanned - len(cancel) - len(delayed)}
