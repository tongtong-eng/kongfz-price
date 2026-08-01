#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子旧书网 · ISBN 查价云服务 (v3 优化版)
============================
优化内容：
  ✅ /api/health 健康检查端点（Railway 原生支持）
  ✅ JSON 响应 Gzip 压缩（减少带宽 5-10x）
  ✅ sortType=3 单页查价（从多页扫描 150 条降到 50 条）
  ✅ 线程级 HTTP 连接池复用（减少 TLS 握手开销）
  ✅ 启动加速（地址清理改为后台）
  ✅ Docker 镜像瘦身（.dockerignore + 单层构建）
"""
import http.server
import json
import urllib.request
import urllib.parse
import re
import os
import sys
import time
import io
import gzip
import mimetypes
import socketserver
import threading
from datetime import datetime

# ── 配置（前置：用于 import 路径） ──────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
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
from kongfz_order import search_by_phone

# ── 配置 ──────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 5000))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 确保 data 目录存在（用于持久化 Cookie 和历史记录）
os.makedirs(DATA_DIR, exist_ok=True)

# Cookie 存到 data/ 目录（Railway/Zeabur 持久卷，重启不丢失）
import kongfz_cookie
COOKIE_FILE = os.path.join(DATA_DIR, ".kongfz_cookies.json")
kongfz_cookie.STORAGE_FILE = COOKIE_FILE

# 首次部署：从环境变量读取 Cookie
_kfz_cookie_env = os.environ.get("KONGFZ_COOKIE", "").strip()
if _kfz_cookie_env:
    if not os.path.exists(COOKIE_FILE) or not kongfz_cookie.test_cookie(_kfz_cookie_env):
        kongfz_cookie.save_cookie(_kfz_cookie_env, verified=True)
    try:
        del os.environ["KONGFZ_COOKIE"]
    except KeyError:
        pass

HTML_FILE = os.path.join(BASE_DIR, "index.html")
HISTORY_FILE = os.path.join(DATA_DIR, "kongfz_history.json")
# ── Gzip 压缩 ────────────────────────────────────────────
_GZIP_THRESHOLD = 1024  # 超过 1KB 的响应自动 Gzip

def _gzip_encode(data_json):
    """将 JSON 数据 Gzip 压缩，返回压缩后的 bytes"""
    raw = json.dumps(data_json, ensure_ascii=False).encode("utf-8")
    if len(raw) < _GZIP_THRESHOLD:
        return raw, False
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as f:
        f.write(raw)
    return buf.getvalue(), True


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

    # 禁止 BaseHTTPRequestHandler 打印每个请求到 stderr
    def log_message(self, fmt, *args):
        msg = fmt % args
        # 只打印 API 查询类请求，忽略静默轮询（健康检查、CSS/JS）
        if "/api/query" in msg or "/api/batch" in msg:
            print(f"  📡 {msg}")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        # 静态文件
        if path.startswith("/static/"):
            self.serve_static(path)
            return

        # API 路由
        if path == "/" or path == "/index.html":
            self.serve_html()
        elif path == "/api/health":
            # 健康检查：最快路径，无 Cookie 验证，无数据库查询
            self.send_json({"status": "ok", "time": datetime.now().isoformat()})
        elif path.startswith("/api/cookie/status"):
            self.send_json(get_cookie_info())
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
        elif path.startswith("/api/batch_query_stream"):
            self._do_batch_query_stream()
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
            # sortType=3 价格升序 + quality_filter 品相过滤
            results = batch_query(isbns, cookie, quality_filter, max_concurrent=20)
            self.send_json({"results": results, "count": len(results)})
        elif path.startswith("/api/clearcart"):
            cookie = load_cookie()
            if not cookie:
                self.send_json({"error": "未登录"})
                return
            cart_url = "https://cart.kongfz.com/jsonp/listcart"
            cart_params = urllib.parse.urlencode({"callback": "cb", "_": int(time.time())})
            try:
                req = urllib.request.Request(
                    f"{cart_url}?{cart_params}",
                    headers={**HEADERS, "Cookie": cookie},
                )
                resp = urllib.request.urlopen(req, timeout=10)
                body = resp.read().decode("utf-8", errors="replace")
                if body.startswith("cb(") and body.endswith(")"):
                    data = json.loads(body[3:-1])
                    if data.get("status") != 1:
                        self.send_json({"error": data.get("result", {}).get("errMessage", "获取购物车失败")})
                        return
                    items = data.get("result", {}).get("data", [])
                    if not items:
                        self.send_json({"success": True, "deleted": 0, "total": 0, "message": "购物车已空"})
                        return
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    total = len(items)
                    deleted = [0]
                    failed = []
                    def del_one(it):
                        cart_id = it.get("cartId") or it.get("id")
                        item_id = it.get("itemId")
                        item_name = (it.get("itemName") or "")[:30]
                        del_url = "https://cart.kongfz.com/jsonp/delCartItem?callback=cb&" + \
                            urllib.parse.urlencode({
                                f"carts[0][cartId]": cart_id,
                                f"carts[0][itemId]": item_id,
                            })
                        try:
                            dreq = urllib.request.Request(del_url, headers={**HEADERS, "Cookie": cookie})
                            dresp = urllib.request.urlopen(dreq, timeout=10)
                            dbody = dresp.read().decode("utf-8", errors="replace")
                            if dbody.startswith("cb(") and dbody.endswith(")"):
                                ddata = json.loads(dbody[3:-1])
                                if ddata.get("status") == 1:
                                    deleted[0] += 1
                                    return True
                            failed.append(item_name or str(cart_id))
                            return False
                        except Exception:
                            failed.append(item_name or str(cart_id))
                            return False
                    with ThreadPoolExecutor(max_workers=min(total, 8)) as ex:
                        futs = [ex.submit(del_one, it) for it in items]
                        for f in as_completed(futs):
                            f.result()
                    self.send_json({
                        "success": True,
                        "deleted": deleted[0],
                        "total": total,
                        "failed": failed[:10],
                        "message": f"已清空 {deleted[0]}/{total} 件" + (f"，{len(failed)} 件失败" if failed else ""),
                    })
                else:
                    self.send_json({"error": "购物车接口返回异常"})
            except Exception as e:
                self.send_json({"error": str(e)[:60]})
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
                        self.send_json({"error": data.get("errMessage", "加购失败")})
                else:
                    self.send_json({"error": "接口返回异常"})
            except Exception as e:
                self.send_json({"error": str(e)[:40]})
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
        elif path.startswith("/api/order/search"):
            cookie = load_cookie()
            if not cookie:
                self.send_json({"error": "Cookie 未找到，请先设置 Cookie"})
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            phone = q.get("phone", [""])[0].strip()
            if not phone or not re.match(r'^1\d{10}$', phone):
                self.send_json({"error": "请输入有效的11位手机号"})
                return
            page = int(q.get("page", ["1"])[0])
            result = search_by_phone(cookie, phone, page=page)
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
            # SPA 回退到 index.html
            self.serve_html()

    def do_POST(self):
        if self.path.startswith("/api/cookie/update"):
            body = self._read_json()
            if body is None:
                return
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
        elif self.path.startswith("/api/cookie/extract"):
            body = self._read_json()
            if body is None:
                return
            text = body.get("text", "")
            cookie = extract_from_curl(text)
            if cookie:
                self.send_json({"success": True, "cookie": cookie, "len": len(cookie)})
            else:
                self.send_json({"error": "未能提取到 Cookie"})
        elif self.path.startswith("/api/history/save"):
            body = self._read_json()
            if body is None:
                return
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
        else:
            self.send_json({"error": "未知接口"})

    # ── 辅助方法 ─────────────────────────────────────────

    def _read_json(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self.send_json({"error": "请求体为空"})
            return None
        try:
            return json.loads(self.rfile.read(content_len).decode("utf-8"))
        except json.JSONDecodeError:
            self.send_json({"error": "JSON 解析失败"})
            return None
        except Exception as e:
            self.send_json({"error": str(e)[:60]})
            return None

    def serve_static(self, path):
        """安全地提供 static/ 目录下的文件"""
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
        """发送 JSON 响应，超过 1KB 自动 Gzip 压缩"""
        body, compressed = _gzip_encode(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        if compressed:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _do_batch_query_stream(self):
        """SSE 流式查询，每查完一本推送进度"""
        cookie = load_cookie()
        if not cookie:
            self.send_json({"error": "Cookie 未找到"})
            return
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        isbns_raw = q.get("isbns", [""])[0]
        if not isbns_raw:
            self.send_json({"error": "缺少 isbns 参数"})
            return
        isbns = [s.strip().replace("-", "") for s in isbns_raw.split(",") if s.strip().isdigit()]
        if not isbns:
            self.send_json({"error": "无有效 ISBN"})
            return
        quality_filter = q.get("quality", [""])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        from kongfz_query import query_isbn as _qisbn
        from concurrent.futures import ThreadPoolExecutor, as_completed

        batch_id = str(int(time.time()))
        results = [None] * len(isbns)
        done_count = [0]

        with ThreadPoolExecutor(max_workers=min(len(isbns), 10)) as ex:
            fut_map = {}
            for i, isbn in enumerate(isbns):
                fut = ex.submit(_qisbn, isbn, cookie, quality_filter)
                fut_map[fut] = (i, isbn)

            for f in as_completed(fut_map):
                i, isbn = fut_map[f]
                try:
                    r = f.result()
                except Exception as e:
                    r = {"isbn": isbn, "title": "—", "error": str(e)[:40]}
                r["_batchId"] = batch_id
                results[i] = r
                done_count[0] += 1

                progress = {
                    "current": done_count[0],
                    "total": len(isbns),
                    "isbn": isbn,
                    "ok": r.get("error") is None,
                    "title": (r.get("title") or "")[:30] if r.get("error") is None else "",
                    "error": r.get("error") or "",
                }
                try:
                    msg = f"event: progress\ndata: {json.dumps(progress, ensure_ascii=False)}\n\n"
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    break

        try:
            summary = {"batchId": batch_id, "results": results, "count": len(results)}
            msg = f"event: complete\ndata: {json.dumps(summary, ensure_ascii=False)}\n\n"
            self.wfile.write(msg.encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    def _do_self_check(self):
        import subprocess, hashlib
        from datetime import datetime
        result = {}

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

        files = ["app.py", "index.html", "kongfz_query.py", "kongfz_cookie.py"]
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

        cookie = load_cookie()
        info = get_cookie_info()
        result["cookie"] = {
            "has": bool(cookie),
            "valid": info.get("is_valid", False),
            "len": len(cookie) if cookie else 0,
        }

        try:
            from kongfz_query import query_isbn_simple
            r = query_isbn_simple("9787020002207", cookie)
            result["api_query"] = {
                "ok": r.get("error") is None,
                "detail": f"查到 {r.get('total_count',0)} 本, 最低¥{r.get('min_price','?')}" if r.get("error") is None else r.get("error"),
            }
        except Exception as e:
            result["api_query"] = {"ok": False, "detail": str(e)[:40]}

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


# ── 后台任务 ────────────────────────────────────────────────

def _background_addr_cleanup():
    """后台静默清理收货地址（启动时不阻塞）"""
    cookie = load_cookie()
    if not cookie:
        return
    try:
        result = cleanup_addresses(cookie)
        if result.get("deleted", 0) > 0:
            print(f"  🧹 地址清理：删除了 {result['deleted']} 个旧地址")
        elif result.get("success") is False:
            pass  # Cookie 未登录地址管理，静默忽略
    except Exception:
        pass


# ── 启动 ───────────────────────────────────────────────────

if __name__ == "__main__":
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
        # 地址清理改为后台执行，不阻塞启动
        t = threading.Thread(target=_background_addr_cleanup, daemon=True)
        t.start()

    print("  📡 健康检查端点: /api/health")
    print("  💨 Gzip 压缩: 已启用（>1KB 自动压缩）")
    print("  ⚡ sortType=3 单页查价 + HTTP 连接池复用")

    # 多线程服务器
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    server.max_children = 16
    print(f"""
╔══════════════════════════════════════════╗
║  📚 孔夫子 ISBN 查价 · 云服务 v3        ║
║                                         ║
║  👉 本机：   http://localhost:{PORT}     ║
║                                         ║
║  ⏹  按 Ctrl+C 停止                      ║
╚══════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()
