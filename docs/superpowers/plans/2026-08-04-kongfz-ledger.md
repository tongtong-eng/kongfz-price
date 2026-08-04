# 记账功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为孔夫子查价工具新增记账功能——按单记进货/卖出，自动算差价盈利，提供今日/本周/本月汇总与每周每月滚动趋势。

**Architecture:** 新建独立后端模块 `kongfz_ledger.py`（JSON 文件存储 + 纯逻辑），在 `app.py` 挂 4 个 `/api/ledger/*` 路由；前端在本地版 `kongfz_web.html` 与云版 `kongfz_cloud/index.html` 各新增「📒 账本」卡片（底部导航按钮进入），两个文件同步修改。

**Tech Stack:** Python 标准库（http.server / json / datetime / unittest），原生 JavaScript。

## Global Constraints

- 项目只依赖 Python 标准库，**不引入第三方依赖**（测试用标准库 `unittest`）
- 所有代码注释、文档、界面文案用简体中文
- 前端本地版 `kongfz_web.html` 与云版 `kongfz_cloud/index.html` **必须同步修改**（记忆 kongfz-sync-both-frontends）
- 盈利口径 = 数量×售价 − 数量×成本，只算差价，不含佣金/运费
- 后端改动只需改 `kongfz_cloud/` 目录下的文件
- 数据存 `data/kongfz_ledger.json`，记录上限 500 条
- 日期格式 `YYYY-MM-DD`；周=自然周（周一起），月=自然月（1号起）

---

### Task 1: 后端记账模块 `kongfz_ledger.py`

**Files:**
- Create: `kongfz_cloud/kongfz_ledger.py`
- Create: `kongfz_cloud/tests/test_ledger.py`

**Interfaces:**
- Produces（供 Task 2 与后续使用）:
  - `add_record(type_, book, isbn, qty, unit, cost, date_str=None) -> dict`
  - `list_records(limit=20, type_filter="") -> list`
  - `delete_record(rid) -> bool`
  - `summary(scope="today") -> dict`
  - `trends(weeks=8, months=6) -> {"weekly": [...], "monthly": [...]}`
  - 模块变量 `LEDGER_FILE`（可覆盖，供测试指向临时文件）

- [ ] **Step 1: 写失败测试**

Create `kongfz_cloud/tests/test_ledger.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记账模块单元测试（标准库 unittest）"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kongfz_ledger as lg


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        lg.LEDGER_FILE = os.path.join(self.tmp, "ledger.json")

    def test_add_in_computes_cost(self):
        rec = lg.add_record("in", "红岩", "9787020002207", 10, 5.0, 0, "2026-08-04")
        self.assertEqual(rec["type"], "in")
        self.assertEqual(rec["cost"], 50.0)
        self.assertNotIn("profit", rec)

    def test_add_out_computes_sale_and_profit(self):
        rec = lg.add_record("out", "红岩", "9787020002207", 3, 15.0, 5.0, "2026-08-04")
        self.assertEqual(rec["sale"], 45.0)
        self.assertEqual(rec["cost"], 15.0)
        self.assertEqual(rec["profit"], 30.0)

    def test_default_date_is_today(self):
        import datetime
        rec = lg.add_record("in", "书", "", 1, 10.0, 0)
        self.assertEqual(rec["date"], datetime.date.today().strftime("%Y-%m-%d"))

    def test_summary_today(self):
        lg.add_record("in", "红岩", "", 2, 5.0, 0, "2026-08-04")
        lg.add_record("out", "红岩", "", 1, 15.0, 5.0, "2026-08-04")
        s = lg.summary("today")
        # 用测试里写入的日期固定范围——但 today 依赖系统日期，此处仅验证结构
        self.assertEqual(set(s.keys()), {"scope", "in_cost", "out_sale", "profit", "in_count", "out_count"})

    def test_trends_structure(self):
        lg.add_record("in", "红岩", "", 2, 5.0, 0, "2026-08-04")
        t = lg.trends()
        self.assertEqual(len(t["weekly"]), 8)
        self.assertEqual(len(t["monthly"]), 6)
        self.assertTrue(all("label" in w and "in_cost" in w for w in t["weekly"]))

    def test_delete_record(self):
        rec = lg.add_record("in", "红岩", "", 1, 5.0, 0, "2026-08-04")
        self.assertTrue(lg.delete_record(rec["id"]))
        self.assertFalse(lg.delete_record(rec["id"]))
        self.assertEqual(lg.list_records(100), [])

    def test_list_filter(self):
        lg.add_record("in", "红岩", "", 1, 5.0, 0, "2026-08-04")
        lg.add_record("out", "红岩", "", 1, 15.0, 5.0, "2026-08-04")
        self.assertEqual(len(lg.list_records(100, "in")), 1)
        self.assertEqual(len(lg.list_records(100, "out")), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/tong/kongfz_cloud && mkdir -p tests && python tests/test_ledger.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'kongfz_ledger'`

