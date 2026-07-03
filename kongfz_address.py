#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子旧书网 · 收货地址管理共享模块
====================================
提供地址列表查询、单个/批量删除、自动清理（保留最新 N 个地址）。
"""
import json
import urllib.request

from kongfz_query import HEADERS

API_BASE = "https://user.kongfz.com/pc-gw/user-service/client/pc/address"
MAX_ADDRESSES = 12  # 默认最多保留 12 个地址


class AuthError(Exception):
    """Cookie 未通过认证，需要用户重新设置"""
    pass


def list_addresses(cookie_str):
    """获取当前账号的所有收货地址。

    返回: list[dict]，每个 dict 包含 addrId, receiverName, mobile, address, isDefault 等字段。
          认证失败时抛出 AuthError。
    """
    h = {**HEADERS, "Cookie": cookie_str, "Referer": "https://user.kongfz.com/buyer/receive_address.html"}
    try:
        req = urllib.request.Request(f"{API_BASE}/list", headers=h)
        resp = urllib.request.urlopen(req, timeout=15)
        body = resp.read().decode("utf-8")
        data = json.loads(body)

        # 检查是否未登录
        if isinstance(data, dict):
            msg = (data.get("message") or "").lower()
            if "登录" in msg or "login" in msg:
                raise AuthError(f"未登录，Cookie 对地址管理 API 无效（请更新 Cookie）")
            if data.get("status") == 0 and not data.get("data") and not data.get("result"):
                if data.get("errType") == "100":
                    raise AuthError("Cookie 无效，无法访问地址管理（请更新 Cookie）")
                return []

            items = data.get("result") or data.get("data") or []
        else:
            items = data or []

        # 标准化：补全 addrId
        for it in items:
            if "addrId" not in it and "addr_id" in it:
                it["addrId"] = it["addr_id"]

        return items
    except AuthError:
        raise
    except Exception as e:
        print(f"  ⚠️ 获取地址列表失败: {e}")
        return []


def delete_address(cookie_str, addr_id):
    """删除单个收货地址。

    返回: bool
    """
    h = {**HEADERS, "Cookie": cookie_str, "Referer": "https://user.kongfz.com/buyer/receive_address.html"}
    try:
        req = urllib.request.Request(
            f"{API_BASE}/{addr_id}",
            headers=h,
            method="DELETE",
        )
        resp = urllib.request.urlopen(req, timeout=15)
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        code = data.get("code") if isinstance(data, dict) else 0
        return code == 0
    except Exception as e:
        print(f"  ⚠️ 删除地址 {addr_id} 失败: {e}")
        return False


def batch_delete(cookie_str, addr_ids):
    """批量删除收货地址。

    参数:
        addr_ids: list[int] 或 list[str]
    返回: (成功数, 失败数)
    """
    ids_str = ",".join(str(a) for a in addr_ids)
    h = {**HEADERS, "Cookie": cookie_str, "Referer": "https://user.kongfz.com/buyer/receive_address.html"}
    try:
        req = urllib.request.Request(
            f"{API_BASE}/multi/{ids_str}",
            headers=h,
            method="DELETE",
        )
        resp = urllib.request.urlopen(req, timeout=15)
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        if isinstance(data, dict) and data.get("code") == 0:
            return (len(addr_ids), 0)
        return (0, len(addr_ids))
    except Exception as e:
        print(f"  ⚠️ 批量删除地址失败: {e}")
        # 接口不支持批量时，逐个删除
        ok, ng = 0, 0
        for aid in addr_ids:
            if delete_address(cookie_str, aid):
                ok += 1
            else:
                ng += 1
        return (ok, ng)


def cleanup_addresses(cookie_str, max_count=MAX_ADDRESSES, dry_run=False):
    """自动清理收货地址，只保留最新的 max_count 个。

    保留规则：
    - 默认地址始终保留
    - 按 addrId 降序（越大越新），保留最新的 max_count 个
    - 删除超出的旧地址

    参数:
        cookie_str: Cookie 字符串
        max_count: 最多保留的地址数（默认 12）
        dry_run: 为 True 时只列出待删除项，不实际删除

    返回: dict
        {
            "success": True/False,
            "error": "错误信息（失败时）",
            "total": 总地址数,
            "default_count": 默认地址数,
            "to_delete": 待删除地址列表,
            "deleted": 实际删除数,
            "kept": 保留数,
            "max_count": max_count,
            "errors": 错误数,
        }
    """
    try:
        addrs = list_addresses(cookie_str)
    except AuthError as e:
        return {"success": False, "error": str(e), "total": 0, "default_count": 0,
                "to_delete": [], "deleted": 0, "kept": 0, "max_count": max_count,
                "errors": 0}
    if not addrs:
        return {"success": True, "total": 0, "default_count": 0, "to_delete": [], "deleted": 0,
                "kept": 0, "max_count": max_count, "errors": 0, "message": "无地址或获取失败"}

    total = len(addrs)
    if total <= max_count:
        return {"success": True, "total": total, "default_count": sum(1 for a in addrs if a.get("isDefault") in (1, "1")),
                "to_delete": [], "deleted": 0, "kept": total,
                "max_count": max_count, "errors": 0, "message": f"共 {total} 个，未超过 {max_count} 个限制"}

    # 分离默认地址和非默认地址
    default_addrs = [a for a in addrs if a.get("isDefault") in (1, "1")]
    non_default = [a for a in addrs if a.get("isDefault") not in (1, "1")]

    # 按 addrId 降序排列（ID 越大越新）
    non_default.sort(key=lambda a: int(a.get("addrId", 0)), reverse=True)

    # 需要保留的非默认地址数
    keep_slots = max(0, max_count - len(default_addrs))
    to_keep = non_default[:keep_slots]
    to_delete = non_default[keep_slots:]

    result = {
        "success": True,
        "total": total,
        "default_count": len(default_addrs),
        "to_delete": [
            {"addrId": a.get("addrId"), "receiverName": a.get("receiverName", ""),
             "address": a.get("address", ""), "mobile": a.get("mobile", "")}
            for a in to_delete
        ],
        "deleted": 0,
        "kept": len(default_addrs) + len(to_keep),
        "max_count": max_count,
        "errors": 0,
        "message": f"共 {total} 个地址，默认 {len(default_addrs)} 个，需删除 {len(to_delete)} 个"
    }

    if dry_run or not to_delete:
        return result

    # 实际删除
    del_ids = [a.get("addrId") for a in to_delete if a.get("addrId")]

    # 批量删除
    ok, ng = batch_delete(cookie_str, del_ids)
    result["deleted"] = ok
    result["errors"] = ng

    return result
