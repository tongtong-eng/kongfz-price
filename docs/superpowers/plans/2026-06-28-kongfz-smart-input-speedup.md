# 孔夫子查价 · 智能输入 + 并行查价 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task.

**目标:** 为孔夫子查价网站实现智能 ISBN 输入（智能粘贴 / 图片 OCR / 扫码）和并行查价引擎，从整理 ISBN 最耗时环节切入，大幅提升进货扫书效率

**架构:** 前端改造为主，后端新增 OCR 接口。本地版和云版同步修改

**涉及文件一览:**
| 文件 | 角色 | 改动量 |
|------|------|--------|
| `/Users/tong/kongfz_web.py` | 本地版后端 | 新增 OCR 接口 |
| `/Users/tong/kongfz_web.html` | 本地版前端 | 智能粘贴 + 并行查价 + 扫码 + OCR 上传 |
| `/Users/tong/kongfz_cloud/app.py` | 云版后端 | 新增 OCR 接口 |
| `/Users/tong/kongfz_cloud/index.html` | 云版前端 | 智能粘贴 + 并行查价 + 扫码 + OCR 上传 |
| `/Users/tong/kongfz_cloud/requirements.txt` | 云版依赖 | 增加 pytesseract + Pillow |

## 全局约束

- 所有代码注释使用中文
- 不引入 npm 包或 Webpack，纯原生 JS
- 后端不引入新框架，继续使用 `http.server`
- 云版和本地版保持接口一致（`/api/ocr` + `/api/query` 等）
- 不破坏现有 Cookie 管理、历史记录、加购等功能

---

### 任务 1: OCR 后端接口（本地版 `kongfz_web.py`）

**文件:** 修改 `kongfz_web.py`
**依赖:** `brew install tesseract tesseract-lang` + `pip install pytesseract Pillow`

- [ ] **步骤 1: 增加 import**

`import uuid` 之后增加:

```python
import io
import cgi
import pytesseract
from PIL import Image
```

- [ ] **步骤 2: 新增 `ocr_image()` 函数**

在 `query_isbn()` 函数之后（约第 144 行）新增:

```python
def ocr_image(file_bytes, filename=""):
    """OCR 识别图片中的文字，提取 ISBN"""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        # 中文 + 英文 + 数字识别
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        if not text.strip():
            return {"isbns": [], "raw_text": "", "error": "未识别到文字"}
        # 从识别结果中提取 ISBN（10位或13位数字）
        isbns = set()
        for line in text.split("\n"):
            cleaned = line.strip().replace("-", "").replace(" ", "").replace("　", "")
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
```

- [ ] **步骤 3: 在 `do_POST` 中增加 OCR 路由**

在 `do_POST` 方法的 `elif self.path.startswith("/api/history/save"):` 分支之前增加：

```python
elif self.path.startswith("/api/ocr"):
    content_type = self.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        self.send_json({"error": "需要 multipart/form-data"})
        return
    try:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
        )
        file_item = form.getfirst("image")
        if not file_item or not isinstance(file_item, cgi.FieldStorage):
            self.send_json({"error": "未找到图片数据"})
            return
        file_bytes = file_item.file.read()
        result = ocr_image(file_bytes, file_item.filename or "")
        self.send_json(result)
    except Exception as e:
        self.send_json({"error": str(e)[:60]})
```

- [ ] **步骤 4: 启动时检查 tesseract 可用性**

在 `if __name__ == "__main__":` 块中，`server.serve_forever()` 之前增加：

```python
try:
    pytesseract.get_tesseract_version()
    print("🔍 Tesseract OCR 可用")
except Exception:
    print("⚠️ Tesseract OCR 未安装，图片识别功能不可用")
    print("   brew install tesseract tesseract-lang")
    print("   pip install pytesseract Pillow")
```

- [ ] **步骤 5: 快速验证**

```bash
python3 -c "import pytesseract; print(pytesseract.get_tesseract_version())"
# 预期: 5.x.y
python3 -c "
from kongfz_web import ocr_image
# 用一张空白图片测试
import io
from PIL import Image
img = Image.new('RGB', (100,30), 'white')
buf = io.BytesIO()
img.save(buf, 'PNG')
r = ocr_image(buf.getvalue())
print(r)
# 预期: {'isbns': [], 'raw_text': '', 'image_count': 1}
"
```