- [ ] **Step 3: 写实现 `kongfz_ledger.py`**

Create `kongfz_cloud/kongfz_ledger.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孔夫子查价 · 记账模块（进/销单，差价盈利）
====================================
- 按单记：进货单 / 卖出单，一单一种书（可多本）
- 盈利 = 数量×售价 − 数量×成本（只算差价）
- 数据存 JSON 文件，上限 500 条
"""
import json
import os
import time
from datetime import date, datetime, timedelta

# 数据文件（测试可覆盖为临时文件）
LEDGER_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "kongfz_ledger.json"
)
LEDGER_MAX = 500  # 记录上限


def _round2(x):
    return round(x, 2)


def load_ledger():
    """读取全部记录，文件损坏时重置为空"""
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("records"), list):
                return data
        except Exception:
            pass
    return {"records": []}


def save_ledger(data):
    os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_record(type_, book, isbn, qty, unit, cost, date_str=None):
    """
    记一笔。type_='in' 进货 / 'out' 卖出。
    - 进货：cost（总成本）= qty × unit
    - 卖出：cost（总成本）= qty × cost，sale（销售额）= qty × unit，profit = sale − cost
    返回新记录 dict。
    """
    type_ = type_ if type_ in ("in", "out") else "in"
    qty = int(qty)
    unit = float(unit)
    if not date_str:
        date_str = date.today().strftime("%Y-%m-%d")
    rec = {
        "id": f"{'IN' if type_ == 'in' else 'OUT'}_{int(time.time() * 1000)}",
        "type": type_,
        "book": str(book or "").strip(),
        "isbn": str(isbn or "").strip(),
        "qty": qty,
        "unit": unit,
        "date": str(date_str),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if type_ == "in":
        rec["cost"] = _round2(qty * unit)
    else:
        cost = float(cost)
        rec["cost"] = _round2(qty * cost)
        rec["sale"] = _round2(qty * unit)
        rec["profit"] = _round2(rec["sale"] - rec["cost"])

    data = load_ledger()
    data["records"].insert(0, rec)
    if len(data["records"]) > LEDGER_MAX:
        data["records"] = data["records"][:LEDGER_MAX]
    save_ledger(data)
    return rec


def list_records(limit=20, type_filter=""):
    """明细列表（按写入顺序倒序），可选按 in/out 过滤"""
    records = load_ledger()["records"]
    if type_filter in ("in", "out"):
        records = [r for r in records if r["type"] == type_filter]
    return records[:limit]


def delete_record(rid):
    """删除一笔，存在且被删除返回 True"""
    data = load_ledger()
    before = len(data["records"])
    data["records"] = [r for r in data["records"] if r["id"] != rid]
    if len(data["records"]) != before:
        save_ledger(data)
        return True
    return False


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _sum_range(records, start, end):
    """统计 [start, end] 日期范围内进货/销售/盈利"""
    in_cost = out_sale = profit = 0
    in_count = out_count = 0
    for r in records:
        d = _parse_date(r.get("date", ""))
        if d is None or not (start <= d <= end):
            continue
        if r.get("type") == "out":
            out_sale += r.get("sale", 0)
            profit += r.get("profit", 0)
            out_count += 1
        else:
            in_cost += r.get("cost", 0)
            in_count += 1
    return {
        "in_cost": _round2(in_cost),
        "out_sale": _round2(out_sale),
        "profit": _round2(profit),
        "in_count": in_count,
        "out_count": out_count,
    }


def summary(scope="today"):
    """今日/本周/本月汇总。scope: today | week | month"""
    t = date.today()
    if scope == "week":
        start = t - timedelta(days=t.weekday())  # 本周一
    elif scope == "month":
        start = t.replace(day=1)  # 本月 1 号
    else:
        start = t
    agg = _sum_range(load_ledger()["records"], start, t)
    agg["scope"] = scope
    return agg


def trends(weeks=8, months=6):
    """返回最近 N 周、最近 N 月聚合，供前端滚动表格展示"""
    t = date.today()
    week_list = []
    for i in range(weeks - 1, -1, -1):
        ws = t - timedelta(days=t.weekday() + 7 * i)
        we = ws + timedelta(days=6)
        agg = _sum_range(load_ledger()["records"], ws, we)
        agg["label"] = f"{ws.month}月{ws.day}日-{we.month}月{we.day}日"
        week_list.append(agg)

    month_list = []
    for i in range(months - 1, -1, -1):
        y, m = t.year, t.month - i
        while m <= 0:
            y -= 1
            m += 12
        ms = date(y, m, 1)
        me = date(y + 1, 1, 1) - timedelta(days=1) if m == 12 else date(y, m + 1, 1) - timedelta(days=1)
        agg = _sum_range(load_ledger()["records"], ms, me)
        agg["label"] = f"{y}年{m}月"
        month_list.append(agg)

    return {"weekly": week_list, "monthly": month_list}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/tong/kongfz_cloud && python tests/test_ledger.py`
