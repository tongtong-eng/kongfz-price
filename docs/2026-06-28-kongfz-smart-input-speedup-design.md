# 孔夫子查价网站 · 智能输入 + 并行查价 设计方案

> 日期：2026-06-28
> 基于用户反馈：进货扫书场景，最痛点是从聊天消息/照片中整理 ISBN

---

## 一、现状

现有功能：
- 纯 textarea 输入 ISBN（每行一个）
- 串行查价（间隔 1.5s），20 本约 35 秒
- 结果全部完成后才渲染
- 仅支持手动粘贴纯 ISBN 数字

## 二、目标

1. **智能输入**：不管什么格式粘贴/上传，自动识别 ISBN
2. **OCR 识别**：上传书单照片自动提取 ISBN
3. **手机扫码**：调用摄像头扫条码查价
4. **并行查价**：大幅提速，结果逐本实时渲染

---

## 三、详细设计

### 3.1 架构总览

```
用户输入
    │
    ├─ 粘贴文本 ──→ 智能 ISBN 提取器 ──→ 确认弹窗 ──→
    │                                                      │
    ├─ 图片拖拽/上传 ──→ POST /api/ocr ──→ pytesseract ──→   ├── 并行查价引擎 ──→ 逐本渲染结果
    │                                                      │       (并发 5~8)
    └─ 手机扫码 ──→ BarcodeDetector API ──→ 自动填入 ──→
```

### 3.2 智能粘贴（前端）

**触发机制：**
- 监听 textarea 的 `paste` 事件
- 从 `clipboardData` 获取纯文本内容

**提取逻辑（JavaScript）：**
```js
function extractISBNs(text) {
  // 1. 去除连字符、空格
  // 2. 正则匹配 10~13 位纯数字
  // 3. 校验 ISBN-10 / ISBN-13 格式
  // 4. 去重
  // 5. 返回 {isbns: [...], ignored: number}
}
```

**用户交互：**
- 粘贴后自动弹出底部浮动条："📋 从粘贴内容中识别到 X 个 ISBN（忽略 Y 行）→ 确认查价"
- 点击确认后直接开始并行查价
- 用户仍可手动编辑 textarea

**支持的输入格式：**

| 来源 | 示例 | 提取 |
|------|------|------|
| 聊天消息 | `9787108009821 帮我查下价格` | 1 个 |
| Excel 整列复制 | `978-7-100-09821-0\t论语\t25\n978-7-...` | 多个 |
| 混杂文本 | `数学 9787108009821 x2本，语文 9787020002207` | 2 个 |
| 纯数字列表 | `9787108009821\n9787020002207` | 多个 |

### 3.3 图片 OCR（前端 + 后端）

**前端：**
- 输入区下方新增上传区，支持点击和拖拽
- 支持格式：jpg / png / heic
- 上传后显示缩略图和识别状态
- 支持一次上传多张图片

**后端 `POST /api/ocr`：**
- 接收 multipart/form-data 图片
- 用 **pytesseract** + **Pillow** 做中文 OCR
- 从识别文本中提取 ISBN
- 返回：`{isbns: [...], raw_text: "...", image_count: 1}`

**依赖安装：**
```bash
brew install tesseract tesseract-lang  # 安装中文语言包
pip install pytesseract Pillow
```

### 3.4 手机扫码（纯前端）

**入口：** 输入区旁新增 "📷 扫码" 按钮
**实现：**
- 使用 `navigator.mediaDevices.getUserMedia` 打开摄像头
- 使用 `BarcodeDetector` API 检测条形码（Chrome 系支持）
- 检测到 ISBN 后自动填入输入框并查价

**降级：** 浏览器不支持时隐藏按钮，不影响主功能

### 3.5 并行查价引擎（前端改造）

**改前（串行）：**
```js
function doNext(idx) {
  queryIsbn(isbns[idx]).then(...)   // 一本查完再查下一本
  // 间隔 1.5s
}
```

**改后（并行，并发控制）：**
```js
async function parallelQuery(isbns, concurrency = 6) {
  const pool = new Set();
  const results = [];
  for (const isbn of isbns) {
    if (pool.size >= concurrency) {
      await Promise.race(pool);  // 等一个完成
    }
    const p = queryIsbn(isbn).then(r => {
      renderSingleResult(r);     // 逐本渲染
      return r;
    });
    pool.add(p);
    p.finally(() => pool.delete(p));
  }
  await Promise.all(pool);
  return results;
}
```

**并发数控制：** 可调，默认 6

**进度展示改造：**
- 每本书一个独立状态卡片，实时显示：
  - 🔍 查询中 → ✅ ¥xx.xx → ❌ 失败
- 不用等全部完成才看结果

### 3.6 性能预期

| 本数 | 改前（串行） | 改后（并发 6） |
|------|------------|--------------|
| 10 本 | ~18 秒 | ~5 秒 |
| 20 本 | ~35 秒 | ~8 秒 |
| 50 本 | ~85 秒 | ~15 秒 |

---

## 四、涉及文件

### 改前端（核心）
- **`/Users/tong/kongfz_web.html`**（本地版）
- **`/Users/tong/kongfz_cloud/index.html`**（云版）

改动内容：智能粘贴、图片上传、扫码入口、并行查价引擎、逐本渲染

### 改后端
- **`/Users/tong/kongfz_web.py`**（本地版）
- **`/Users/tong/kongfz_cloud/app.py`**（云版）

改动内容：新增 `/api/ocr` 接口

---

## 五、边界情况与错误处理

| 场景 | 处理方式 |
|------|---------|
| 粘贴内容不含 ISBN | 提示"未识别到有效 ISBN"，保留原内容让用户手动编辑 |
| OCR 识别不出 ISBN | 返回原始识别文本供参考，提示用户手动输入 |
| 扫码不支持 | 按钮隐藏，不影响其他功能 |
| 并行请求部分失败 | 失败的自动重试 1 次，仍然失败的标记为异常（现有异常展示机制） |
| 并发数过高被限流 | 提供并发数调节入口（默认 6，用户可改） |
| 上传非图片文件 | 前端 type 校验 + 后端校验，拒绝并提示 |

---

## 六、不做（YAGNI）

以下功能与当前场景无关，暂不纳入：
- 书单管理/采购单系统
- 价格追踪/降价提醒
- 利润计算/报价单生成
- 代码重构/架构升级