---

### 任务 2: OCR 后端接口（云版 `kongfz_cloud/app.py` + `requirements.txt`）

**文件:** 修改 `kongfz_cloud/app.py` + `kongfz_cloud/requirements.txt`
**改动:** 与任务 1 完全相同的逻辑

- [ ] **步骤 1: 在 `app.py` 中增加 import（与任务 1 步骤 1 同）**

```python
import io
import cgi
import pytesseract
from PIL import Image
```

- [ ] **步骤 2: 在 `app.py` 中新增 `ocr_image()` 函数（与任务 1 步骤 2 同，注意放在 `query_isbn` 之后的位置）**

```python
def ocr_image(file_bytes, filename=""):
    """OCR 识别图片中的文字，提取 ISBN"""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        if not text.strip():
            return {"isbns": [], "raw_text": "", "error": "未识别到文字"}
        isbns = set()
        for line in text.split("\n"):
            cleaned = line.strip().replace("-", "").replace(" ", "").replace("　", "")
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
```

- [ ] **步骤 3: 在 `do_POST` 中增加 `/api/ocr` 路由（与任务 1 步骤 3 同）**

```python
elif self.path.startswith("/api/ocr"):
    content_type = self.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        self.send_json({"error": "需要 multipart/form-data"})
        return
    try:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
        )
        file_item = form.getfirst("image")
        if not file_item or not isinstance(file_item, cgi.FieldStorage):
            self.send_json({"error": "未找到图片数据"})
            return
        file_bytes = file_item.file.read()
        result = ocr_image(file_bytes, file_item.filename or "")
        self.send_json(result)
    except Exception as e:
        self.send_json({"error": str(e)[:60]})
```

- [ ] **步骤 4: 启动时检查 tesseract**

```python
try:
    pytesseract.get_tesseract_version()
    print("🔍 Tesseract OCR 可用")
except Exception:
    print("⚠️ Tesseract OCR 未安装，图片识别功能不可用")
```

- [ ] **步骤 5: 在 `requirements.txt` 尾部追加依赖**

```txt
pytesseract>=0.3.10
Pillow>=10.0.0
```

- [ ] **步骤 6: 快速验证**

```bash
cd /Users/tong/kongfz_cloud
python3 -c "from app import ocr_image; print('import OK')"
```

---

### 任务 3: 并行查价引擎（本地版 `kongfz_web.html`）

**文件:** 修改 `kongfz_web.html`
**核心改动:** 将 btnQuery.onclick 中的串行 `doNext()` 替换为并行 `parallelQuery()`，并发数 6

**思路:** 并行查价期间显示进度摘要，每完成一本实时更新进度数字，全部完成后调用已有 `showResults()` 渲染最终结果。`showResults` 本身不需改动。

- [ ] **步骤 1: 替换 `btnQuery.onclick` 函数体**

找到 `btnQuery.onclick = function() { ... }`（约第 191 行），将内部 `doNext` 串行逻辑替换为：

```javascript
btnQuery.onclick = function() {
  if (isRunning) return;
  var text = inputArea.value.trim();
  if (!text) { setStatus('请输入 ISBN', 'error'); return; }

  var isbns = [], seen = {};
  text.split(/[\s,，、\n]+/).forEach(function(s) {
    s = s.trim().replace(/-/g, '');
    if (/^\d{8,13}$/.test(s) && !seen[s]) { seen[s] = true; isbns.push(s); }
  });
  if (!isbns.length) { setStatus('没有有效的 ISBN', 'error'); return; }

  isRunning = true;
  btnQuery.disabled = true;
  emptyEl.style.display = 'none';
  resultsEl.innerHTML = '';
  setStatus('⏳ 并行查询 ' + isbns.length + ' 本...（并发 6）', 'loading');

  // 进度摘要
  var progressHtml = '<div class="summary">';
  progressHtml += '<div class="s-card blue"><div class="n">0/' + isbns.length + '</div><div class="l">进度</div></div>';
  progressHtml += '<div class="s-card green"><div class="n">0</div><div class="l">查到</div></div>';
  progressHtml += '<div class="s-card amber"><div class="n">0</div><div class="l">异常</div></div>';
  progressHtml += '</div>';
  resultsEl.innerHTML = progressHtml;

  var allData = [];
  var okCount = 0, failCount = 0;
  var CONCURRENCY = 6;
  var idx = 0, pending = 0, doneCount = 0;

  function updateProgress() {
    var cards = resultsEl.querySelectorAll('.summary .s-card');
    if (cards.length >= 3) {
      cards[0].querySelector('.n').textContent = doneCount + '/' + isbns.length;
      cards[1].querySelector('.n').textContent = okCount;
      cards[2].querySelector('.n').textContent = failCount;
    }
  }

  function tryNext() {
    while (pending < CONCURRENCY && idx < isbns.length) {
      var i = idx++;
      pending++;
      (function(i) {
        setStatus('⏳ 查询 ' + (i+1) + '/' + isbns.length + ': ' + isbns[i], 'loading');
        queryIsbn(isbns[i]).then(function(data) {
          allData.push(data);
          doneCount++;
          pending--;
          if (data.cheapest) okCount++;
          if (data.error) failCount++;
          updateProgress();
          if (doneCount >= isbns.length) {
            // 全部完成
            lastResults = allData;
            showResults(allData);
            isRunning = false;
            btnQuery.disabled = false;
            setStatus('✅ 查询完成！共 ' + allData.length + ' 本', 'done');
          } else {
            tryNext();
          }
        });
      })(i);
    }
  }

  tryNext();
};
```