Expected: `Ran 7 tests ... OK`

- [ ] **Step 5: 提交**

```bash
cd /Users/tong/kongfz_cloud && git add kongfz_ledger.py tests/test_ledger.py && git commit -m "feat: 记账模块 kongfz_ledger.py（进/销单、差价盈利、日周月汇总）"
```

---

### Task 2: `app.py` 挂载 `/api/ledger/*` 路由

**Files:**
- Modify: `kongfz_cloud/app.py`（import 区、`do_GET`、`do_POST`）

**Interfaces:**
- Consumes: `add_record / list_records / delete_record / summary / trends`（来自 Task 1）
- Produces: HTTP 接口
  - `POST /api/ledger/add` body: `{type, book, isbn, qty, unit, cost, date}`
  - `GET /api/ledger/list?limit=&type=`
  - `GET /api/ledger/summary?scope=today|week|month|all`
  - `GET /api/ledger/delete?id=`

- [ ] **Step 1: 加 import**

In `kongfz_cloud/app.py`, 在现有 import 区（`from kongfz_order import search_by_phone` 之后）追加：

```python
from kongfz_ledger import add_record, list_records, delete_record
from kongfz_ledger import summary as ledger_summary
from kongfz_ledger import trends as ledger_trends
```

- [ ] **Step 2: 在 `do_GET` 加 3 个路由**

在 `do_GET` 中 `/api/history/delete` 分支（`elif path.startswith("/api/history/delete"):` 整个 if 块）之后、`elif path.startswith("/api/self_check"):` 之前插入：

```python
        elif path.startswith("/api/ledger/list"):
            # 记账明细列表
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            limit = int(q.get("limit", ["20"])[0])
            type_filter = q.get("type", [""])[0]
            records = list_records(limit=limit, type_filter=type_filter)
            self.send_json({"records": records})
        elif path.startswith("/api/ledger/summary"):
            # 记账汇总：today/week/month 或 all（周月滚动）
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            scope = q.get("scope", ["today"])[0]
            if scope in ("today", "week", "month"):
                self.send_json(ledger_summary(scope))
            elif scope == "all":
                self.send_json(ledger_trends())
            else:
                self.send_json({"error": "scope 参数无效"})
        elif path.startswith("/api/ledger/delete"):
            # 删除一笔记账
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            rid = q.get("id", [""])[0]
            if not rid:
                self.send_json({"error": "缺少 id 参数"})
                return
            ok = delete_record(rid)
            self.send_json({"success": ok})
```

- [ ] **Step 3: 在 `do_POST` 加 `/api/ledger/add`**

在 `do_POST` 中 `/api/history/save` 分支之后、`else:` 之前插入：

```python
        elif self.path.startswith("/api/ledger/add"):
            # 记账：记一笔进货/卖出
            body = self._read_json()
            if body is None:
                return
            type_ = body.get("type", "")
            book = (body.get("book", "") or "").strip()
            if type_ not in ("in", "out"):
                self.send_json({"error": "type 必须是 in 或 out"})
                return
            if not book:
                self.send_json({"error": "书名不能为空"})
                return
            try:
                qty = int(body.get("qty", 1))
                unit = float(body.get("unit", 0))
            except (TypeError, ValueError):
                self.send_json({"error": "数量/单价格式不对"})
                return
            if qty <= 0 or unit <= 0:
                self.send_json({"error": "数量和单价必须大于 0"})
                return
            if type_ == "out":
                try:
                    cost = float(body.get("cost", 0))
                except (TypeError, ValueError):
                    self.send_json({"error": "成本格式不对"})
                    return
                if cost <= 0:
                    self.send_json({"error": "卖出必须填写成本"})
                    return
            else:
                cost = 0
            rec = add_record(type_, book, body.get("isbn", ""), qty, unit,
                             cost, body.get("date", ""))
            self.send_json({"success": True, "record": rec,
                            "summary": ledger_summary("today")})
```

- [ ] **Step 4: 启动服务做冒烟测试**

