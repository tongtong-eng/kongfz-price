#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子查价服务 · Cookie 共享管理模块
====================================

为 CLI（kongfz_price.py）和 Web（kongfz_web.py）提供统一的 Cookie 管理。
"""

import json
import os
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
import shelve

# ============================================================
#  常量配置
# ============================================================

STORAGE_FILE = os.path.expanduser("~/.kongfz_cookies.json")

API_HOST = "https://search.kongfz.com"
API_PATH = "/pc-gw/search-web/client/pc/product/keyword/list"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://search.kongfz.com/product/",
    "Origin": "https://search.kongfz.com",
}

TIMEOUT = 20

# 旧版 shelve 路径（用于迁移检测）
OLD_SHELVE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".kongfz_cookies"
)


# ============================================================
#  存储基础操作
# ============================================================


def get_storage_path():
    """返回 STORAGE_FILE 路径"""
    return STORAGE_FILE


def _read_storage():
    """内部：读取 JSON 存储文件，不存在或损坏返回 None"""
    if not os.path.exists(STORAGE_FILE):
        return None
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def _write_storage(data):
    """内部：写入 JSON 存储文件"""
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
#  Cookie 生命周期
# ============================================================


def load_cookie():
    """读取 Cookie 字符串，不存在返回 None"""
    data = _read_storage()
    if data is None:
        return None
    cookie = data.get("cookie")
    if not cookie:
        return None
    return cookie


def save_cookie(cookie_str, verified=False):
    """保存 Cookie，写入时间戳。返回 True 表示成功。"""
    if not cookie_str:
        return False

    now = datetime.now(timezone.utc).isoformat()

    # 读取现有数据，保留 created_at 和累积计数
    existing = _read_storage()
    if existing:
        created_at = existing.get("created_at", now)
        verify_count = existing.get("verify_count", 0)
        fail_count = existing.get("fail_count", 0)
    else:
        created_at = now
        verify_count = 0
        fail_count = 0

    if verified:
        is_valid = True
        verify_count += 1
        last_verified_at = now
    else:
        is_valid = existing.get("is_valid", False) if existing else False
        last_verified_at = existing.get("last_verified_at", "") if existing else ""

    data = {
        "cookie": cookie_str,
        "created_at": created_at,
        "updated_at": now,
        "last_verified_at": last_verified_at,
        "is_valid": is_valid,
        "verify_count": verify_count,
        "fail_count": fail_count,
        "migrated": existing.get("migrated", False) if existing else False,
    }

    _write_storage(data)
    return True


def delete_cookie():
    """删除存储文件"""
    if os.path.exists(STORAGE_FILE):
        try:
            os.remove(STORAGE_FILE)
            return True
        except OSError:
            return False
    return False


# ============================================================
#  验证
# ============================================================


def test_cookie(cookie_str):
    """调用 API 验证 Cookie 是否有效，更新存储中的验证记录"""
    now = datetime.now(timezone.utc).isoformat()

    # 执行 API 测试
    try:
        params = urllib.parse.urlencode(
            {"keyword": "9787108009821", "page": 1, "size": 1}
        )
        url = f"{API_HOST}{API_PATH}?{params}"
        req = urllib.request.Request(url, headers={**HEADERS, "Cookie": cookie_str})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        is_valid = data.get("status") == 1 and data.get("data") is not None
    except urllib.error.HTTPError as e:
        is_valid = False
    except urllib.error.URLError:
        is_valid = False
    except Exception:
        is_valid = False

    # 更新存储中的验证记录
    existing = _read_storage()
    if existing is not None and existing.get("cookie") == cookie_str:
        verify_count = existing.get("verify_count", 0)
        fail_count = existing.get("fail_count", 0)
        if is_valid:
            verify_count += 1
        else:
            fail_count += 1

        data = dict(existing)
        data["last_verified_at"] = now
        data["is_valid"] = is_valid
        data["verify_count"] = verify_count
        data["fail_count"] = fail_count
        _write_storage(data)

    return is_valid


def verify_current_cookie():
    """验证当前存储的 Cookie，返回 (is_valid, message)"""
    cookie = load_cookie()
    if not cookie:
        return (False, "未存储 Cookie")

    is_valid = test_cookie(cookie)
    if is_valid:
        return (True, "Cookie 有效")
    else:
        return (False, "Cookie 已失效")


def get_cookie_info():
    """返回完整状态信息"""
    data = _read_storage()

    if data is None or not data.get("cookie"):
        return {
            "has_cookie": False,
            "cookie_len": 0,
            "is_valid": False,
            "created_at": "",
            "updated_at": "",
            "last_verified_at": "",
            "days_since_update": 0,
            "verify_count": 0,
            "fail_count": 0,
            "storage_path": STORAGE_FILE,
        }

    cookie = data.get("cookie", "")
    updated_at_str = data.get("updated_at", "")

    # 计算距上次更新的天数
    days_since_update = 0
    if updated_at_str:
        try:
            updated_dt = datetime.fromisoformat(updated_at_str)
            now_dt = datetime.now(timezone.utc)
            delta = now_dt - updated_dt
            days_since_update = round(delta.total_seconds() / 86400, 1)
        except (ValueError, TypeError):
            days_since_update = 0

    return {
        "has_cookie": True,
        "cookie_len": len(cookie),
        "is_valid": data.get("is_valid", False),
        "created_at": data.get("created_at", ""),
        "updated_at": updated_at_str,
        "last_verified_at": data.get("last_verified_at", ""),
        "days_since_update": days_since_update,
        "verify_count": data.get("verify_count", 0),
        "fail_count": data.get("fail_count", 0),
        "storage_path": STORAGE_FILE,
    }


# ============================================================
#  提取与迁移
# ============================================================


def extract_from_curl(text):
    """从 cURL 命令或文本中提取 Cookie 字符串"""
    if not text:
        return None

    # 匹配 -H 'Cookie: ...' 或 --header 'Cookie: ...'
    patterns = [
        r"['\"]cookie:\s*(.*?)['\"]",
        r"['\"]Cookie:\s*(.*?)['\"]",
        r"-b\s+['\"]([^'\"]+)['\"]",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            val = val.rstrip("'\" ;")
            if val:
                return val

    # 直接找 Cookie= 值的模式
    m = re.search(r"Cookie[=:]\s*['\"]([^'\"]+)['\"]", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip().rstrip("'\" ;")
        if val:
            return val

    # 纯 Cookie 文本（key=value 格式），排除 curl 命令和 URL
    clean = text.strip().strip("'\"")
    if clean and "=" in clean:
        lower = clean.lower()
        if not (lower.startswith("curl") or lower.startswith("http")):
            return clean

    return None


def migrate_from_shelve_needed():
    """检查是否需要从 shelve 迁移到 JSON"""
    shelve_exists = any(
        os.path.exists(OLD_SHELVE_PATH + suffix)
        for suffix in [".db", ".dat", ".bak", ".dir"]
    )
    if not shelve_exists:
        return False

    # 如果 JSON 存储已存在且包含已迁移标记，不需要迁移
    data = _read_storage()
    if data is not None and data.get("migrated"):
        return False

    return True


def migrate_from_shelve():
    """从 shelve 迁移到 JSON。返回 True 表示迁移成功。"""
    if not migrate_from_shelve_needed():
        return False

    try:
        with shelve.open(OLD_SHELVE_PATH) as db:
            cookie = db.get("cookies")
            if not cookie:
                return False
            updated_at = db.get("updated_at", "")
    except Exception:
        return False

    now = datetime.now(timezone.utc).isoformat()

    data = {
        "cookie": cookie,
        "created_at": updated_at or now,
        "updated_at": now,
        "last_verified_at": "",
        "is_valid": False,
        "verify_count": 0,
        "fail_count": 0,
        "migrated": True,
    }

    _write_storage(data)
    return True