> **注意:** 云版 `index.html` 的 `setStatus` 使用 CSS 类 `'status-' + type`，而本地版使用 `type` 原始值。确保 `setStatus('...', 'loading')` 的第二个参数在本地版中能匹配 `.loading` 类选择器。

- [ ] **步骤 2: 验证至少一个 ISBN 能正常查价**

```bash
python3 kongfz_web.py &
sleep 1
curl -s 'http://localhost:5000/api/query?isbn=9787108009821' | python3 -m json.tool | head -5
kill %1 2>/dev/null
```

---

### 任务 4: 并行查价引擎（云版 `kongfz_cloud/index.html`）

**文件:** 修改 `kongfz_cloud/index.html`
**说明:** 与任务 3 完全相同逻辑，但需要适配云版的 CSS 类和 `setStatus` 函数签名

- [ ] **步骤 1: 替换 `btnQuery.onclick` 函数体**

找到 `btnQuery.onclick = function() { ... }`（约第 371 行），替换内部逻辑。代码与任务 3 步骤 1 相同，但注意云版的 `setStatus` 接受第二个参数为 CSS 类后缀（`'loading'` → `'status-loading'`）。

```javascript
btnQuery.onclick = function() {
  if (isRunning) return;
  var text = inputArea.value.trim();
  if (!text) { setStatus('请输入 ISBN', 'error'); return; }

  var isbns = [], seen = {};
  text.split(/[\s,，、\n]+/).forEach(function(s) {
    s = s.trim().replace(/-/g, '');
    if (/^\d{8,13}$/.test(s) && !seen[s]) { seen[s] = true; isbns.push(s); }
  });
  if (!isbns.length) { setStatus('没有有效的 ISBN', 'error'); return; }

  isRunning = true;
  btnQuery.disabled = true;
  emptyEl.style.display = 'none';
  resultsEl.innerHTML = '';
  setStatus('⏳ 并行查询 ' + isbns.length + ' 本...（并发 6）', 'loading');

  var progressHtml = '<div class="summary">';
  progressHtml += '<div class="s-card s-blue"><div class="n">0/' + isbns.length + '</div><div class="l">进度</div></div>';
  progressHtml += '<div class="s-card s-green"><div class="n">0</div><div class="l">查到</div></div>';
  progressHtml += '<div class="s-card s-amber"><div class="n">0</div><div class="l">异常</div></div>';
  progressHtml += '</div>';
  resultsEl.innerHTML = progressHtml;

  var allData = [];
  var okCount = 0, failCount = 0;
  var CONCURRENCY = 6;
  var idx = 0, pending = 0, doneCount = 0;

  function updateProgress() {
    var cards = resultsEl.querySelectorAll('.summary .s-card .n');
    if (cards.length >= 3) {
      cards[0].textContent = doneCount + '/' + isbns.length;
      cards[1].textContent = okCount;
      cards[2].textContent = failCount;
    }
  }

  function tryNext() {
    while (pending < CONCURRENCY && idx < isbns.length) {
      var i = idx++;
      pending++;
      (function(i) {
        setStatus('⏳ 查询 ' + (i+1) + '/' + isbns.length + ': ' + isbns[i], 'loading');
        queryIsbn(isbns[i]).then(function(data) {
          allData.push(data);
          doneCount++;
          pending--;
          if (data.cheapest) okCount++;
          if (data.error) failCount++;
          updateProgress();
          if (doneCount >= isbns.length) {
            lastResults = allData;
            showResults(allData);
            isRunning = false;
            btnQuery.disabled = false;
            setStatus('✅ 查询完成！共 ' + allData.length + ' 本', 'done');
          } else {
            tryNext();
          }
        });
      })(i);
    }
  }

  tryNext();
};
```