Run:
```bash
cd /Users/tong/kongfz_cloud && rm -f data/kongfz_ledger.json
python app.py > /tmp/kfz_server.log 2>&1 &
sleep 2
echo "── 记一笔进货 ──"
curl -s -X POST http://localhost:5000/api/ledger/add -H 'Content-Type: application/json' -d '{"type":"in","book":"红岩","qty":10,"unit":5.0,"date":"2026-08-04"}'
echo; echo "── 记一笔卖出 ──"
curl -s -X POST http://localhost:5000/api/ledger/add -H 'Content-Type: application/json' -d '{"type":"out","book":"红岩","qty":3,"unit":15.0,"cost":5.0,"date":"2026-08-04"}'
echo; echo "── 今日汇总 ──"
curl -s 'http://localhost:5000/api/ledger/summary?scope=today'
echo; echo "── 明细 ──"
curl -s 'http://localhost:5000/api/ledger/list?limit=5'
echo; echo "── 周月滚动 ──"
curl -s 'http://localhost:5000/api/ledger/summary?scope=all'
echo; echo "── 非法 type ──"
curl -s -X POST http://localhost:5000/api/ledger/add -H 'Content-Type: application/json' -d '{"type":"x","book":"书","qty":1,"unit":1}'
echo
```
Expected: 各接口返回成功 JSON；进货 cost=50；卖出 sale=45 / profit=30；非法 type 返回 `{"error":"type 必须是 in 或 out"}`。

- [ ] **Step 5: 停掉服务并清理测试数据**

Run:
```bash
pkill -f "python app.py"
rm -f /Users/tong/kongfz_cloud/data/kongfz_ledger.json
```

- [ ] **Step 6: 提交**

```bash
cd /Users/tong/kongfz_cloud && git add app.py && git commit -m "feat: app.py 挂载 /api/ledger/* 记账接口"
```

---

### Task 3: 云版前端 `index.html` 加「📒 账本」卡片

**Files:**
- Modify: `kongfz_cloud/index.html`（底部导航、卡片区、`<script>` 内 JS）

**Interfaces:**
- Consumes: `/api/ledger/add|list|summary|delete`（来自 Task 2）
- 复用现有函数：`id()`、`fj()`、`es()`、`fold()`

- [ ] **Step 1: 底部导航加按钮**

在 `index.html` 底部导航 `<div class="bottom-nav">` 中，「历史」按钮（`onclick="fold('hist')"`）之后加：

```html
  <button onclick="fold('ledger');lgRefresh()"><svg viewBox="0 0 24 24"><path d="M9 14h6"/><path d="M9 11h6"/><path d="M5 21h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2z"/></svg><span>📒 账本</span></button>
```

- [ ] **Step 2: 插入账本卡片 HTML**

在「历史记录」卡片 `</div>`（`<div id="histList">...` 所在 card 的闭合）之后、`<div id="results"></div>` 之前插入：

