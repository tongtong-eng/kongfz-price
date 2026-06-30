#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子旧书网 · ISBN 查价云服务
============================
启动：python app.py
部署：Railway / Zeabur / Fly.io 等平台
"""
import http.server
import json
import urllib.request
import urllib.parse
import re
import os
import time
import mimetypes
from datetime import datetime
from kongfz_cookie import (
    load_cookie, save_cookie, test_cookie, get_cookie_info,
    verify_current_cookie, extract_from_curl,
    migrate_from_shelve_needed, migrate_from_shelve,
)
import uuid
import posixpath
import io
import pytesseract
from PIL import Image

# ── 配置 ──────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 5000))

# 云部署时，项目根目录为当前文件所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data")

# 确保 data 目录存在（用于持久化 Cookie 和历史记录）
os.makedirs(DATA_DIR, exist_ok=True)

# 覆盖 cookie 模块的存储路径到 data 目录
import kongfz_cookie
kongfz_cookie.STORAGE_FILE = os.path.join(DATA_DIR, ".kongfz_cookies.json")

HTML_FILE = os.path.join(BASE_DIR, "index.html")
HISTORY_FILE = os.path.join(DATA_DIR, "kongfz_history.json")

API_HOST = "https://search.kongfz.com"
API_PATH = "/pc-gw/search-web/client/pc/product/keyword/list"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://search.kongfz.com/product/",
}


# ── 查询逻辑 ───────────────────────────────────────────────

def query_isbn(isbn, cookie_str, quality_filter=""):
    """查询单个 ISBN，返回价格信息"""
    isbn = isbn.strip().replace("-", "").replace(" ", "")
    if not re.match(r'^\d{8,13}$', isbn):
        return {"isbn": isbn, "title": "—", "error": "格式不对"}

    # 第一页获取基本信息
    params_dict = {"keyword": isbn, "page": 1, "size": 30}
    if quality_filter:
        params_dict["quality"] = quality_filter
    params = urllib.parse.urlencode(params_dict)
    url = f"{API_HOST}{API_PATH}?{params}"
    try:
        req = urllib.request.Request(url, headers={**HEADERS, "Cookie": cookie_str})
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"isbn": isbn, "title": "—", "error": str(e)[:30]}

    if data.get("status") != 1:
        msg = data.get("message", "查询失败")
        return {"isbn": isbn, "title": "—", "error": msg}

    payload = data.get("data", {})
    item_resp = payload.get("itemResponse", {})
    total = payload.get("totalFound") or payload.get("totalCount") or 0
    items = item_resp.get("list") or item_resp.get("items") or []
    if not items:
        return {"isbn": isbn, "title": "—", "error": "无在售记录", "count": total}

    title = items[0].get("title", "—")
    author = items[0].get("author", "")
    press = items[0].get("press", "")

    # 翻页扫描找出最低价
    cheap_items = []
    all_prices = []
    total_pages = max(1, (total + 29) // 30)
    max_pages = min(total_pages, 5)

    for page in range(1, max_pages + 1):
        if page > 1:
            p_dict = {"keyword": isbn, "page": page, "size": 30}
            if quality_filter:
                p_dict["quality"] = quality_filter
            params = urllib.parse.urlencode(p_dict)
            url = f"{API_HOST}{API_PATH}?{params}"
            try:
                req = urllib.request.Request(url, headers={**HEADERS, "Cookie": cookie_str})
                resp = urllib.request.urlopen(req, timeout=15)
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("data", {}).get("itemResponse", {}).get("list") or []
            except Exception:
                break

        for item in items:
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

        if page < max_pages:
            time.sleep(0.3)

    if not cheap_items:
        return {"isbn": isbn, "title": title, "error": "未解析到价格", "count": total}

    cheap_items.sort(key=lambda x: x["total"])
    cheapest = cheap_items[0]

    return {
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


def preprocess_image(img):
    """对图片进行预处理，提升 OCR 准确率"""
    from PIL import ImageFilter, ImageOps
    img = img.convert("L")
    img = ImageOps.autocontrast(img, cutoff=5)
    w, h = img.size
    if w < 800 or h < 200:
        scale = max(800 / w, 200 / h, 2)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 0 if x < 180 else 255)
    return img


def ocr_image(file_bytes, filename=""):
    """OCR 识别图片中的文字，提取 ISBN（Tesseract + 预处理优化）"""
    try:
        import pytesseract

        img = Image.open(io.BytesIO(file_bytes))
        img = preprocess_image(img)

        custom_config = r"--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ISBN"
        text = pytesseract.image_to_string(img, lang="chi_sim+eng", config=custom_config)
        if not text.strip():
            custom_config = r"--oem 3 --psm 6 digits"
            text = pytesseract.image_to_string(img, lang="eng", config=custom_config)

        if not text.strip():
            return {"isbns": [], "raw_text": "", "error": "未识别到文字"}

        isbns = set()
        for line in text.split("\n"):
            cleaned = line.strip().replace("-", "").replace(" ", "").replace("　", "").replace("I", "1").replace("S", "5").replace("B", "8").replace("O", "0")
            matches = re.findall(r"\b\d{10,13}\b", cleaned)
            for m in matches:
                if 10 <= len(m) <= 13:
                    isbns.add(m)
        return {
            "isbns": sorted(isbns),
            "raw_text": text.strip()[:500],
            "image_count": 1,
        }
    except Exception as e:
        return {"isbns": [], "raw_text": "", "error": str(e)[:60]}


# ── 历史记录 ───────────────────────────────────────────────

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"records": []}

def save_history(data):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_history_record(name, results, quality_filter=""):
    data = load_history()
    priced = [r for r in results if r.get("cheapest")]
    record_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]
    total_cost = sum(r["cheapest"]["total"] for r in priced if r.get("cheapest"))
    record = {
        "id": record_id,
        "name": name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "isbns": [r["isbn"] for r in results if r.get("isbn")],
        "results": results,
        "book_count": len(results),
        "priced_count": len(priced),
        "total_cost": round(total_cost, 1),
        "quality_filter": quality_filter,
    }
    data["records"].insert(0, record)
    if len(data["records"]) > 100:
        data["records"] = data["records"][:100]
    save_history(data)
    return record_id

def delete_history_record(record_id):
    data = load_history()
    data["records"] = [r for r in data["records"] if r["id"] != record_id]
    save_history(data)


# ── HTTP 处理器 ────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        # 静态文件
        if path.startswith("/static/"):
            self.serve_static(path)
            return

        # API 路由
        if path == "/" or path == "/index.html":
            self.serve_html()
        elif path.startswith("/api/cookie/status"):
            info = get_cookie_info()
            self.send_json(info)
        elif path.startswith("/api/cookie/verify"):
            valid, msg = verify_current_cookie()
            self.send_json({"valid": valid, "message": msg, **get_cookie_info()})
        elif path.startswith("/api/query"):
            cookie = load_cookie()
            if not cookie:
                self.send_json({"error": "Cookie 未找到，请先设置 Cookie"})
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            isbn = q.get("isbn", [""])[0]
            if not isbn:
                self.send_json({"error": "缺少 isbn 参数"})
                return
            quality_filter = q.get("quality", [""])[0]
            result = query_isbn(isbn, cookie, quality_filter)
            self.send_json(result)
        elif path.startswith("/api/addtocart"):
            cookie = load_cookie()
            if not cookie:
                self.send_json({"error": "未登录"})
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            item_id = q.get("itemId", [""])[0]
            shop_id = q.get("shopId", [""])[0]
            if not item_id or not shop_id:
                self.send_json({"error": "缺少参数"})
                return
            cart_url = "https://cart.kongfz.com/jsonp/add"
            cart_params = urllib.parse.urlencode({
                "itemId": item_id, "shopId": shop_id,
                "numbers": "1", "callback": "cb",
            })
            try:
                req = urllib.request.Request(
                    f"{cart_url}?{cart_params}",
                    headers={**HEADERS, "Cookie": cookie},
                )
                resp = urllib.request.urlopen(req, timeout=10)
                body = resp.read().decode("utf-8", errors="replace")
                if body.startswith("cb(") and body.endswith(")"):
                    data = json.loads(body[3:-1])
                    if data.get("status") == 1:
                        self.send_json({"success": True, "cartId": data.get("result", {}).get("cartId")})
                    else:
                        err = data.get("errMessage", "加购失败")
                        self.send_json({"error": err})
                else:
                    self.send_json({"error": "接口返回异常"})
            except Exception as e:
                self.send_json({"error": str(e)[:40]})
        elif path.startswith("/api/history/list"):
            data = load_history()
            summaries = []
            for r in data["records"]:
                summaries.append({
                    "id": r["id"],
                    "name": r["name"],
                    "created_at": r["created_at"],
                    "book_count": r["book_count"],
                    "priced_count": r["priced_count"],
                    "total_cost": r["total_cost"],
                    "quality_filter": r.get("quality_filter", ""),
                })
            self.send_json({"records": summaries})
        elif path.startswith("/api/history/get"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            rid = q.get("id", [""])[0]
            if not rid:
                self.send_json({"error": "缺少 id 参数"})
                return
            data = load_history()
            for r in data["records"]:
                if r["id"] == rid:
                    self.send_json(r)
                    return
            self.send_json({"error": "记录未找到"})
        elif path.startswith("/api/history/delete"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            rid = q.get("id", [""])[0]
            if not rid:
                self.send_json({"error": "缺少 id 参数"})
                return
            delete_history_record(rid)
            self.send_json({"success": True})
        elif path.startswith("/api/"):
            self.send_json({"error": "未知接口"})
        else:
            # 前端路由：SPA 回退到 index.html
            self.serve_html()

    def do_POST(self):
        if self.path.startswith("/api/cookie/update"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json({"error": "请求体为空"})
                return
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                raw = body.get("cookie", "")
                if not raw:
                    self.send_json({"error": "Cookie 不能为空"})
                    return
                cookie = extract_from_curl(raw)
                if not cookie:
                    self.send_json({"error": "无法从输入中提取 Cookie，请检查格式"})
                    return
                save_cookie(cookie)
                valid = test_cookie(cookie)
                if valid:
                    self.send_json({"success": True, **get_cookie_info()})
                else:
                    self.send_json({
                        "success": True,
                        "warning": "Cookie 已保存但验证未通过，请确认已登录",
                        **get_cookie_info(),
                    })
            except json.JSONDecodeError:
                self.send_json({"error": "JSON 解析失败"})
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
        elif self.path.startswith("/api/cookie/extract"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json({"error": "请求体为空"})
                return
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                text = body.get("text", "")
                cookie = extract_from_curl(text)
                if cookie:
                    self.send_json({"success": True, "cookie": cookie, "len": len(cookie)})
                else:
                    self.send_json({"error": "未能提取到 Cookie"})
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
        elif self.path.startswith("/api/history/save"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json({"error": "请求体为空"})
                return
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                name = body.get("name", "")
                results = body.get("results", [])
                quality_filter = body.get("quality_filter", "")
                if not results:
                    self.send_json({"error": "无数据"})
                    return
                if not name:
                    name = f"查询 {datetime.now().strftime('%m-%d %H:%M')}"
                rid = add_history_record(name, results, quality_filter)
                self.send_json({"success": True, "id": rid, "name": name})
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
        elif self.path.startswith("/api/ocr"):
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self.send_json({"error": "需要 multipart/form-data"})
                return
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                boundary = content_type.split("boundary=")[1].strip()
                if boundary.startswith('"') and boundary.endswith('"'):
                    boundary = boundary[1:-1]
                parts = body.split(("--" + boundary).encode())
                for part in parts:
                    if b'name="image"' in part:
                        marker = b"\r\n\r\n"
                        idx = part.find(marker)
                        if idx > 0:
                            img_data = part[idx + len(marker):]
                            img_data = img_data.rstrip(b"\r\n-")
                            if img_data:
                                result = ocr_image(img_data)
                                self.send_json(result)
                                return
                self.send_json({"error": "未找到图片数据"})
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
        else:
            self.send_json({"error": "未知接口"})

    # ── 辅助方法 ─────────────────────────────────────────

    def serve_static(self, path):
        """安全地提供 static/ 目录下的文件"""
        # 防止路径穿越
        rel = path[len("/static/"):]
        rel = rel.split("?")[0].split("#")[0]
        rel = posixpath.normpath(rel)
        if rel.startswith("..") or rel.startswith("/"):
            self.send_response(403)
            self.end_headers()
            return
        filepath = os.path.join(STATIC_DIR, rel)
        if not os.path.isfile(filepath):
            self.send_response(404)
            self.end_headers()
            return

        content_type, _ = mimetypes.guess_type(filepath)
        if content_type is None:
            content_type = "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(filepath, "rb") as f:
            self.wfile.write(f.read())

    def serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if os.path.exists(HTML_FILE):
            with open(HTML_FILE, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.wfile.write(b"<h1>index.html not found</h1>")

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        msg = fmt % args
        if "/api/query" in msg or "error" in msg.lower():
            print(f"  📡 {msg}")


# ── 启动 ───────────────────────────────────────────────────

if __name__ == "__main__":
    # 自动迁移旧 shelve → JSON（如果旧数据存在）
    if migrate_from_shelve_needed():
        print("📦 检测到旧版 shelve Cookie 存储，正在迁移到 JSON...")
        if migrate_from_shelve():
            info = get_cookie_info()
            print(f"  ✅ 迁移完成（Cookie 长度 {info['cookie_len']} 字符）")
        else:
            print("  ⚠️ 迁移失败")

    cookie = load_cookie()
    if not cookie:
        print("⚠️ 未找到 Cookie，启动后请通过页面设置 Cookie")
    else:
        print(f"🍪 Cookie 已加载（{len(cookie)} 字符）")

    try:
        pytesseract.get_tesseract_version()
        print("🔍 Tesseract OCR 可用（预处理优化）")
    except Exception:
        print("⚠️ Tesseract OCR 未安装，图片识别功能不可用")
        print("   brew install tesseract tesseract-lang")

    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"""
╔══════════════════════════════════════════╗
║  📚 孔夫子 ISBN 查价 · 云服务           ║
║                                         ║
║  👉 访问 http://0.0.0.0:{PORT}          ║
║                                         ║
║  ⏹  按 Ctrl+C 停止                      ║
╚══════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()