- [ ] **步骤 2: 验证**

启动云版并请求一个简单查询验证：

```bash
cd /Users/tong/kongfz_cloud
python3 app.py &
sleep 1
curl -s 'http://localhost:5000/api/query?isbn=9787108009821' | python3 -m json.tool | head -5
kill %1 2>/dev/null
```

---

### 任务 5: 智能粘贴 ISBN 提取 + 图片上传/OCR（本地版 `kongfz_web.html`）

**文件:** 修改 `kongfz_web.html`
**改动:** 增加粘贴事件监听、OCR 图片上传区域、确认查询条

- [ ] **步骤 1: 增加智能粘贴事件监听（在 `inputArea.addEventListener('keydown', ...)` 之后）**

```javascript
// ── 智能粘贴提取 ISBN ──
var pasteTimer = null;
inputArea.addEventListener('paste', function() {
  clearTimeout(pasteTimer);
  pasteTimer = setTimeout(function() {
    var text = inputArea.value;
    var isbns = [];
    var seen = {};
    text.split(/[\s,，、\n\r]+/).forEach(function(s) {
      s = s.trim().replace(/-/g, '').replace(/ /g, '');
      if (/^\d{10,13}$/.test(s) && !seen[s]) { seen[s] = true; isbns.push(s); }
    });
    if (isbns.length > 0) {
      var lines = text.split(/[\n\r]+/);
      var ignored = 0;
      lines.forEach(function(line) {
        var c = line.trim().replace(/-/g, '').replace(/ /g, '');
        if (c && !/^\d{10,13}$/.test(c)) ignored++;
      });
      showPasteConfirm(isbns.length, ignored);
    }
  }, 100);
});

function showPasteConfirm(count, ignored) {
  var old = document.getElementById('pasteConfirm');
  if (old) old.remove();

  var bar = document.createElement('div');
  bar.id = 'pasteConfirm';
  bar.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:10px;padding:10px 12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;font-size:.85rem';
  bar.innerHTML = '<span>📋</span><span style="flex:1">识别到 <strong>' + count + '</strong> 个 ISBN' +
    (ignored > 0 ? '<span style="color:#94a3b8;font-size:.78rem;margin-left:6px">（忽略 ' + ignored + ' 行）</span>' : '') +
    '</span>' +
    '<button onclick="confirmPasteQuery()" style="padding:8px 18px;border-radius:8px;border:none;background:#2563eb;color:#fff;font-weight:600;cursor:pointer;font-size:.85rem">🔍 立即查价</button>' +
    '<button onclick="dismissPasteConfirm()" style="padding:8px 10px;border-radius:8px;border:none;background:transparent;color:#94a3b8;cursor:pointer;font-size:.8rem">✕</button>';

  var card = inputArea.closest('.card');
  if (card) card.appendChild(bar);
}

function confirmPasteQuery() {
  var bar = document.getElementById('pasteConfirm');
  if (bar) bar.remove();
  btnQuery.click();
}

function dismissPasteConfirm() {
  var bar = document.getElementById('pasteConfirm');
  if (bar) bar.remove();
}
```

- [ ] **步骤 2: 在输入区下方增加 OCR 图片上传区域**

在输入区 `.card` 内部、`<div class="row">` 之后增加：