```html
  <!-- 记账 -->
  <div class="card">
    <div class="fold-header" onclick="fold('ledger');lgRefresh()">
      <div class="card-title" style="margin-bottom:0">📒 账本</div>
      <span><span class="arrow" id="ledgerArrow">▶</span></span>
    </div>
    <div class="fold-body" id="fold_ledger">
      <div style="margin-top:8px">
        <div style="display:flex;gap:6px;margin-bottom:8px">
          <button class="btn btn-primary" id="lgTypeIn" onclick="lgSetType('in')" style="flex:1">⬇ 记进货</button>
          <button class="btn btn-outline" id="lgTypeOut" onclick="lgSetType('out')" style="flex:1">⬆ 记卖出</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <input id="lgBook" class="field" placeholder="书名（如：红岩）">
          <input id="lgIsbn" class="field" placeholder="ISBN（选填）">
          <div style="display:flex;gap:6px">
            <input id="lgQty" type="number" class="field" placeholder="数量" value="1" style="flex:1">
            <input id="lgUnit" type="number" class="field" placeholder="进价/售价" style="flex:1.5">
          </div>
          <div id="lgCostRow" style="display:none;gap:6px">
            <input id="lgCost" type="number" class="field" placeholder="每本成本（卖出必填）">
          </div>
          <div style="display:flex;gap:6px">
            <input id="lgDate" type="date" class="field" style="flex:1">
            <button class="btn btn-primary" onclick="lgSave()" style="flex:0.8">💾 保存</button>
          </div>
        </div>
        <div id="lgMsg" style="font-size:.75rem;color:#d48aa9;margin-top:4px"></div>
        <div style="display:flex;gap:6px;margin-top:10px">
          <button class="btn btn-outline" id="lgTabToday" onclick="lgTab('today')" style="flex:1">今日</button>
          <button class="btn btn-outline" id="lgTabWeek" onclick="lgTab('week')" style="flex:1">本周</button>
          <button class="btn btn-outline" id="lgTabMonth" onclick="lgTab('month')" style="flex:1">本月</button>
        </div>
        <div class="summary" id="lgSummary" style="margin-top:8px"></div>
        <div style="display:flex;gap:6px;margin-top:6px;align-items:center">
          <span style="font-size:.72rem;color:#d48aa9">周期趋势:</span>
          <button class="btn btn-outline" onclick="lgTrend('week')">按周</button>
          <button class="btn btn-outline" onclick="lgTrend('month')">按月</button>
        </div>
        <div id="lgTrend" style="margin-top:6px"></div>
        <div style="font-size:.78rem;font-weight:600;color:#f9a8d4;margin-top:10px">📋 最近记录</div>
        <div id="lgList" style="margin-top:4px"><div style="text-align:center;color:#c4b5d0;font-size:.8rem;padding:10px">暂无</div></div>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: 加 JS 函数**

在 `index.html` 的 `<script>` 末尾（`</script>` 之前）追加：

```javascript
// ── 记账功能 ──────────────────────────
var LG_T={type:'in',tab:'today'};
function lgSetType(t){
  LG_T.type=t;
  id('lgTypeIn').className=t=='in'?'btn btn-primary':'btn btn-outline';
  id('lgTypeOut').className=t=='out'?'btn btn-primary':'btn btn-outline';
  id('lgCostRow').style.display=t=='out'?'flex':'none';
  id('lgUnit').placeholder=t=='in'?'进价':'售价';
}
function lgSave(){
  var book=id('lgBook').value.trim();
  if(!book){id('lgMsg').textContent='请输入书名';return}
  var body={type:LG_T.type,book:book,isbn:id('lgIsbn').value.trim(),
            qty:Number(id('lgQty').value)||0,unit:Number(id('lgUnit').value)||0,
            date:id('lgDate').value};
  if(LG_T.type=='out')body.cost=Number(id('lgCost').value)||0;
  if(body.qty<=0||body.unit<=0){id('lgMsg').textContent='数量和单价必须大于 0';return}
  if(LG_T.type=='out'&&body.cost<=0){id('lgMsg').textContent='卖出必须填写成本';return}
  fj('/api/ledger/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(d){
    if(d.error){id('lgMsg').textContent=d.error;return}
    id('lgMsg').textContent='✅ 已保存 '+(d.record.type=='in'?'进货':'卖出')+' '+d.record.book+' x'+d.record.qty;
    id('lgBook').value='';id('lgIsbn').value='';id('lgCost').value='';
    lgRefresh();
  });
}
function lgTab(t){
  LG_T.tab=t;
  var map={today:'lgTabToday',week:'lgTabWeek',month:'lgTabMonth'};
  var ids=['lgTabToday','lgTabWeek','lgTabMonth'];
  for(var i=0;i<ids.length;i++)id(ids[i]).className=ids[i]==map[t]?'btn btn-primary':'btn btn-outline';
  lgLoadSummary();
}
function lgLoadSummary(){
  fj('/api/ledger/summary?scope='+LG_T.tab).then(function(d){
    if(d.error){id('lgSummary').innerHTML='';return}
    id('lgSummary').innerHTML=
      '<div class="s-card"><div class="n">¥'+(d.in_cost||0).toFixed(1)+'</div><div class="l">进货成本</div></div>'+
      '<div class="s-card blue"><div class="n">¥'+(d.out_sale||0).toFixed(1)+'</div><div class="l">销售额</div></div>'+
      '<div class="s-card green"><div class="n">¥'+(d.profit||0).toFixed(1)+'</div><div class="l">盈利</div></div>'+
      '<div class="s-card amber"><div class="n">'+(d.out_count||0)+'单</div><div class="l">卖出单数</div></div>';
  });
}
function lgTrend(k){
  LG_T.trend=k;
  fj('/api/ledger/summary?scope=all').then(function(d){
    var arr=k=='week'?d.weekly:d.monthly;
    if(!arr||!arr.length){id('lgTrend').innerHTML='';return}
    var h='<table><thead><tr><th>周期</th><th>进货</th><th>销售额</th><th>盈利</th></tr></thead><tbody>';
    for(var i=0;i<arr.length;i++){
      var r=arr[i];
      h+='<tr><td>'+esc(r.label)+'</td><td>¥'+(r.in_cost||0).toFixed(1)+'</td><td>¥'+(r.out_sale||0).toFixed(1)+'</td><td style="color:'+((r.profit||0)>=0?'#10b981':'#ef4444')+'">¥'+(r.profit||0).toFixed(1)+'</td></tr>';
    }
    h+='</tbody></table>';
    id('lgTrend').innerHTML=h;
  });
}
function lgLoadList(){
  fj('/api/ledger/list?limit=20').then(function(d){
    var arr=(d&&d.records)||[];
    if(!arr.length){id('lgList').innerHTML='<div style="text-align:center;color:#c4b5d0;font-size:.8rem;padding:10px">暂无记录</div>';return}
    var h='';
    for(var i=0;i<arr.length;i++){
      var r=arr[i];
      var icon=r.type=='in'?'⬇':'⬆';
      var color=r.type=='in'?'#f59e0b':'#10b981';
      var amt='¥'+(r.type=='in'?(r.cost||0):(r.sale||0)).toFixed(1);
      h+='<div class="h-item"><div class="info"><div class="name">'+icon+' '+esc(r.book)+' <span style="color:#e0a8c2;font-weight:400">x'+r.qty+'</span></div><div class="meta">'+esc(r.date)+(r.type=='out'?' · 盈利 ¥'+(r.profit||0).toFixed(1):'')+'</div></div><div style="color:'+color+';font-weight:700;font-size:.82rem">'+amt+'</div><div class="actions"><button class="btn-h-d" onclick="lgDel(\''+r.id+'\')">✕</button></div></div>';
    }
    id('lgList').innerHTML=h;
  });
}
function lgDel(rid){
  if(!confirm('删除这条记录？'))return;
  fj('/api/ledger/delete?id='+rid).then(function(){lgRefresh()});
}
function lgRefresh(){lgLoadSummary();lgLoadList();}
```

- [ ] **Step 4: 扩展 fold 函数——打开账本卡片时自动刷新**

在 `index.html` 的 `fold()` 函数（约 206-213 行）末尾追加一行，使打开账本卡片时自动加载数据：

```javascript
  if(b.classList.contains('open')&&n==='ledger')lgRefresh();
