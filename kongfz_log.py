#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子查价服务 · 结构化日志模块
==============================
轻量内存环形日志，记录查询耗时、失败原因、限流/熔断事件，
供 /api/logs 接口查询，方便排查「查价慢 / 被封」等问题。

设计原则：
  - 纯标准库，无外部依赖
  - 内存环形缓冲（最多 N 条），不写磁盘，重启即清空
  - 线程安全（多线程查价并发写日志）
"""

import threading
import time
from collections import deque

# 最多保留的日志条数
MAX_ENTRIES = 200

# 环形缓冲 + 锁
_BUFFER = deque(maxlen=MAX_ENTRIES)
_LOCK = threading.Lock()

# 统计计数
_STATS = {
    "query_total": 0,        # 累计查询次数
    "query_ok": 0,           # 查询成功次数
    "query_fail": 0,         # 查询失败次数
    "rate_limit_hits": 0,    # 触发限流/封禁次数
    "circuit_breaks": 0,     # 熔断次数
    "started_at": time.time(),
}


def log(event_type, message, **fields):
    """写入一条结构化日志。event_type: query/error/rate_limit/circuit_break/info"""
    entry = {
        "ts": time.strftime("%H:%M:%S"),
        "ts_epoch": time.time(),
        "type": event_type,
        "message": message,
    }
    entry.update(fields)
    with _LOCK:
        _BUFFER.append(entry)


def record_query(ok, isbn="", cost_ms=0, error=""):
    """记录一次查价结果，更新统计。"""
    with _LOCK:
        _STATS["query_total"] += 1
        if ok:
            _STATS["query_ok"] += 1
        else:
            _STATS["query_fail"] += 1
    log("query" if ok else "error",
        ("成功" if ok else "失败"),
        isbn=isbn,
        cost_ms=round(cost_ms, 1),
        error=error)


def record_rate_limit(message=""):
    """记录一次限流/封禁命中。"""
    with _LOCK:
        _STATS["rate_limit_hits"] += 1
    log("rate_limit", message or "检测到限流/封禁")


def record_circuit_break(message=""):
    """记录一次熔断。"""
    with _LOCK:
        _STATS["circuit_breaks"] += 1
    log("circuit_break", message or "熔断打开，暂停出站请求")


def get_logs(limit=100):
    """返回最近 limit 条日志（倒序，最新在前）。"""
    with _LOCK:
        entries = list(_BUFFER)
    entries.reverse()
    return entries[:limit]


def get_stats():
    """返回统计信息。"""
    with _LOCK:
        stats = dict(_STATS)
    stats["uptime_sec"] = round(time.time() - _STATS["started_at"], 1)
    stats["buffer_len"] = len(_BUFFER)
    return stats