```html
<!-- OCR 图片上传 -->
<div id="ocrArea" style="margin-top:12px;border:2px dashed #cbd5e1;border-radius:10px;padding:16px;text-align:center;cursor:pointer;transition:all .2s"
     ondragover="this.style.borderColor='#3b82f6';this.style.background='#eff6ff';return false"
     ondragleave="this.style.borderColor='#cbd5e1';this.style.background='';return false"
     ondrop="handleOcrDrop(event);return false"
     onclick="document.getElementById('ocrInput').click()">
  <div style="font-size:1.5rem;margin-bottom:4px">📷</div>
  <div style="font-size:.85rem;color:#64748b">点击上传或拖拽书单截图，自动识别 ISBN</div>
  <div style="font-size:.72rem;color:#94a3b8;margin-top:4px">支持 JPG / PNG / HEIC</div>
  <input type="file" id="ocrInput" accept="image/*" multiple
         style="display:none" onchange="handleOcrFiles(this.files)">
  <div id="ocrStatus" style="display:none;margin-top:8px;font-size:.82rem"></div>
</div>
```

- [ ] **步骤 3: 增加 OCR 上传处理的 JavaScript**

在 `<script>` 底部增加：

```javascript
// ── OCR 图片识别 ISBN ──
function handleOcrDrop(e) {
  e.preventDefault();
  document.getElementById('ocrArea').style.borderColor = '#cbd5e1';
  document.getElementById('ocrArea').style.background = '';
  var files = e.dataTransfer.files;
  if (files.length > 0) handleOcrFiles(files);
}

function handleOcrFiles(files) {
  var statusEl = document.getElementById('ocrStatus');
  statusEl.style.display = 'block';
  statusEl.innerHTML = '⏳ 正在识别 ' + files.length + ' 张图片...';
  statusEl.style.color = '#3b82f6';

  var pending = files.length;
  var allIsbns = [];

  function processFile(i) {
    if (i >= files.length) {
      if (allIsbns.length > 0) {
        statusEl.innerHTML = '✅ 识别到 <strong>' + allIsbns.length + '</strong> 个 ISBN，已填入输入框';
        statusEl.style.color = '#059669';
        // 追加到输入框
        var existing = inputArea.value.trim();
        var newVal = allIsbns.join('\n');
        inputArea.value = existing ? existing + '\n' + newVal : newVal;
        // 显示确认条
        showPasteConfirm(allIsbns.length, 0);
      } else {
        statusEl.innerHTML = '⚠️ 未识别到 ISBN，请检查图片是否清晰包含 ISBN 数字';
        statusEl.style.color = '#d97706';
      }
      return;
    }

    var file = files[i];
    // 校验格式
    if (!file.type.startsWith('image/')) {
      pending--;
      processFile(i + 1);
      return;
    }

    var formData = new FormData();
    formData.append('image', file);

    fetch('/api/ocr', { method: 'POST', body: formData })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        pending--;
        if (d.isbns && d.isbns.length > 0) {
          d.isbns.forEach(function(isbn) {
            if (allIsbns.indexOf(isbn) === -1) allIsbns.push(isbn);
          });
          statusEl.innerHTML = '⏳ 识别中... 已提取 ' + allIsbns.length + ' 个 ISBN（' + (files.length - pending) + '/' + files.length + '）';
        }
        processFile(i + 1);
      })
      .catch(function() {
        pending--;
        processFile(i + 1);
      });
  }

  processFile(0);
}
```

- [ ] **步骤 4: 增加手机扫码按钮**

在输入区的 `.row` 中的"清空"按钮之后增加扫码按钮：

```html
<button id="btnScan" onclick="scanBarcode()" style="padding:10px 14px;border-radius:8px;border:1px solid #e2e8f0;background:transparent;color:#64748b;cursor:pointer;font-size:.85rem;display:none">📷 扫码</button>
```

在 JavaScript 末尾增加：