```

即改后为：
```javascript
function fold(n){
  var b=id('fold_'+n),a=id(n+'Arrow');
  if(!b)return;
  b.classList.toggle('open');
  if(a)a.classList.toggle('open');
  if(b.classList.contains('open')&&n==='hist')loadH();
  if(b.classList.contains('open')&&n==='cookie')ckC();
  if(b.classList.contains('open')&&n==='ledger')lgRefresh();
}
```

> 注意：云版转义函数名为 **`esc()`**（非 `es()`），本任务 JS 已全部使用 `esc()`。若页面初始化另有自动刷新（可选），可加一行 `lgRefresh(); lgTrend('week');`，但非必需——账本卡片默认折叠，点击展开时 fold() 已触发刷新。

- [ ] **Step 5: 验证页面元素存在**

Run: `cd /Users/tong/kongfz_cloud && python app.py > /tmp/kfz_server.log 2>&1 & sleep 2 && curl -s http://localhost:5000/ | grep -o '📒 账本\|lgSave\|lgRefresh' | sort -u`
Expected: 三行均出现。

- [ ] **Step 6: 停服务**

Run: `pkill -f "python app.py"`

- [ ] **Step 7: 提交**

```bash
cd /Users/tong/kongfz_cloud && git add index.html && git commit -m "feat: 云版前端加📒账本卡片（录入/日周月汇总/趋势/明细）"
```

---

### Task 4: 本地版前端 `kongfz_web.html` 加「📒 账本」卡片（同步）

**Files:**
- Modify: `/Users/tong/kongfz_web.html`（底部导航、卡片区、`<script>` 内 JS）

**Interfaces:**
- 与 Task 3 相同；注意**本地版类名不同**：折叠头用 `.fh`/`.fb`/`.ar`，底部导航用 `.bn`，历史卡片 id 为 `fb_hi`/`hil`
- 复用现有函数：`id()`、`fj()`、`es()`、`fold()`

- [ ] **Step 1: 底部导航加按钮**

在 `/Users/tong/kongfz_web.html` 的 `<div class="bn">` 中，「历史」按钮（`onclick="fold('hi')"`）之后加：

```html
  <button onclick="fold('lg');lgRefresh()"><svg viewBox="0 0 24 24"><path d="M9 14h6"/><path d="M9 11h6"/><path d="M5 21h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2z"/></svg><span>📒 账本</span></button>
```

- [ ] **Step 2: 插入账本卡片 HTML**

在「历史记录」卡片（`id="fb_hi"` 所在 card 的闭合 `</div>`）之后、`<div id="res"></div>` 之前插入：

