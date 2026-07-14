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
import sys
import mimetypes
import io
import socketserver
from datetime import datetime

# ── 配置（前置：用于 import 路径） ──────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
# 共享模块在父目录（kongfz_query.py, kongfz_inventory.py 等）
_PARENT = os.path.dirname(BASE_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from kongfz_cookie import (
    load_cookie, save_cookie, test_cookie, get_cookie_info,
    verify_current_cookie, extract_from_curl,
    migrate_from_shelve_needed, migrate_from_shelve,
)
from kongfz_query import query_isbn, batch_query, HEADERS
from kongfz_address import cleanup_addresses, MAX_ADDRESSES
from kongfz_inventory import (
    load_inventory, add_item, sell_item, update_sale_price,
    delete_item, get_stats,
)

# ── 配置 ──────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 5000))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 确保 data 目录存在（用于持久化 Cookie 和历史记录）
os.makedirs(DATA_DIR, exist_ok=True)

# 覆盖 cookie 模块的存储路径（优先用根目录，Git 可追踪）
import kongfz_cookie
COOKIE_FILE = os.path.join(BASE_DIR, ".kongfz_cookies.json")
# 如果根目录没有 cookie 文件，尝试 data 目录（Zeabur 持久卷迁移）
if not os.path.exists(COOKIE_FILE):
    legacy = os.path.join(DATA_DIR, ".kongfz_cookies.json")
    if os.path.exists(legacy):
        import shutil
        shutil.copy2(legacy, COOKIE_FILE)
kongfz_cookie.STORAGE_FILE = COOKIE_FILE

HTML_FILE = os.path.join(BASE_DIR, "index.html")
HISTORY_FILE = os.path.join(DATA_DIR, "kongfz_history.json")
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")


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
    """OCR 识别图片中的文字，提取 ISBN（Tesseract，懒加载）"""
    try:
        import pytesseract
        from PIL import Image

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
            # 先试纯数字提取（Vision 识别准确的场景）
            digits = re.sub(r"[^0-9]", "", line.strip())
            if 10 <= len(digits) <= 13:
                isbns.add(digits)
            # 再试带字符替换的（Tesseract 易混淆场景）
            alt = line.strip().replace("-", "").replace(" ", "").replace("　", "")
            alt = alt.replace("I", "1").replace("S", "5").replace("B", "8").replace("O", "0").replace("l", "1")
            alt_digits = re.sub(r"[^0-9]", "", alt)
            if 10 <= len(alt_digits) <= 13:
                isbns.add(alt_digits)
        return {"isbns": sorted(isbns), "raw_text": text.strip()[:500], "image_count": 1}
    except ImportError:
        return {"isbns": [], "raw_text": "", "error": "缺少 Tesseract"}
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
    record_id = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        elif path.startswith("/api/batch_query"):
            cookie = load_cookie()
            if not cookie:
                self.send_json({"error": "Cookie 未找到，请先设置 Cookie"})
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            isbns_raw = q.get("isbns", [""])[0]
            if not isbns_raw:
                self.send_json({"error": "缺少 isbns 参数（逗号分隔）"})
                return
            isbns = [s.strip().replace("-", "") for s in isbns_raw.split(",") if s.strip().isdigit()]
            if not isbns:
                self.send_json({"error": "无有效 ISBN"})
                return
            quality_filter = q.get("quality", [""])[0]
            # 有品相过滤时用完整模式（fast_mode 不支持 quality_filter）
            fast = not bool(quality_filter)
            results = batch_query(isbns, cookie, quality_filter, max_concurrent=20, fast_mode=fast)
            self.send_json({"results": results, "count": len(results)})
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
        elif path.startswith("/api/inventory/list"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            items = load_inventory(INVENTORY_FILE).get("items", [])
            # 按 status 筛选
            status = q.get("status", [""])[0]
            if status == "in_stock":
                items = [i for i in items if i.get("status") == "in_stock"]
            elif status == "sold":
                items = [i for i in items if i.get("status") == "sold"]
            # 按书名/ISBN 搜索
            search = q.get("q", [""])[0].strip()
            if search:
                search_lower = search.lower()
                items = [i for i in items
                         if search_lower in i.get("title", "").lower()
                         or search in str(i.get("isbn", ""))]
            # 按月份筛选
            month = q.get("month", [""])[0].strip()
            if month:
                items = [i for i in items if i.get("created_at", "").startswith(month)]
            self.send_json({"items": items, "total": len(items)})
        elif path.startswith("/api/inventory/stats"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            period = q.get("period", [""])[0] or None
            items = load_inventory(INVENTORY_FILE).get("items", [])
            stats = get_stats(items, period)
            self.send_json(stats)
        elif path.startswith("/api/address/cleanup"):
            cookie = load_cookie()
            if not cookie:
                self.send_json({"error": "Cookie 未找到"})
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            dry_run = q.get("dry_run", [""])[0] in ("1", "true", "yes")
            max_count = int(q.get("max", [MAX_ADDRESSES])[0])
            result = cleanup_addresses(cookie, max_count=max_count, dry_run=dry_run)
            self.send_json(result)
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
        elif path.startswith("/api/self_check"):
            self._do_self_check()
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
        elif self.path.startswith("/api/inventory/add"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json({"error": "请求体为空"})
                return
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                item = add_item(
                    isbn=body.get("isbn", ""),
                    title=body.get("title", ""),
                    author=body.get("author", ""),
                    cost_price=body.get("cost_price", 0),
                    shipping=body.get("shipping", 0),
                    source_batch=body.get("source_batch", ""),
                    storage_path=INVENTORY_FILE,
                )
                self.send_json({"success": True, "item": item})
            except json.JSONDecodeError:
                self.send_json({"error": "JSON 解析失败"})
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
        elif self.path.startswith("/api/inventory/sell"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json({"error": "请求体为空"})
                return
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                success = sell_item(
                    item_id=body["id"],
                    sale_price=body["sale_price"],
                    storage_path=INVENTORY_FILE,
                )
                self.send_json({"success": success})
            except KeyError:
                self.send_json({"error": "缺少必要参数 id 或 sale_price"})
            except json.JSONDecodeError:
                self.send_json({"error": "JSON 解析失败"})
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
        elif self.path.startswith("/api/inventory/update_sale_price"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json({"error": "请求体为空"})
                return
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                success = update_sale_price(
                    item_id=body["id"],
                    sale_price=body["sale_price"],
                    storage_path=INVENTORY_FILE,
                )
                self.send_json({"success": success})
            except KeyError:
                self.send_json({"error": "缺少必要参数 id 或 sale_price"})
            except json.JSONDecodeError:
                self.send_json({"error": "JSON 解析失败"})
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
        elif self.path.startswith("/api/inventory/delete"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json({"error": "请求体为空"})
                return
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
                success = delete_item(
                    item_id=body["id"],
                    storage_path=INVENTORY_FILE,
                )
                self.send_json({"success": success})
            except KeyError:
                self.send_json({"error": "缺少必要参数 id"})
            except json.JSONDecodeError:
                self.send_json({"error": "JSON 解析失败"})
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
        rel = os.path.normpath(rel)
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

    def _do_self_check(self):
        import subprocess, hashlib
        from datetime import datetime
        result = {}

        # Git 版本
        try:
            out = subprocess.run(["git", "log", "--oneline", "-1"],
                                 capture_output=True, text=True, cwd=BASE_DIR, timeout=5)
            result["git_commit"] = out.stdout.strip() or "无"
            out2 = subprocess.run(["git", "status", "--short"],
                                  capture_output=True, text=True, cwd=BASE_DIR, timeout=5)
            dirty = [l for l in out2.stdout.strip().split("\n") if l.strip()]
            result["git_dirty"] = dirty if dirty else []
            out3 = subprocess.run(["git", "log", "--oneline", "origin/main", "-1"],
                                  capture_output=True, text=True, cwd=BASE_DIR, timeout=5)
            result["git_remote"] = out3.stdout.strip() or "无"
        except Exception:
            result["git_commit"] = "非 Git 目录"
            result["git_dirty"] = []
            result["git_remote"] = "未知"

        # 关键文件
        files = ["app.py", "index.html", "kongfz_query.py", "kongfz_cookie.py", "kongfz_inventory.py"]
        file_info = {}
        for fn in files:
            fp = os.path.join(BASE_DIR, fn)
            if os.path.exists(fp):
                s = os.stat(fp)
                with open(fp, "rb") as f:
                    h = hashlib.md5(f.read(65536)).hexdigest()[:8]
                file_info[fn] = {
                    "mtime": datetime.fromtimestamp(s.st_mtime).strftime("%m-%d %H:%M"),
                    "hash": h,
                    "size": s.st_size,
                }
            else:
                file_info[fn] = {"error": "不存在"}
        result["files"] = file_info

        # Cookie
        cookie = load_cookie()
        info = get_cookie_info()
        result["cookie"] = {
            "has": bool(cookie),
            "valid": info.get("is_valid", False),
            "len": len(cookie) if cookie else 0,
        }

        # API 查价测试
        try:
            from kongfz_query import query_isbn_simple
            r = query_isbn_simple("9787020002207", cookie)
            result["api_query"] = {
                "ok": r.get("error") is None,
                "detail": f"查到 {r.get('total_count',0)} 本, 最低¥{r.get('min_price','?')}" if r.get("error") is None else r.get("error"),
            }
        except Exception as e:
            result["api_query"] = {"ok": False, "detail": str(e)[:40]}

        # API 加购测试
        if cookie:
            from kongfz_query import query_isbn
            try:
                r2 = query_isbn("9787020002207", cookie)
                c = r2.get("cheapest", {})
                if c.get("itemId") and c.get("shopId"):
                    import urllib.request, urllib.parse
                    cart_url = "https://cart.kongfz.com/jsonp/add"
                    cp = urllib.parse.urlencode({"itemId": c["itemId"], "shopId": c["shopId"], "numbers": "1", "callback": "cb"})
                    req = urllib.request.Request(f"{cart_url}?{cp}", headers={**HEADERS, "Cookie": cookie})
                    resp = urllib.request.urlopen(req, timeout=10)
                    body = resp.read().decode("utf-8", errors="replace")
                    if body.startswith("cb(") and body.endswith(")"):
                        dd = json.loads(body[3:-1])
                        result["api_addtocart"] = {"ok": dd.get("status") == 1, "detail": dd.get("errMessage", "成功")}
                    else:
                        result["api_addtocart"] = {"ok": False, "detail": "接口返回异常"}
                else:
                    result["api_addtocart"] = {"ok": False, "detail": "查价未返回商品ID"}
            except Exception as e:
                result["api_addtocart"] = {"ok": False, "detail": str(e)[:40]}
        else:
            result["api_addtocart"] = {"ok": False, "detail": "无 Cookie"}

        result["time"] = datetime.now().strftime("%m-%d %H:%M:%S")
        self.send_json(result)

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
        # 自动清理收货地址
        try:
            result = cleanup_addresses(cookie)
            if result.get("deleted", 0) > 0:
                print(f"  🧹 收货地址自动清理：删除了 {result['deleted']} 个旧地址，保留 {result['kept']} 个")
            elif result.get("to_delete"):
                print(f"  🧹 收货地址检查：{result['message']}")
            elif result.get("success") is False:
                print(f"  ⚠️ 地址清理：{result.get('error', 'Cookie 未登录地址管理')}")
        except Exception as e:
            print(f"  ⚠️ 地址清理出错: {e}")

    try:
        import subprocess
        subprocess.run(["tesseract", "--version"], capture_output=True, timeout=3)
        print("🔍 Tesseract OCR 可用（图片识别功能已开启）")
    except Exception:
        print("ℹ️ Tesseract 未安装，图片识别功能不可用")

    # 多线程服务器：并发请求同时处理（查价不再排队）
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    server.max_children = 16  # 最大线程数
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