```javascript
// ── 手机扫码 ──
(function() {
  if ('BarcodeDetector' in window) {
    document.getElementById('btnScan').style.display = '';
  }
})();

function scanBarcode() {
  if (!('BarcodeDetector' in window)) {
    toast('当前浏览器不支持扫码功能');
    return;
  }
  var btn = document.getElementById('btnScan');
  btn.textContent = '⏳ 正在打开摄像头...';
  btn.disabled = true;

  try {
    var barcodeDetector = new BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'isbn_13', 'isbn_10'] });
  } catch(e) {
    btn.textContent = '📷 扫码';
    btn.disabled = false;
    toast('扫码初始化失败');
    return;
  }

  // 创建视频元素
  var video = document.createElement('video');
  video.style.cssText = 'max-width:100%;border-radius:10px;margin-top:10px';
  video.setAttribute('playsinline', '');
  video.setAttribute('autoplay', '');

  var scanContainer = document.createElement('div');
  scanContainer.id = 'scanContainer';
  scanContainer.style.cssText = 'margin-top:8px;text-align:center';
  scanContainer.appendChild(video);

  var cancelBtn = document.createElement('button');
  cancelBtn.textContent = '✕ 关闭扫码';
  cancelBtn.style.cssText = 'margin-top:8px;padding:6px 16px;border-radius:6px;border:none;background:#e2e8f0;color:#64748b;cursor:pointer;font-size:.8rem';
  cancelBtn.onclick = stopScan;
  scanContainer.appendChild(cancelBtn);

  var inputCard = inputArea.closest('.card');
  if (inputCard) inputCard.appendChild(scanContainer);

  var stream = null;

  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    .then(function(s) {
      stream = s;
      video.srcObject = s;
      video.play();

      // 循环检测条码
      var scanTimer = setInterval(function() {
        if (!stream) { clearInterval(scanTimer); return; }
        barcodeDetector.detect(video)
          .then(function(barcodes) {
            if (barcodes.length > 0) {
              var code = barcodes[0].rawValue.replace(/-/g, '');
              if (/^\d{10,13}$/.test(code)) {
                stopScan();
                inputArea.value = (inputArea.value.trim() ? inputArea.value.trim() + '\n' : '') + code;
                toast('✅ 扫码成功: ' + code);
                setTimeout(function() { btnQuery.click(); }, 500);
              }
            }
          })
          .catch(function() {});
      }, 500);
    })
    .catch(function() {
      btn.textContent = '📷 扫码';
      btn.disabled = false;
      toast('无法打开摄像头，请确保有摄像头权限');
      stopScan();
    });

  function stopScan() {
    if (stream) { stream.getTracks().forEach(function(t) { t.stop(); }); stream = null; }
    var container = document.getElementById('scanContainer');
    if (container) container.remove();
    btn.textContent = '📷 扫码';
    btn.disabled = false;
  }
}
```

---

### 任务 6: 智能粘贴 + 图片上传/OCR + 扫码（云版 `kongfz_cloud/index.html`）

**文件:** 修改 `kongfz_cloud/index.html`
**说明:** 与任务 5 完全相同语法和逻辑，适配云版 HTML 结构差异

- [ ] **步骤 1: 增加智能粘贴事件监听（代码与任务 5 步骤 1 相同）**

找到 `inputArea.addEventListener('keydown', ...)`（约第 909 行），在其后增加粘贴监听。

```javascript
// ── 智能粘贴提取 ISBN ──
var pasteTimer = null;
inputArea.addEventListener('paste', function() {
  clearTimeout(pasteTimer);
  pasteTimer = setTimeout(function() {
    var text = inputArea.value;
    var isbns = [];
    var seen = {};
    text.split(/[\s,，、\n\r]+/).forEach(function(s) {
      s = s.trim().replace(/-/g, '').replace(/ /g, '');
      if (/^\d{10,13}$/.test(s) && !seen[s]) { seen[s] = true; isbns.push(s); }
    });
    if (isbns.length > 0) {
      var lines = text.split(/[\n\r]+/);
      var ignored = 0;
      lines.forEach(function(line) {
        var c = line.trim().replace(/-/g, '').replace(/ /g, '');
        if (c && !/^\d{10,13}$/.test(c)) ignored++;
      });
      showPasteConfirm(isbns.length, ignored);
    }
  }, 100);
});

function showPasteConfirm(count, ignored) {
  var old = document.getElementById('pasteConfirm');
  if (old) old.remove();

  var bar = document.createElement('div');
  bar.id = 'pasteConfirm';
  bar.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:10px;padding:10px 12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;font-size:.85rem';
  bar.innerHTML = '<span>📋</span><span style="flex:1">识别到 <strong>' + count + '</strong> 个 ISBN' +
    (ignored > 0 ? '<span style="color:#94a3b8;font-size:.78rem;margin-left:6px">（忽略 ' + ignored + ' 行）</span>' : '') +
    '</span>' +
    '<button onclick="confirmPasteQuery()" style="padding:8px 18px;border-radius:8px;border:none;background:#2563eb;color:#fff;font-weight:600;cursor:pointer;font-size:.85rem">🔍 立即查价</button>' +
    '<button onclick="dismissPasteConfirm()" style="padding:8px 10px;border-radius:8px;border:none;background:transparent;color:#94a3b8;cursor:pointer;font-size:.8rem">✕</button>';

  var card = inputArea.closest('.card');
  if (card) card.appendChild(bar);
}

function confirmPasteQuery() {
  var bar = document.getElementById('pasteConfirm');
  if (bar) bar.remove();
  btnQuery.click();
}

function dismissPasteConfirm() {
  var bar = document.getElementById('pasteConfirm');
  if (bar) bar.remove();
}
```