```html
  <!-- 记账 -->
  <div class="card">
    <div class="fh" onclick="fold('lg');lgRefresh()">
      <div class="card-title" style="margin-bottom:0">📒 账本</div>
      <span class="ar" id="lgar">▶</span>
    </div>
    <div class="fb" id="fb_lg">
      <div style="margin-top:8px">
        <div style="display:flex;gap:6px;margin-bottom:8px">
          <button class="btn btn-primary" id="lgTypeIn" onclick="lgSetType('in')" style="flex:1">⬇ 记进货</button>
          <button class="btn btn-outline" id="lgTypeOut" onclick="lgSetType('out')" style="flex:1">⬆ 记卖出</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <input id="lgBook" class="fld" placeholder="书名（如：红岩）">
          <input id="lgIsbn" class="fld" placeholder="ISBN（选填）">
          <div style="display:flex;gap:6px">
            <input id="lgQty" type="number" class="fld" placeholder="数量" value="1" style="flex:1">
            <input id="lgUnit" type="number" class="fld" placeholder="进价/售价" style="flex:1.5">
          </div>
          <div id="lgCostRow" style="display:none;gap:6px">
            <input id="lgCost" type="number" class="fld" placeholder="每本成本（卖出必填）">
          </div>
          <div style="display:flex;gap:6px">
            <input id="lgDate" type="date" class="fld" style="flex:1">
            <button class="btn btn-primary" onclick="lgSave()" style="flex:0.8">💾 保存</button>
          </div>
        </div>
        <div id="lgMsg" style="font-size:.75rem;color:#d48aa9;margin-top:4px"></div>
        <div style="display:flex;gap:6px;margin-top:10px">
          <button class="btn btn-outline" id="lgTabToday" onclick="lgTab('today')" style="flex:1">今日</button>
          <button class="btn btn-outline" id="lgTabWeek" onclick="lgTab('week')" style="flex:1">本周</button>
          <button class="btn btn-outline" id="lgTabMonth" onclick="lgTab('month')" style="flex:1">本月</button>
        </div>
        <div class="summary" id="lgSummary" style="margin-top:8px"></div>
        <div style="display:flex;gap:6px;margin-top:6px;align-items:center">
          <span style="font-size:.72rem;color:#d48aa9">周期趋势:</span>
          <button class="btn btn-outline" onclick="lgTrend('week')">按周</button>
          <button class="btn btn-outline" onclick="lgTrend('month')">按月</button>
        </div>
        <div id="lgTrend" style="margin-top:6px"></div>
        <div style="font-size:.78rem;font-weight:600;color:#f9a8d4;margin-top:10px">📋 最近记录</div>
        <div id="lgList" style="margin-top:4px"><div style="text-align:center;color:#c4b5d0;font-size:.8rem;padding:10px">暂无</div></div>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: 加 JS 函数**

在 `/Users/tong/kongfz_web.html` 的 `<script>` 末尾（`</script>` 之前）追加：

```javascript
// ── 记账功能（与云版同步） ──────────────
var LG_T={type:'in',tab:'today'};
function lgSetType(t){
  LG_T.type=t;
  id('lgTypeIn').className=t=='in'?'btn btn-primary':'btn btn-outline';
  id('lgTypeOut').className=t=='out'?'btn btn-primary':'btn btn-outline';
  id('lgCostRow').style.display=t=='out'?'flex':'none';
  id('lgUnit').placeholder=t=='in'?'进价':'售价';
}
function lgSave(){
  var book=id('lgBook').value.trim();
  if(!book){id('lgMsg').textContent='请输入书名';return}
  var body={type:LG_T.type,book:book,isbn:id('lgIsbn').value.trim(),
            qty:Number(id('lgQty').value)||0,unit:Number(id('lgUnit').value)||0,
            date:id('lgDate').value};
  if(LG_T.type=='out')body.cost=Number(id('lgCost').value)||0;
  if(body.qty<=0||body.unit<=0){id('lgMsg').textContent='数量和单价必须大于 0';return}
  if(LG_T.type=='out'&&body.cost<=0){id('lgMsg').textContent='卖出必须填写成本';return}
  fj('/api/ledger/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(d){
    if(d.error){id('lgMsg').textContent=d.error;return}
    id('lgMsg').textContent='✅ 已保存 '+(d.record.type=='in'?'进货':'卖出')+' '+d.record.book+' x'+d.record.qty;
    id('lgBook').value='';id('lgIsbn').value='';id('lgCost').value='';
    lgRefresh();
  });
}
function lgTab(t){
  LG_T.tab=t;
  var map={today:'lgTabToday',week:'lgTabWeek',month:'lgTabMonth'};
  var ids=['lgTabToday','lgTabWeek','lgTabMonth'];
  for(var i=0;i<ids.length;i++)id(ids[i]).className=ids[i]==map[t]?'btn btn-primary':'btn btn-outline';
  lgLoadSummary();
}
function lgLoadSummary(){
  fj('/api/ledger/summary?scope='+LG_T.tab).then(function(d){
    if(d.error){id('lgSummary').innerHTML='';return}
    id('lgSummary').innerHTML=
      '<div class="s-card"><div class="n">¥'+(d.in_cost||0).toFixed(1)+'</div><div class="l">进货成本</div></div>'+
      '<div class="s-card blue"><div class="n">¥'+(d.out_sale||0).toFixed(1)+'</div><div class="l">销售额</div></div>'+
      '<div class="s-card green"><div class="n">¥'+(d.profit||0).toFixed(1)+'</div><div class="l">盈利</div></div>'+
      '<div class="s-card amber"><div class="n">'+(d.out_count||0)+'单</div><div class="l">卖出单数</div></div>';
  });
}
function lgTrend(k){
  LG_T.trend=k;
  fj('/api/ledger/summary?scope=all').then(function(d){
    var arr=k=='week'?d.weekly:d.monthly;
    if(!arr||!arr.length){id('lgTrend').innerHTML='';return}
    var h='<table><thead><tr><th>周期</th><th>进货</th><th>销售额</th><th>盈利</th></tr></thead><tbody>';
    for(var i=0;i<arr.length;i++){
      var r=arr[i];
      h+='<tr><td>'+es(r.label)+'</td><td>¥'+(r.in_cost||0).toFixed(1)+'</td><td>¥'+(r.out_sale||0).toFixed(1)+'</td><td style="color:'+((r.profit||0)>=0?'#10b981':'#ef4444')+'">¥'+(r.profit||0).toFixed(1)+'</td></tr>';
    }
    h+='</tbody></table>';
    id('lgTrend').innerHTML=h;
  });
}
function lgLoadList(){
  fj('/api/ledger/list?limit=20').then(function(d){
    var arr=(d&&d.records)||[];
    if(!arr.length){id('lgList').innerHTML='<div style="text-align:center;color:#c4b5d0;font-size:.8rem;padding:10px">暂无记录</div>';return}
    var h='';
    for(var i=0;i<arr.length;i++){
      var r=arr[i];
      var icon=r.type=='in'?'⬇':'⬆';
      var color=r.type=='in'?'#f59e0b':'#10b981';
      var amt='¥'+(r.type=='in'?(r.cost||0):(r.sale||0)).toFixed(1);
      h+='<div class="hi"><div class="inf"><div class="nm">'+icon+' '+es(r.book)+' <span style="color:#e0a8c2;font-weight:400">x'+r.qty+'</span></div><div class="mt">'+es(r.date)+(r.type=='out'?' · 盈利 ¥'+(r.profit||0).toFixed(1):'')+'</div></div><div style="color:'+color+';font-weight:700;font-size:.82rem">'+amt+'</div><div class="ac"><button class="bhd" onclick="lgDel(\''+r.id+'\')">✕</button></div></div>';
    }
    id('lgList').innerHTML=h;
  });
}
function lgDel(rid){
  if(!confirm('删除这条记录？'))return;
  fj('/api/ledger/delete?id='+rid).then(function(){lgRefresh()});
}
function lgRefresh(){lgLoadSummary();lgLoadList();}
```

- [ ] **Step 4: 扩展 fold 函数——打开账本卡片时自动刷新**

在 `kongfz_web.html` 的 `fold()` 函数（约 219-224 行）末尾追加一行，使打开账本卡片时自动加载数据：

```javascript
  if(b.classList.contains('open')&&n==='lg')lgRefresh();
