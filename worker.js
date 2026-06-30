// ============================================================
//  孔夫子 ISBN 查价 · Cloudflare Worker
//  零服务器，永久免费，手机可用
// ============================================================

// ── KV 命名空间绑定（在 Cloudflare Dashboard 中设置）──
// KV 名称: KONGFZ_PRICE

// ── HTML 前端 ──────────────────────────────────────────────

const HTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#2563eb">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>孔夫子 ISBN 查价</title>
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.svg">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f1f5f9;color:#1e293b;padding:16px 12px 80px;min-height:100vh;-webkit-tap-highlight-color:transparent}
.container{max-width:960px;margin:0 auto}
.header{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.header h1{font-size:1.25rem;font-weight:700;background:linear-gradient(135deg,#2563eb,#1d4ed8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .badge{font-size:.65rem;color:#64748b;background:#e2e8f0;padding:2px 8px;border-radius:10px;font-weight:500;-webkit-text-fill-color:#64748b}
.subtitle{color:#64748b;font-size:.8rem;margin-bottom:16px;line-height:1.4}
.card{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:14px}
.card-title{font-size:1rem;font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:6px}
textarea{width:100%;padding:12px;border:1px solid #e2e8f0;border-radius:10px;font-size:.9rem;min-height:90px;outline:none;font-family:inherit;line-height:1.6;resize:vertical}
textarea:focus{border-color:#3b82f6;box-shadow:0 0 0 3px #dbeafe}
.row{display:flex;gap:10px;margin-top:12px;align-items:center;flex-wrap:wrap}
.btn{-webkit-appearance:none;appearance:none;padding:12px 24px;border-radius:10px;border:none;font-weight:600;cursor:pointer;font-size:.9rem;transition:all .1s;touch-action:manipulation;user-select:none}
.btn:active{transform:scale(.97)}
.btn-primary{background:#2563eb;color:#fff}.btn-primary:disabled{background:#93c5fd;cursor:not-allowed}
.btn-outline{background:transparent;border:1.5px solid #cbd5e1;color:#64748b}
.btn-save{background:#f59e0b;color:#fff;padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:.85rem}
select{-webkit-appearance:none;appearance:none;padding:11px 32px 11px 12px;border:1px solid #e2e8f0;border-radius:10px;font-size:.85rem;background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E") no-repeat right 10px center;outline:none;min-width:120px}
#status{font-size:.82rem;color:#64748b;padding:4px 0}
.status-loading{color:#2563eb}.status-done{color:#059669}.status-error{color:#dc2626}
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}
.s-card{text-align:center;padding:10px 6px;border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0}
.s-card .n{font-size:1.2rem;font-weight:700}.s-card .l{font-size:.68rem;color:#64748b;margin-top:3px}
.s-blue .n{color:#2563eb}.s-green .n{color:#059669}.s-amber .n{color:#d97706}
.result-box{border:2px solid #059669;border-radius:12px;padding:14px;margin-bottom:14px;background:linear-gradient(135deg,#f0fdf4,#ecfdf5)}
.result-box .book-title{font-size:1rem;font-weight:700;color:#065f46;line-height:1.4;word-break:break-all}
.result-box .meta{font-size:.72rem;color:#64748b;margin-top:3px}
.empty-state{text-align:center;color:#94a3b8;padding:40px 20px;font-size:.88rem}
.table-wrap{overflow-x:auto;margin:8px -4px 0;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:.8rem;min-width:480px}
thead{background:#f8fafc}
th{padding:7px 6px;text-align:left;font-weight:600;white-space:nowrap;border-bottom:2px solid #e2e8f0;font-size:.75rem;color:#64748b}
td{padding:7px 6px;border-bottom:1px solid #e2e8f0;white-space:nowrap}
.btn-cart-all{display:inline-flex;align-items:center;gap:4px;padding:10px 20px;border-radius:8px;border:none;background:#059669;color:#fff;font-size:.88rem;font-weight:600;cursor:pointer}
.btn-cart{display:inline-flex;align-items:center;gap:3px;padding:6px 12px;border-radius:6px;border:1px solid #3b82f6;background:transparent;color:#3b82f6;font-size:.78rem;cursor:pointer}
.btn-batch-cart{display:block;width:100%;padding:14px;border-radius:10px;border:none;background:#dc2626;color:#fff;font-size:1rem;font-weight:700;cursor:pointer;box-shadow:0 2px 8px rgba(220,38,38,.25)}
.btn-batch-cart:disabled{background:#fca5a5;cursor:not-allowed;box-shadow:none}
.fail-chip{display:inline-flex;align-items:center;gap:4px;padding:7px 14px;border:1px solid #fca5a5;border-radius:20px;font-size:.78rem;background:#fff;cursor:pointer;color:#dc2626}
.save-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px;padding:12px;background:#fffbeb;border:1px solid #fde68a;border-radius:10px}
.save-bar input{flex:1;min-width:140px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:.85rem;outline:none}
.history-header{display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none}
.history-header .toggle{font-size:.8rem;color:#94a3b8;transition:transform .25s}
.history-header .toggle.open{transform:rotate(90deg)}
.history-body{max-height:0;overflow:hidden;transition:max-height .3s ease}
.history-body.open{max-height:2000px}
.history-item{display:flex;justify-content:space-between;align-items:center;padding:12px;border:1px solid #e2e8f0;border-radius:10px;margin-top:8px;flex-wrap:wrap;gap:8px}
.history-item .info{flex:1;min-width:140px}
.history-item .name{font-weight:500;font-size:.85rem}
.history-item .meta{font-size:.72rem;color:#64748b;margin-top:2px}
.history-item .actions{display:flex;gap:6px;flex-wrap:wrap}
.history-item .actions button{padding:8px 14px;border-radius:8px;border:none;font-size:.78rem;font-weight:500;cursor:pointer}
.btn-h-query{background:#2563eb;color:#fff}
.btn-h-cart{background:#dc2626;color:#fff}
.btn-h-del{background:transparent;border:1px solid #e2e8f0!important;color:#94a3b8}
#cookieCard{border:2px solid #fde68a}
#cookieBar{transition:all .2s;cursor:pointer}
#cookieBar.valid{border-color:#86efac;background:#f0fdf4}
#cookieBar.invalid{border-color:#fca5a5;background:#fef2f2;border-width:2px}
#cookieBar.warning{border-color:#fde68a;background:#fffbeb;border-width:2px}
.install-banner{display:none;align-items:center;gap:10px;padding:10px 14px;background:#2563eb;color:#fff;border-radius:10px;margin-bottom:14px;font-size:.82rem;font-weight:500}
.install-banner .close-btn{margin-left:auto;background:rgba(255,255,255,.2);border:none;color:#fff;width:26px;height:26px;border-radius:50%;font-size:14px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #e2e8f0;display:flex;padding:8px 12px;justify-content:space-around;z-index:100;padding-bottom:max(8px,env(safe-area-inset-bottom))}
.bottom-nav button{display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 12px;border:none;background:transparent;color:#64748b;font-size:.7rem;cursor:pointer}
.bottom-nav button svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#1e293b;color:#fff;padding:10px 20px;border-radius:10px;font-size:.82rem;z-index:300;opacity:0;transition:opacity .25s;pointer-events:none}
.toast.show{opacity:1}
@media(min-width:640px){body{padding:24px 20px 24px}.bottom-nav{display:none}.header h1{font-size:1.4rem}}
</style>
</head>
<body>
<div class="container">
  <div class="header"><h1>📚 孔夫子查价</h1><span class="badge">☁️</span></div>
  <p class="subtitle">批量查 ISBN 在孔夫子旧书网的最低进货价，支持一键加购</p>
  <div class="install-banner" id="installBanner"><span>📲 添加到主屏幕，像 App 一样使用</span><button class="close-btn" onclick="dismissInstallBanner()">✕</button></div>
  <div class="card">
    <div class="card-title">📖 输入 ISBN（每行一个）</div>
    <textarea id="inputArea" placeholder="9787108009821&#10;9787020002207" enterkeyhint="done"></textarea>
    <div class="row">
      <label style="font-size:.82rem;color:#64748b;display:flex;align-items:center;gap:4px">📦
        <select id="qualitySelect">
          <option value="">不限品相</option>
          <option value="100~100">全新</option>
          <option value="95~100">九五品及以上</option>
          <option value="90~100">九品及以上</option>
          <option value="85~100">八五品及以上</option>
          <option value="80~100">八品及以上</option>
          <option value="70~100">七品及以上</option>
        </select>
      </label>
      <button class="btn btn-primary" id="btnQuery">🔍 查最低价</button>
      <button class="btn btn-outline" id="btnClear" style="padding:12px 16px">清空</button>
      <button class="btn btn-outline" id="btnScan" onclick="scanBarcode()" style="display:none">📷 扫码</button>
    </div>
    <div id="status">就绪</div>
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
  </div>
  <div id="cookieBar" class="card" style="display:none;padding:12px 16px;border-radius:10px" onclick="toggleCookie()">
    <div style="display:flex;align-items:center;gap:10px;font-size:.85rem">
      <span>🍪</span>
      <span id="cookieBarIcon" style="font-size:1rem">🟢</span>
      <span id="cookieBarText" style="flex:1">加载中...</span>
      <span id="cookieBarAction" style="font-size:.75rem;padding:6px 14px;border-radius:8px;background:#f1f5f9;color:#64748b;white-space:nowrap">设置 →</span>
    </div>
  </div>
  <div class="card" id="cookieCard">
    <div class="history-header" onclick="toggleCookie()">
      <div class="card-title" style="margin-bottom:0">🍪 Cookie 设置</div>
      <span><span id="cookieStatusBadge" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#94a3b8;margin-right:6px"></span><span class="toggle" id="cookieToggle">▶</span></span>
    </div>
    <div class="history-body" id="cookieBody">
      <div style="margin-top:8px;font-size:.82rem;color:#475569;line-height:1.7">
        <div id="cookieStatus" style="margin-bottom:10px;padding:10px 14px;border-radius:8px;background:#f8fafc;font-size:.82rem;border:1px solid #e2e8f0">正在检查 Cookie 状态...</div>
        <details style="margin-bottom:10px;background:#eff6ff;border-radius:8px;padding:10px 14px;border:1px solid #bfdbfe">
          <summary style="font-weight:600;font-size:.82rem;color:#2563eb;cursor:pointer">📱 手机如何获取 Cookie？</summary>
          <div style="margin-top:8px;font-size:.78rem;color:#475569;line-height:1.8">
            <p><strong>方法一（手机直接操作）：</strong></p>
            <ol style="margin:4px 0 8px 16px">
              <li>在手机 Safari/Chrome 打开 <strong>kongfz.com</strong> 并登录</li>
              <li>在地址栏输入 <code style="background:#e2e8f0;padding:1px 6px;border-radius:4px;font-size:.75rem;word-break:break-all">javascript:prompt('复制 Cookie',document.cookie)</code> 并回车</li>
              <li>全选弹窗里的文本 → 复制 → 粘贴到下方输入框</li>
            </ol>
            <p><strong>方法二（电脑/手机配合）：</strong></p>
            <ol style="margin:4px 0 0 16px">
              <li>电脑登录 kongfz.com，F12 → Network → 点请求 → 复制 Cookie</li>
              <li>发送到手机，粘贴到下方</li>
            </ol>
          </div>
        </details>
        <p style="margin-bottom:8px;color:#64748b">粘贴 Cookie 字符串或 cURL 命令（自动识别）：</p>
        <textarea id="cookieInput" placeholder="在此粘贴 Cookie 字符串&#10;或 cURL 命令中的 Cookie 值" style="width:100%;min-height:70px;padding:10px;border:1px solid #e2e8f0;border-radius:8px;font-size:.78rem;font-family:monospace;outline:none;resize:vertical"></textarea>
        <div class="row">
          <button class="btn btn-primary" id="btnSaveCookie" onclick="saveCookie()" style="background:#f59e0b">💾 保存 Cookie</button>
          <span id="cookieMsg" style="font-size:.82rem;flex:1"></span>
        </div>
      </div>
    </div>
  </div>
  <div class="card" id="historyCard">
    <div class="history-header" onclick="toggleHistory()">
      <div class="card-title" style="margin-bottom:0">📋 历史记录</div>
      <span class="toggle" id="historyToggle">▶</span>
    </div>
    <div class="history-body" id="historyBody">
      <div id="historyList" style="margin-top:8px"><div style="text-align:center;color:#94a3b8;font-size:.85rem;padding:16px" id="historyEmpty">暂无记录</div></div>
    </div>
  </div>
  <div id="results"></div>
  <div id="empty" class="empty-state">📝 输入 ISBN 后点「查最低价」</div>
</div>
<div class="bottom-nav">
  <button onclick="scrollToTop()"><svg viewBox="0 0 24 24"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg><span>回到顶部</span></button>
  <button onclick="toggleCookie()"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="8" r="1.5" fill="currentColor"/><circle cx="8" cy="12" r="1.5" fill="currentColor"/><circle cx="15" cy="13" r="1.5" fill="currentColor"/></svg><span>Cookie</span></button>
  <button onclick="toggleHistory()"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span>历史</span></button>
</div>
<div class="toast" id="toast"></div>
<script>
var isRunning=false,lastResults=[];
var inputArea=document.getElementById('inputArea'),statusEl=document.getElementById('status'),resultsEl=document.getElementById('results'),emptyEl=document.getElementById('empty'),btnQuery=document.getElementById('btnQuery');
function setStatus(t,c){statusEl.textContent=t;statusEl.className=c?'status-'+c:''}
function toast(m,d){var e=document.getElementById('toast');e.textContent=m;e.classList.add('show');clearTimeout(e._timer);e._timer=setTimeout(function(){e.classList.remove('show')},d||2000)}
function scrollToTop(){window.scrollTo({top:0,behavior:'smooth'})}
var deferredPrompt=null;
window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();deferredPrompt=e;var b=document.getElementById('installBanner');if(!localStorage.getItem('pwaInstallDismissed'))b.style.display='flex'});
function dismissInstallBanner(){document.getElementById('installBanner').style.display='none';localStorage.setItem('pwaInstallDismissed','1')}
document.getElementById('installBanner').addEventListener('click',function(e){if(e.target.tagName==='BUTTON'||!deferredPrompt)return;deferredPrompt.prompt()});
if('serviceWorker'in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){})}
document.getElementById('btnClear').onclick=function(){inputArea.value='';resultsEl.innerHTML='';emptyEl.style.display='block';setStatus('就绪','')};
function queryIsbn(isbn){var q=document.getElementById('qualitySelect').value;var u='/api/query?isbn='+encodeURIComponent(isbn);if(q)u+='&quality='+encodeURIComponent(q);return fetch(u).then(function(r){return r.json()}).catch(function(){return{isbn:isbn,error:'请求失败'}})}
btnQuery.onclick=function(){if(isRunning)return;var t=inputArea.value.trim();if(!t){setStatus('请输入ISBN','error');return}
var isbns=[],seen={};t.split(/[\s,，、\n]+/).forEach(function(s){s=s.trim().replace(/-/g,'');if(/^\\d{8,13}$/.test(s)&&!seen[s]){seen[s]=true;isbns.push(s)}});if(!isbns.length){setStatus('没有有效的ISBN','error');return}
isRunning=true;btnQuery.disabled=true;emptyEl.style.display='none';resultsEl.innerHTML='';setStatus('⏳并行查询'+isbns.length+'本...(并发6)','loading')
var ph='<div class="summary"><div class="s-card s-blue"><div class="n">0/'+isbns.length+'</div><div class="l">进度</div></div><div class="s-card s-green"><div class="n">0</div><div class="l">查到</div></div><div class="s-card s-amber"><div class="n">0</div><div class="l">异常</div></div></div>';resultsEl.innerHTML=ph
var allData=[],okC=0,failC=0,CONC=6,idx=0,pend=0,done=0
function up(){var c=resultsEl.querySelectorAll('.summary .s-card .n');if(c.length>=3){c[0].textContent=done+'/'+isbns.length;c[1].textContent=okC;c[2].textContent=failC}}
function nx(){while(pend<CONC&&idx<isbns.length){var i=idx++;pend++;(function(i){setStatus('⏳查询'+(i+1)+'/'+isbns.length+': '+isbns[i],'loading');queryIsbn(isbns[i]).then(function(d){allData.push(d);done++;pend--;if(d.cheapest)okC++;if(d.error)failC++;up();if(done>=isbns.length){lastResults=allData;showResults(allData);isRunning=false;btnQuery.disabled=false;var ot=allData.filter(function(r){return!r.error}).length;setStatus('✅查询完成！共'+allData.length+'本,查到'+ot+'本','done')}else{nx()}})})(i)}}nx()}
function esc(s){return(s||'').replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})}
function showResults(data){var ok=data.filter(function(r){return!r.error}),priced=ok.filter(function(r){return r.cheapest}),fails=data.filter(function(r){return r.error}),html='';if(fails.length>0){var ft='';fails.forEach(function(r){ft+=r.isbn+'  '+(r.error||'')+'\\n'})
html+='<div class="card" style="border:2px solid #ef4444;background:#fef2f2;margin-bottom:14px"><div class="card-title" style="color:#dc2626;font-size:.9rem">⚠️ 异常 '+fails.length+' 个</div><div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">'
for(var fi=0;fi<fails.length;fi++){var f=fails[fi];html+='<span class="fail-chip" onclick="reQueryFailed(\\''+f.isbn+'\\')">🔍 '+f.isbn+' <span style="color:#fca5a5;font-size:.7rem">('+esc(f.error||'')+')</span></span>'}
html+='</div><div class="row"><button class="btn btn-primary" onclick="reQueryAllFailed()" style="background:#dc2626;font-size:.85rem">🔍 重新查询全部异常</button><button class="btn btn-outline" onclick="copyFailText(\\''+esc(ft)+'\\')" style="border-color:#ef4444;color:#ef4444;font-size:.85rem">📋 复制异常列表</button></div></div>'}
var tc=0;priced.forEach(function(r){tc+=r.cheapest.total});html+='<div class="summary"><div class="s-card s-blue"><div class="n">'+data.length+'</div><div class="l">查询</div></div><div class="s-card s-green"><div class="n">'+ok.length+'</div><div class="l">查到</div></div><div class="s-card s-amber"><div class="n">'+(data.length-ok.length)+'</div><div class="l">异常</div></div></div>'
if(priced.length){html+='<div style="text-align:center;margin-bottom:14px"><div style="font-size:.75rem;color:#64748b;margin-bottom:6px">最低进货总价</div><div style="font-size:1.5rem;font-weight:800;color:#059669">¥'+tc.toFixed(1)+'</div><button id="btnBatchCart" class="btn-batch-cart" style="margin-top:10px" onclick="batchAddAll()">🛒 一键加购最低价 '+priced.length+' 本</button></div>'}
for(var i=0;i<data.length;i++){var r=data[i];if(r.error){html+='<div class="card" style="border-left:4px solid #ef4444"><div style="font-family:monospace;font-size:.8rem;color:#94a3b8">'+esc(r.isbn)+'</div><div style="color:#ef4444;font-size:.85rem;margin-top:4px">'+esc(r.error)+'</div></div>'}else if(r.cheapest){var cp=r.cheapest;html+='<div class="result-box"><div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:6px"><div class="book-title">'+esc(r.title)+'</div><span style="font-size:.7rem;color:#94a3b8;white-space:nowrap">'+esc(r.isbn)+'</span></div>'+(r.author||r.press?'<div class="meta">'+esc(r.author)+(r.author&&r.press?' · ':'')+esc(r.press)+'</div>':'')
html+='<div style="margin:8px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap"><button class="btn-cart-all" onclick="addToCart('+cp.itemId+','+cp.shopId+',this)">🛒 加购 ¥'+cp.total.toFixed(1)+'</button><span style="font-size:.72rem;color:#64748b">'+esc(cp.shop)+' · '+esc(cp.quality_text)+'</span></div>'
var its=r.top_cheapest||[r.cheapest];html+='<div class="table-wrap"><table><thead><tr><th>#</th><th>店铺</th><th>品相</th><th style="text-align:right">书价</th><th style="text-align:right">运费</th><th style="text-align:right;color:#dc2626">总价</th><th style="text-align:center">操作</th></tr></thead><tbody>'
for(var j=0;j<its.length;j++){var it=its[j];html+='<tr><td>'+(j+1)+'</td><td>'+esc(it.shop)+'</td><td>'+esc(it.quality_text||'—')+'</td><td style="text-align:right">¥'+it.price.toFixed(2)+'</td><td style="text-align:right">¥'+it.shipping.toFixed(1)+'</td><td style="text-align:right"><span'+(j===0?' style="font-weight:600;color:#dc2626"':'')+'>¥'+it.total.toFixed(1)+'</span></td><td style="text-align:center">'+(it.itemId&&it.shopId?'<button class="btn-cart" onclick="addToCart('+it.itemId+','+it.shopId+',this)">🛒</button>':'')+'</td></tr>'}
html+='</tbody></table></div><div style="font-size:.68rem;color:#94a3b8;margin-top:6px">扫描'+(r.pages_scanned||1)+'页 · 在售'+r.total_count+'本</div></div>'}}
resultsEl.innerHTML=html;lastResults=data;setStatus('查询完成！','done')
var sbId='sb_'+Date.now();html='<div class="save-bar" id="'+sbId+'"><span>💾</span><input id="saveNameInput" placeholder="给本次查询起个名字" value=""><button class="btn-save" onclick="saveHistory(\\''+sbId+'\\')">保存</button></div>';resultsEl.insertAdjacentHTML('afterbegin',html)}
function addToCart(iid,sid,btn){var ot=btn.textContent;btn.textContent='⏳';btn.disabled=true;btn.style.opacity='0.5';fetch('/api/addtocart?itemId='+iid+'&shopId='+sid).then(function(r){return r.json()}).then(function(d){if(d.success){btn.textContent='✅';toast('✅ 已加购')}else{btn.textContent='❌';toast('❌ '+(d.error||'加购失败'));setTimeout(function(){btn.textContent=ot;btn.disabled=false;btn.style.opacity='1'},1500)}}).catch(function(){btn.textContent='❌';toast('❌ 网络错误');setTimeout(function(){btn.textContent=ot;btn.disabled=false;btn.style.opacity='1'},1500)})}
function batchAddAll(){var p=lastResults.filter(function(r){return r.cheapest&&r.cheapest.itemId&&r.cheapest.shopId});if(!p.length){toast('没有可加购的商品');return}
var btn=document.getElementById('btnBatchCart');btn.disabled=true;btn.textContent='⏳ 0/'+p.length;var s=0,f=0;function n(idx){if(idx>=p.length){btn.textContent='✅ '+s+'/'+p.length+(f>0?' ('+f+'失败)':'');btn.style.background=s>0?'#059669':'#dc2626';toast('✅ 已加购 '+s+' 本');setTimeout(function(){btn.disabled=false},2000);return}
var r=p[idx];btn.textContent='⏳ '+(idx+1)+'/'+p.length;fetch('/api/addtocart?itemId='+r.cheapest.itemId+'&shopId='+r.cheapest.shopId).then(function(resp){return resp.json()}).then(function(d){if(d.success)s++;else f++;setTimeout(function(){n(idx+1)},1200)}).catch(function(){f++;setTimeout(function(){n(idx+1)},1200)})}
n(0)}
function copyFailText(t){if(navigator.clipboard){navigator.clipboard.writeText(t).then(function(){toast('✅ 已复制')}).catch(function(){fc(t)})}else{fc(t)}}
function fc(t){var ta=document.createElement('textarea');ta.value=t;ta.style.position='fixed';ta.style.left='-9999px';document.body.appendChild(ta);ta.select();try{document.execCommand('copy');toast('✅ 已复制')}catch(e){toast('❌ 复制失败')}document.body.removeChild(ta)}
function reQueryFailed(i){if(isRunning)return;inputArea.value=i;resultsEl.innerHTML='';emptyEl.style.display='none';window.scrollTo({top:0,behavior:'smooth'});setTimeout(function(){btnQuery.click()},300)}
function reQueryAllFailed(){if(isRunning)return;var cs=document.querySelectorAll('.fail-chip');if(!cs.length)return;var bs=[];cs.forEach(function(el){var m=(el.textContent||'').match(/\\d{8,13}/);if(m)bs.push(m[0])});if(!bs.length)return;inputArea.value=bs.join('\\n');resultsEl.innerHTML='';emptyEl.style.display='none';window.scrollTo({top:0,behavior:'smooth'});setTimeout(function(){btnQuery.click()},300)}
function toggleHistory(){var b=document.getElementById('historyBody'),t=document.getElementById('historyToggle');b.classList.toggle('open');t.classList.toggle('open');if(b.classList.contains('open'))loadHistoryList()}
function saveHistory(sbId){var btn=document.querySelector('#'+sbId+' .btn-save');if(!btn)return;var n=document.getElementById('saveNameInput'),name=n?n.value.trim():'';if(!name)name='查询 '+new Date().toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});btn.disabled=true;btn.textContent='⏳';var q=document.getElementById('qualitySelect').value;fetch('/api/history/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,results:lastResults,quality_filter:q})}).then(function(r){return r.json()}).then(function(d){if(d.success){btn.textContent='✅ 已保存';btn.style.background='#059669';document.getElementById('historyBody').classList.add('open');document.getElementById('historyToggle').classList.add('open');loadHistoryList()}else{btn.textContent='❌';setTimeout(function(){btn.disabled=false;btn.textContent='保存';btn.style.background='#f59e0b'},2000)}}).catch(function(){btn.textContent='❌';setTimeout(function(){btn.disabled=false;btn.textContent='保存';btn.style.background='#f59e0b'},2000)})}
function loadHistoryList(){fetch('/api/history/list').then(function(r){return r.json()}).then(function(d){var el=document.getElementById('historyList');if(!d.records||!d.records.length){el.innerHTML='<div style="text-align:center;color:#94a3b8;font-size:.85rem;padding:16px">暂无记录</div>';return}
var html='';for(var i=0;i<d.records.length;i++){var r=d.records[i];html+='<div class="history-item" id="hi_'+r.id+'"><div class="info"><div class="name">'+esc(r.name)+'</div><div class="meta">'+(r.created_at||'')+' · '+r.book_count+'本'+(r.priced_count>0?' · ¥'+r.total_cost.toFixed(1):'')+'</div></div><div class="actions"><button class="btn-h-query" onclick="reQueryHistory(\\''+r.id+'\\')">🔍 重查</button>'+(r.priced_count>0?'<button class="btn-h-cart" onclick="batchCartHistory(\\''+r.id+'\\')">🛒 加购</button>':'')+'<button class="btn-h-del" onclick="deleteHistory(\\''+r.id+'\\')">🗑️</button></div></div>'}
el.innerHTML=html}).catch(function(){})}
function reQueryHistory(id){fetch('/api/history/get?id='+encodeURIComponent(id)).then(function(r){return r.json()}).then(function(rec){if(rec.error||!rec.isbns||!rec.isbns.length){toast('获取记录失败');return}
inputArea.value=rec.isbns.join('\\n');if(rec.quality_filter)document.getElementById('qualitySelect').value=rec.quality_filter;resultsEl.innerHTML='';emptyEl.style.display='none';window.scrollTo({top:0,behavior:'smooth'});setTimeout(function(){btnQuery.click()},300)}).catch(function(){toast('获取记录失败')})}
function batchCartHistory(id){fetch('/api/history/get?id='+encodeURIComponent(id)).then(function(r){return r.json()}).then(function(rec){if(rec.error||!rec.results){toast('获取记录失败');return}
var p=rec.results.filter(function(r){return r.cheapest&&r.cheapest.itemId&&r.cheapest.shopId});if(!p.length){toast('没有可加购的商品');return}
var t=p.length,s=0,f=0;var btn=event&&event.target||document.querySelector('.btn-h-cart');if(btn){btn.disabled=true;btn.textContent='⏳ 0/'+t}
function n(idx){if(idx>=t){if(btn){btn.textContent='✅ '+s+'/'+t+(f>0?' ('+f+'失败)':'');setTimeout(function(){btn.disabled=false},2000)}toast('✅ 已加购 '+s+' 本');return}
var r=p[idx];if(btn)btn.textContent='⏳ '+(idx+1)+'/'+t;fetch('/api/addtocart?itemId='+encodeURIComponent(r.cheapest.itemId)+'&shopId='+encodeURIComponent(r.cheapest.shopId)).then(function(resp){return resp.json()}).then(function(d){if(d.success)s++;else f++;setTimeout(function(){n(idx+1)},1200)}).catch(function(){f++;setTimeout(function(){n(idx+1)},1200)})}
n(0)}).catch(function(){toast('获取记录失败')})}
function deleteHistory(id){if(!confirm('删除这条记录？'))return;fetch('/api/history/delete?id='+encodeURIComponent(id)).then(function(r){return r.json()}).then(function(d){if(d.success){loadHistoryList();toast('已删除')}}).catch(function(){})}
function toggleCookie(){var b=document.getElementById('cookieBody'),t=document.getElementById('cookieToggle');b.classList.toggle('open');t.classList.toggle('open');if(b.classList.contains('open'))checkCookieStatus()}
function updateCookieBar(i){var bar=document.getElementById('cookieBar'),icon=document.getElementById('cookieBarIcon'),text=document.getElementById('cookieBarText'),action=document.getElementById('cookieBarAction');if(!i.has_cookie){bar.style.display='flex';bar.className='card invalid';icon.textContent='🔴';text.textContent='未设置 Cookie';action.textContent='立即设置 →';return}
if(i.is_valid){bar.style.display='flex';bar.className='card valid';icon.textContent='🟢';var d=i.days_since_update||0;if(d>7){text.textContent='Cookie 有效，已 '+d.toFixed(0)+' 天';bar.className='card warning';icon.textContent='🟡';action.textContent='更新 →'}else{text.textContent='Cookie 正常 · '+(d>0?d.toFixed(0)+' 天':'刚刚更新');action.textContent='详情 →'}}else{bar.style.display='flex';bar.className='card invalid';icon.textContent='🔴';text.textContent='Cookie 已失效';action.textContent='立即更新 →'}}
function checkCookieStatus(){var se=document.getElementById('cookieStatus'),bg=document.getElementById('cookieStatusBadge');fetch('/api/cookie/status').then(function(r){return r.json()}).then(function(d){updateCookieBar(d);if(d.has_cookie){se.innerHTML='✅ Cookie 已设置 · '+d.cookie_len+' 字符';se.style.background='#f0fdf4';se.style.borderColor='#86efac';bg.style.background='#059669'}else{se.innerHTML='❌ 未设置 Cookie';se.style.background='#fef2f2';se.style.borderColor='#fca5a5';bg.style.background='#ef4444'}
if(!d.has_cookie||!d.is_valid){var b=document.getElementById('cookieBody'),t=document.getElementById('cookieToggle');if(!b.classList.contains('open')){b.classList.add('open');t.classList.add('open')}}}).catch(function(){se.innerHTML='⚠️ 无法获取状态';bg.style.background='#94a3b8'})}
function saveCookie(){var inp=document.getElementById('cookieInput'),btn=document.getElementById('btnSaveCookie'),msg=document.getElementById('cookieMsg'),raw=inp.value.trim();if(!raw){msg.innerHTML='❌ 请粘贴 Cookie';msg.style.color='#ef4444';return}
btn.disabled=true;btn.textContent='⏳';msg.textContent='';fetch('/api/cookie/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookie:raw})}).then(function(r){return r.json()}).then(function(d){if(d.success){msg.innerHTML=d.warning?'⚠️ '+d.warning:'✅ 保存并验证通过！';msg.style.color=d.warning?'#d97706':'#059669';checkCookieStatus();inp.value=''}else{msg.innerHTML='❌ '+(d.error||'保存失败');msg.style.color='#ef4444'}}).catch(function(){msg.innerHTML='❌ 网络错误';msg.style.color='#ef4444'}).finally(function(){btn.disabled=false;btn.textContent='💾 保存 Cookie'})}
setTimeout(function(){loadHistoryList();checkCookieStatus()},500);

// ── 智能粘贴 ISBN ──
var pasteTimer=null;
inputArea.addEventListener('paste',function(){clearTimeout(pasteTimer);pasteTimer=setTimeout(function(){var t=inputArea.value;var isbns=[],seen={};t.split(/[\s,，、\n\r]+/).forEach(function(s){s=s.trim().replace(/-/g,'').replace(/ /g,'');if(/^\d{10,13}$/.test(s)&&!seen[s]){seen[s]=true;isbns.push(s)}});if(isbns.length>0){var lines=t.split(/[\n\r]+/);var ig=0;lines.forEach(function(l){var c=l.trim().replace(/-/g,'').replace(/ /g,'');if(c&&!/^\d{10,13}$/.test(c))ig++});showPasteConfirm(isbns.length,ig)}},100)});
function showPasteConfirm(c,ig){var o=document.getElementById('pasteConfirm');if(o)o.remove();var bar=document.createElement('div');bar.id='pasteConfirm';bar.style.cssText='display:flex;align-items:center;gap:8px;margin-top:10px;padding:10px 12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;font-size:.85rem';bar.innerHTML='<span>📋</span><span style="flex:1">识别到 <strong>'+c+'</strong> 个 ISBN'+(ig>0?'<span style="color:#94a3b8;font-size:.78rem;margin-left:6px">（忽略 '+ig+' 行）</span>':'')+'</span><button onclick="confirmPasteQuery()" style="padding:8px 18px;border-radius:8px;border:none;background:#2563eb;color:#fff;font-weight:600;cursor:pointer;font-size:.85rem">🔍 立即查价</button><button onclick="dismissPasteConfirm()" style="padding:8px 10px;border-radius:8px;border:none;background:transparent;color:#94a3b8;cursor:pointer;font-size:.8rem">✕</button>';var card=inputArea.closest('.card');if(card)card.appendChild(bar)}
function confirmPasteQuery(){var b=document.getElementById('pasteConfirm');if(b)b.remove();btnQuery.click()}
function dismissPasteConfirm(){var b=document.getElementById('pasteConfirm');if(b)b.remove()}

// ── OCR 图片识别 ISBN ──
function handleOcrDrop(e){e.preventDefault();document.getElementById('ocrArea').style.borderColor='#cbd5e1';document.getElementById('ocrArea').style.background='';var files=e.dataTransfer.files;if(files.length>0)handleOcrFiles(files)}
function handleOcrFiles(files){var se=document.getElementById('ocrStatus');se.style.display='block';se.innerHTML='⏳ 正在识别 '+files.length+' 张图片...';se.style.color='#2563eb';var pend=files.length,allIsbns=[];function pf(i){if(i>=files.length){if(allIsbns.length>0){se.innerHTML='✅ 识别到 <strong>'+allIsbns.length+'</strong> 个 ISBN，已填入输入框';se.style.color='#059669';var ex=inputArea.value.trim();inputArea.value=ex?ex+'\n'+allIsbns.join('\n'):allIsbns.join('\n');showPasteConfirm(allIsbns.length,0)}else{se.innerHTML='⚠️ 未识别到 ISBN';se.style.color='#d97706'}return}
var file=files[i];if(!file.type.startsWith('image/')){pend--;pf(i+1);return}
var fd=new FormData();fd.append('image',file);fetch('/api/ocr',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){pend--;if(d.isbns&&d.isbns.length>0){d.isbns.forEach(function(isbn){if(allIsbns.indexOf(isbn)===-1)allIsbns.push(isbn)});se.innerHTML='⏳ 识别中... 已提取 '+allIsbns.length+' 个 ISBN'};pf(i+1)}).catch(function(){pend--;pf(i+1)})}
pf(0)}

// ── 手机扫码 ──
(function(){if('BarcodeDetector'in window)document.getElementById('btnScan').style.display=''})();
function scanBarcode(){if(!('BarcodeDetector'in window)){toast('不支持扫码');return}
var btn=document.getElementById('btnScan');btn.textContent='⏳ 打开摄像头...';btn.disabled=true;
var bd;try{bd=new BarcodeDetector({formats:['ean_13','ean_8','upc_a','isbn_13','isbn_10']})}catch(e){btn.textContent='📷 扫码';btn.disabled=false;toast('扫码初始化失败');return}
var v=document.createElement('video');v.style.cssText='max-width:100%;border-radius:10px;margin-top:10px';v.setAttribute('playsinline','');v.setAttribute('autoplay','');
var sc=document.createElement('div');sc.id='scanContainer';sc.style.cssText='margin-top:8px;text-align:center';sc.appendChild(v);
var cb=document.createElement('button');cb.textContent='✕ 关闭扫码';cb.style.cssText='margin-top:8px;padding:6px 16px;border-radius:6px;border:none;background:#e2e8f0;color:#64748b;cursor:pointer;font-size:.8rem';cb.onclick=stopScan;sc.appendChild(cb);
var ic=inputArea.closest('.card');if(ic)ic.appendChild(sc);var stream=null;
navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}}).then(function(s){stream=s;v.srcObject=s;v.play();var st=setInterval(function(){if(!stream){clearInterval(st);return}
bd.detect(v).then(function(bs){if(bs.length>0){var c=bs[0].rawValue.replace(/-/g,'');if(/^\d{10,13}$/.test(c)){stopScan();inputArea.value=inputArea.value.trim()?inputArea.value.trim()+'\n'+c:c;toast('✅ 扫码成功: '+c);setTimeout(function(){btnQuery.click()},500)}}}).catch(function(){})},500)}).catch(function(){btn.textContent='📷 扫码';btn.disabled=false;toast('无法打开摄像头');stopScan()});
function stopScan(){if(stream){stream.getTracks().forEach(function(t){t.stop()});stream=null}var c=document.getElementById('scanContainer');if(c)c.remove();btn.textContent='📷 扫码';btn.disabled=false}}

inputArea.addEventListener('keydown',function(e){if((e.metaKey||e.ctrlKey)&&e.key==='Enter')btnQuery.click()});
</script>
</body>
</html>`;

// ── PWA 静态文件 ───────────────────────────────────────────

const MANIFEST = {
  "name": "孔夫子旧书网 · ISBN 查价",
  "short_name": "孔夫子查价",
  "description": "批量查 ISBN 在孔夫子旧书网的最低进货价",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f1f5f9",
  "theme_color": "#2563eb",
  "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
  "categories": ["shopping", "books"],
  "lang": "zh-CN"
};

const SW_JS = `self.addEventListener("install",()=>self.skipWaiting());
self.addEventListener("activate",(e)=>e.waitUntil(self.clients.claim()));
self.addEventListener("fetch",(e)=>{let u=new URL(e.request.url);if(u.pathname.startsWith("/api/"))return;e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request)))});`;

const ICON_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#2563eb"/><stop offset="100%" stop-color="#1d4ed8"/></linearGradient></defs>
  <rect width="512" height="512" rx="96" fill="url(#b)"/>
  <g transform="translate(256,256)">
    <rect x="-120" y="-130" width="240" height="260" rx="16" fill="white" opacity="0.15"/>
    <rect x="-110" y="-120" width="220" height="240" rx="12" fill="white"/>
    <rect x="-3" y="-120" width="6" height="240" fill="#2563eb" opacity="0.4"/>
    <rect x="-75" y="-78" width="120" height="6" rx="3" fill="#2563eb" opacity="0.6"/>
    <rect x="-75" y="-50" width="90" height="6" rx="3" fill="#2563eb" opacity="0.4"/>
    <rect x="-75" y="-22" width="100" height="6" rx="3" fill="#2563eb" opacity="0.3"/>
    <text x="0" y="70" font-family="system-ui,sans-serif" font-size="80" font-weight="700" text-anchor="middle" fill="#2563eb" opacity="0.15">¥</text>
  </g>
</svg>`;

// ── 工具函数 ──────────────────────────────────────────────

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" },
  });
}

function html(content) {
  return new Response(content, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache" },
  });
}

function text(content, type = "text/plain") {
  return new Response(content, {
    headers: { "Content-Type": type, "Access-Control-Allow-Origin": "*" },
  });
}

function extractFromCurl(text) {
  if (!text) return null;
  // 匹配 Cookie 头
  const patterns = [
    /['"]cookie:\s*(.*?)['"]/i,
    /['"]Cookie:\s*(.*?)['"]/,
    /-b\s+['"]([^'"]+)['"]/,
    /Cookie[=:]\s*['"]([^'"]+)['"]/i,
  ];
  for (const pat of patterns) {
    const m = text.match(pat);
    if (m) {
      let val = m[1].trim().replace(/['"; ]+$/, "");
      if (val) return val;
    }
  }
  // 纯 Cookie 文本
  const clean = text.trim().replace(/^['"]|['"]$/g, "");
  if (clean.includes("=") && !clean.toLowerCase().startsWith("curl") && !clean.toLowerCase().startsWith("http")) {
    return clean;
  }
  return null;
}

// ── 孔夫子 API 查询 ──────────────────────────────────────

async function queryKongfz(isbn, cookieStr, qualityFilter = "") {
  isbn = isbn.trim().replace(/-/g, "").replace(/\s/g, "");
  if (!/^\d{8,13}$/.test(isbn)) {
    return { isbn, title: "—", error: "格式不对" };
  }

  const headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://search.kongfz.com/product/",
    "Cookie": cookieStr,
  };

  const API = "https://search.kongfz.com/pc-gw/search-web/client/pc/product/keyword/list";

  try {
    // 第一页
    let params = new URLSearchParams({ keyword: isbn, page: "1", size: "30" });
    if (qualityFilter) params.set("quality", qualityFilter);
    let resp = await fetch(API + "?" + params.toString(), { headers });
    let data = await resp.json();

    if (data.status !== 1) {
      const msg = data.message || "查询失败";
      return { isbn, title: "—", error: msg.includes("登录") ? "Cookie 失效" : msg };
    }

    const payload = data.data || {};
    const itemResp = payload.itemResponse || {};
    const total = payload.totalFound || payload.totalCount || 0;
    let items = itemResp.list || itemResp.items || [];
    if (!items || items.length === 0) {
      return { isbn, title: "—", error: "无在售记录", count: total };
    }

    const firstItem = items[0];
    const title = firstItem.title || "—";
    const author = firstItem.author || "";
    const press = firstItem.press || "";

    // 翻页找最低价
    const cheapItems = [];
    const allPrices = [];
    const totalPages = Math.max(1, Math.ceil(total / 30));
    const maxPages = Math.min(totalPages, 5);

    for (let page = 1; page <= maxPages; page++) {
      if (page > 1) {
        params = new URLSearchParams({ keyword: isbn, page: String(page), size: "30" });
        if (qualityFilter) params.set("quality", qualityFilter);
        try {
          resp = await fetch(API + "?" + params.toString(), { headers });
          data = await resp.json();
          items = (data.data || {}).itemResponse?.list || [];
        } catch { break; }
      }

      for (const item of items) {
        let p = item.price || item.salePrice;
        if (!p || !(p > 0 && p < 100000)) continue;
        p = parseFloat(p);

        let shipFee = 0;
        const sl = item.postage?.shippingList;
        if (sl?.[0]?.shippingFee != null) shipFee = parseFloat(sl[0].shippingFee);

        cheapItems.push({
          price: Math.round(p * 100) / 100,
          shipping: shipFee,
          total: Math.round((p + shipFee) * 10) / 10,
          quality_text: item.qualityText || "",
          shop: item.shopName || "",
          area: item.shopAreaText || "",
          itemId: item.itemId,
          shopId: item.shopId,
          link: item.link?.pc || "",
        });
        allPrices.push(p);
      }
      if (page < maxPages) {
        // 模拟延时 300ms
        await new Promise((r) => setTimeout(r, 300));
      }
    }

    if (cheapItems.length === 0) {
      return { isbn, title, error: "未解析到价格", count: total };
    }

    cheapItems.sort((a, b) => a.total - b.total);

    return {
      isbn,
      title,
      author: author.substring(0, 20),
      press: press.substring(0, 20),
      count: cheapItems.length,
      total_count: total,
      pages_scanned: maxPages,
      error: null,
      cheapest: cheapItems[0],
      top_cheapest: cheapItems.slice(0, 5),
      price_range: {
        min: Math.min(...allPrices),
        max: Math.max(...allPrices),
        avg: Math.round((allPrices.reduce((a, b) => a + b, 0) / allPrices.length) * 10) / 10,
      },
    };
  } catch (e) {
    return { isbn, title: "—", error: e.message?.substring(0, 30) || "请求异常" };
  }
}

async function addToCart(itemId, shopId, cookieStr) {
  const headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Cookie": cookieStr,
  };
  const params = new URLSearchParams({ itemId: String(itemId), shopId: String(shopId), numbers: "1", callback: "cb" });
  try {
    const resp = await fetch("https://cart.kongfz.com/jsonp/add?" + params.toString(), { headers });
    const body = await resp.text();
    if (body.startsWith("cb(") && body.endsWith(")")) {
      const data = JSON.parse(body.substring(3, body.length - 1));
      if (data.status === 1) {
        return { success: true, cartId: data.result?.cartId };
      }
      return { error: data.errMessage || "加购失败" };
    }
    return { error: "接口返回异常" };
  } catch (e) {
    return { error: e.message?.substring(0, 30) || "请求失败" };
  }
}

// ── Cookie / 历史记录 KV 操作 ────────────────────────────

async function getCookieInfo(KV) {
  const raw = await KV.get("kongfz:config", "json");
  if (!raw || !raw.cookie) {
    return { has_cookie: false, cookie_len: 0, is_valid: false, days_since_update: 0, verify_count: 0, fail_count: 0 };
  }
  let days = 0;
  if (raw.updated_at) {
    const updated = new Date(raw.updated_at);
    const now = new Date();
    days = (now - updated) / 86400000;
  }
  return {
    has_cookie: true,
    cookie_len: raw.cookie.length,
    is_valid: raw.is_valid || false,
    days_since_update: Math.round(days * 10) / 10,
    verify_count: raw.verify_count || 0,
    fail_count: raw.fail_count || 0,
  };
}

async function saveCookieToKV(KV, cookieStr) {
  const existing = await KV.get("kongfz:config", "json");
  const now = new Date().toISOString();
  const data = {
    cookie: cookieStr,
    created_at: existing?.created_at || now,
    updated_at: now,
    is_valid: false,
    verify_count: existing?.verify_count || 0,
    fail_count: existing?.fail_count || 0,
  };
  await KV.put("kongfz:config", JSON.stringify(data));
  return data;
}

async function verifyCookie(KV, cookieStr) {
  // 验证：查询一本确定书
  const result = await queryKongfz("9787108009821", cookieStr);
  const isValid = !result.error || (!result.error.includes("Cookie") && !result.error.includes("登录"));
  const existing = await KV.get("kongfz:config", "json");
  if (existing?.cookie === cookieStr) {
    existing.is_valid = isValid;
    existing.last_verified_at = new Date().toISOString();
    if (isValid) existing.verify_count = (existing.verify_count || 0) + 1;
    else existing.fail_count = (existing.fail_count || 0) + 1;
    await KV.put("kongfz:config", JSON.stringify(existing));
  }
  return isValid;
}

async function getHistory(KV) {
  const raw = await KV.get("kongfz:history", "json");
  return raw?.records || [];
}

async function saveHistoryRecord(KV, name, results, qualityFilter) {
  const records = await getHistory(KV);
  const priced = results.filter((r) => r.cheapest);
  const totalCost = priced.reduce((sum, r) => sum + (r.cheapest.total || 0), 0);
  const id = Date.now().toString(36) + Math.random().toString(36).substring(2, 6);
  const record = {
    id,
    name: name || `查询 ${new Date().toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}`,
    created_at: new Date().toLocaleString("zh-CN", { hour12: false }),
    isbns: results.map((r) => r.isbn).filter(Boolean),
    results,
    book_count: results.length,
    priced_count: priced.length,
    total_cost: Math.round(totalCost * 10) / 10,
    quality_filter: qualityFilter || "",
  };
  records.unshift(record);
  if (records.length > 100) records.length = 100;
  await KV.put("kongfz:history", JSON.stringify({ records }));
  return id;
}

async function deleteHistoryRecord(KV, id) {
  let records = await getHistory(KV);
  records = records.filter((r) => r.id !== id);
  await KV.put("kongfz:history", JSON.stringify({ records }));
}

// ── 请求路由 ──────────────────────────────────────────────

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // ── 静态文件 ──
    if (path === "/manifest.json") return json(MANIFEST);
    if (path === "/sw.js") return text(SW_JS, "application/javascript");
    if (path === "/icon.svg") return text(ICON_SVG, "image/svg+xml");

    // ── 首页 ──
    if (path === "/" || path === "/index.html") return html(HTML);

    // ── API: Cookie 状态 ──
    if (path === "/api/cookie/status") {
      const info = await getCookieInfo(env.KONGFZ_PRICE);
      return json(info);
    }

    // ── API: Cookie 验证 ──
    if (path === "/api/cookie/verify") {
      const config = await env.KONGFZ_PRICE.get("kongfz:config", "json");
      if (!config?.cookie) return json({ valid: false, message: "未设置 Cookie" });
      const valid = await verifyCookie(env.KONGFZ_PRICE, config.cookie);
      return json({ valid, message: valid ? "Cookie 有效" : "Cookie 已失效", ...(await getCookieInfo(env.KONGFZ_PRICE)) });
    }

    // ── API: 更新 Cookie ──
    if (path === "/api/cookie/update" && request.method === "POST") {
      try {
        const body = await request.json();
        const raw = body.cookie || "";
        if (!raw) return json({ error: "Cookie 不能为空" });
        const cookie = extractFromCurl(raw);
        if (!cookie) return json({ error: "无法提取 Cookie，请粘贴 Cookie 字符串或完整 cURL 命令" });
        await saveCookieToKV(env.KONGFZ_PRICE, cookie);
        const valid = await verifyCookie(env.KONGFZ_PRICE, cookie);
        return json({
          success: true,
          ...(valid ? {} : { warning: "Cookie 已保存但验证未通过，请确认已登录后重试" }),
          ...(await getCookieInfo(env.KONGFZ_PRICE)),
        });
      } catch (e) {
        return json({ error: e.message?.substring(0, 60) || "处理失败" });
      }
    }

    // ── API: ISBN 查询 ──
    if (path === "/api/query") {
      const config = await env.KONGFZ_PRICE.get("kongfz:config", "json");
      if (!config?.cookie) return json({ error: "Cookie 未找到，请先设置 Cookie" });
      const isbn = url.searchParams.get("isbn") || "";
      if (!isbn) return json({ error: "缺少 isbn 参数" });
      const quality = url.searchParams.get("quality") || "";
      const result = await queryKongfz(isbn, config.cookie, quality);
      return json(result);
    }

    // ── API: 加购 ──
    if (path === "/api/addtocart") {
      const config = await env.KONGFZ_PRICE.get("kongfz:config", "json");
      if (!config?.cookie) return json({ error: "未登录" });
      const itemId = url.searchParams.get("itemId");
      const shopId = url.searchParams.get("shopId");
      if (!itemId || !shopId) return json({ error: "缺少参数" });
      const result = await addToCart(itemId, shopId, config.cookie);
      return json(result);
    }

    // ── API: 历史记录列表 ──
    if (path === "/api/history/list") {
      const records = await getHistory(env.KONGFZ_PRICE);
      const summaries = records.map((r) => ({
        id: r.id, name: r.name, created_at: r.created_at,
        book_count: r.book_count, priced_count: r.priced_count,
        total_cost: r.total_cost, quality_filter: r.quality_filter || "",
      }));
      return json({ records: summaries });
    }

    // ── API: 获取单条历史 ──
    if (path === "/api/history/get") {
      const id = url.searchParams.get("id");
      if (!id) return json({ error: "缺少 id 参数" });
      const records = await getHistory(env.KONGFZ_PRICE);
      const record = records.find((r) => r.id === id);
      if (!record) return json({ error: "记录未找到" });
      return json(record);
    }

    // ── API: 保存历史 ──
    if (path === "/api/history/save" && request.method === "POST") {
      try {
        const body = await request.json();
        if (!body.results?.length) return json({ error: "无数据" });
        const id = await saveHistoryRecord(env.KONGFZ_PRICE, body.name, body.results, body.quality_filter);
        return json({ success: true, id });
      } catch (e) {
        return json({ error: e.message?.substring(0, 60) || "保存失败" });
      }
    }

    // ── API: 删除历史 ──
    if (path === "/api/history/delete") {
      const id = url.searchParams.get("id");
      if (!id) return json({ error: "缺少 id 参数" });
      await deleteHistoryRecord(env.KONGFZ_PRICE, id);
      return json({ success: true });
    }

    // ── 兜底：SPA 路由 ──
    return html(HTML);
  },
};