- [ ] **步骤 2: 在输入区下方增加 OCR 图片上传区域**

在当前 HTML 的 `</div><!-- 主要输入区结束 -->` 之前、`<div id="status">` 之后增加：

```html
<!-- OCR 图片上传 -->
<div id="ocrArea" style="margin-top:12px;border:2px dashed #cbd5e1;border-radius:10px;padding:16px;text-align:center;cursor:pointer;transition:all .2s"
     ondragover="this.style.borderColor='#2563eb';this.style.background='#eff6ff';return false"
     ondragleave="this.style.borderColor='#cbd5e1';this.style.background='';return false"
     ondrop="handleOcrDrop(event);return false"
     onclick="document.getElementById('ocrInput').click()">
  <div style="font-size:1.5rem;margin-bottom:4px">📷</div>
  <div style="font-size:.85rem;color:#64748b">点击上传或拖拽书单截图，自动识别 ISBN</div>
  <div style="font-size:.72rem;color:#94a3b8;margin-top:4px">支持 JPG / PNG / HEIC</div>
  <input type="file" id="ocrInput" accept="image/*" multiple
         style="display:none" onchange="handleOcrFiles(this.files)">
  <div id="ocrStatus" style="display:none;margin-top:8px;font-size:.82rem"></div>
</div>
```

- [ ] **步骤 3: 增加 OCR 上传处理的 JavaScript（代码与任务 5 步骤 3 相同）**

```javascript
// ── OCR 图片识别 ISBN ──
function handleOcrDrop(e) {
  e.preventDefault();
  document.getElementById('ocrArea').style.borderColor = '#cbd5e1';
  document.getElementById('ocrArea').style.background = '';
  var files = e.dataTransfer.files;
  if (files.length > 0) handleOcrFiles(files);
}

function handleOcrFiles(files) {
  var statusEl = document.getElementById('ocrStatus');
  statusEl.style.display = 'block';
  statusEl.innerHTML = '⏳ 正在识别 ' + files.length + ' 张图片...';
  statusEl.style.color = '#2563eb';

  var pending = files.length;
  var allIsbns = [];

  function processFile(i) {
    if (i >= files.length) {
      if (allIsbns.length > 0) {
        statusEl.innerHTML = '✅ 识别到 <strong>' + allIsbns.length + '</strong> 个 ISBN，已填入输入框';
        statusEl.style.color = '#059669';
        var existing = inputArea.value.trim();
        var newVal = allIsbns.join('\n');
        inputArea.value = existing ? existing + '\n' + newVal : newVal;
        showPasteConfirm(allIsbns.length, 0);
      } else {
        statusEl.innerHTML = '⚠️ 未识别到 ISBN，请检查图片是否清晰包含 ISBN 数字';
        statusEl.style.color = '#d97706';
      }
      return;
    }

    var file = files[i];
    if (!file.type.startsWith('image/')) {
      pending--;
      processFile(i + 1);
      return;
    }

    var formData = new FormData();
    formData.append('image', file);

    fetch('/api/ocr', { method: 'POST', body: formData })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        pending--;
        if (d.isbns && d.isbns.length > 0) {
          d.isbns.forEach(function(isbn) {
            if (allIsbns.indexOf(isbn) === -1) allIsbns.push(isbn);
          });
          statusEl.innerHTML = '⏳ 识别中... 已提取 ' + allIsbns.length + ' 个 ISBN（' + (files.length - pending) + '/' + files.length + '）';
        }
        processFile(i + 1);
      })
      .catch(function() {
        pending--;
        processFile(i + 1);
      });
  }

  processFile(0);
}
```

- [ ] **步骤 4: 增加手机扫码按钮**