```

即改后为：
```javascript
function fold(n){
  var b=id('fb_'+n),a=id(n+'ar');if(!b)return;
  b.classList.toggle('open');if(a)a.classList.toggle('open');
  if(b.classList.contains('open')&&n==='hi')ldH();
  if(b.classList.contains('open')&&n==='ck')ckCK();
  if(b.classList.contains('open')&&n==='lg')lgRefresh();
}
```

> 注意：本地版转义函数名为 **`es()`**（非 `esc()`），本任务 JS 已使用 `es()`。账本卡片默认折叠，点击展开时 fold() 已触发刷新，无需额外初始化。

- [ ] **Step 5: 验证页面元素存在**

Run: `grep -c 'lgSave\|lgRefresh\|📒 账本\|fb_lg' /Users/tong/kongfz_web.html`
Expected: 输出 `4`（或 ≥4，说明四处关键标记都在）。

- [ ] **Step 6: 提交**

```bash
cd /Users/tong/kongfz_cloud && git add /Users/tong/kongfz_web.html && git commit -m "feat: 本地版前端加📒账本卡片（与云版同步）"
```

---

### Task 5: 端到端验证 + 部署

**Files:** 无新代码改动

- [ ] **Step 1: 全量单元测试回归**

Run: `cd /Users/tong/kongfz_cloud && python tests/test_ledger.py`
Expected: `Ran 7 tests ... OK`

- [ ] **Step 2: 启动服务手动浏览器验证**

Run: `cd /Users/tong/kongfz_cloud && python app.py`
Expected: 浏览器打开 `http://localhost:5000` → 底部「📒 账本」按钮 → 录入一笔进货+一笔卖出 → 今日/本周/本月数字正确 → 按周/按月表格正确 → 明细可删除。

- [ ] **Step 3: 推送并部署（用户执行）**

Run:
```bash
cd /Users/tong/kongfz_cloud && git add -A && git commit -m "feat: 记账功能（进/销单、日周月汇总、双端同步）" && git push
```
然后提示用户输入: `! /Users/tong/.local/nodejs/bin/railway redeploy --yes`

- [ ] **Step 4: 验证上线**

Run: `curl -s https://kongfz-price-production.up.railway.app/api/health`
Expected: `{"status": "ok", ...}`。再 `curl -s https://kongfz-price-production.up.railway.app/ | grep -c '📒 账本'`，期望 ≥1。