在当前 HTML 的"清空"按钮旁增加扫码按钮（云版已用 `btn-outline` 类，保持一致）：

```html
<button class="btn btn-outline" id="btnScan" onclick="scanBarcode()" style="display:none">📷 扫码</button>
```

在 JavaScript 末尾增加扫码逻辑（代码与任务 5 步骤 4 相同，但使用云版的 toast 函数）：

```javascript
// ── 手机扫码 ──
(function() {
  if ('BarcodeDetector' in window) {
    document.getElementById('btnScan').style.display = '';
  }
})();

function scanBarcode() {
  if (!('BarcodeDetector' in window)) {
    toast('当前浏览器不支持扫码功能');
    return;
  }
  var btn = document.getElementById('btnScan');
  btn.textContent = '⏳ 正在打开摄像头...';
  btn.disabled = true;

  try {
    var barcodeDetector = new BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'isbn_13', 'isbn_10'] });
  } catch(e) {
    btn.textContent = '📷 扫码';
    btn.disabled = false;
    toast('扫码初始化失败');
    return;
  }

  var video = document.createElement('video');
  video.style.cssText = 'max-width:100%;border-radius:10px;margin-top:10px';
  video.setAttribute('playsinline', '');
  video.setAttribute('autoplay', '');

  var scanContainer = document.createElement('div');
  scanContainer.id = 'scanContainer';
  scanContainer.style.cssText = 'margin-top:8px;text-align:center';
  scanContainer.appendChild(video);

  var cancelBtn = document.createElement('button');
  cancelBtn.textContent = '✕ 关闭扫码';
  cancelBtn.style.cssText = 'margin-top:8px;padding:6px 16px;border-radius:6px;border:none;background:#e2e8f0;color:#64748b;cursor:pointer;font-size:.8rem';
  cancelBtn.onclick = stopScan;
  scanContainer.appendChild(cancelBtn);

  var inputCard = inputArea.closest('.card');
  if (inputCard) inputCard.appendChild(scanContainer);

  var stream = null;

  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    .then(function(s) {
      stream = s;
      video.srcObject = s;
      video.play();

      var scanTimer = setInterval(function() {
        if (!stream) { clearInterval(scanTimer); return; }
        barcodeDetector.detect(video)
          .then(function(barcodes) {
            if (barcodes.length > 0) {
              var code = barcodes[0].rawValue.replace(/-/g, '');
              if (/^\d{10,13}$/.test(code)) {
                stopScan();
                inputArea.value = (inputArea.value.trim() ? inputArea.value.trim() + '\n' : '') + code;
                toast('✅ 扫码成功: ' + code);
                setTimeout(function() { btnQuery.click(); }, 500);
              }
            }
          })
          .catch(function() {});
      }, 500);
    })
    .catch(function() {
      btn.textContent = '📷 扫码';
      btn.disabled = false;
      toast('无法打开摄像头，请确保有摄像头权限');
      stopScan();
    });

  function stopScan() {
    if (stream) { stream.getTracks().forEach(function(t) { t.stop(); }); stream = null; }
    var container = document.getElementById('scanContainer');
    if (container) container.remove();
    btn.textContent = '📷 扫码';
    btn.disabled = false;
  }
}
```

---

### 任务 7: 整体验证

- [ ] **步骤 1: 测试智能粘贴**

启动服务 → 粘贴 `9787108009821 帮我查下价格 9787020002207` → 确认弹出识别到 2 个 ISBN → 点"立即查价"

- [ ] **步骤 2: 测试并行查价**

输入 15 个不同的 ISBN → 查价 → 观察进度列表从 0/15 快速推进到 15/15，应在 ~10 秒内完成

- [ ] **步骤 3: 测试 OCR 识别**

```bash
# 创建一个简单的测试图片
python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (400, 100), 'white')
draw = ImageDraw.Draw(img)
draw.text((20, 30), 'ISBN 9787108009821', fill='black')
img.save('/tmp/test_isbn.png')
"
```

上传该图片 → 应识别出 `9787108009821`

- [ ] **步骤 4: 测试扫码**

在手机上打开云版 → 点扫码按钮 → 扫描任意书背条形码 → 自动填入 ISBN 并查价

- [ ] **步骤 5: 回归测试已有功能**

- 历史记录保存/查看/删除
- 一键加购/批量加购
- 品相筛选
- Cookie 设置/验证
