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
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/icon.svg">
<link rel="icon" href="/static/icon.svg" type="image/svg+xml">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f1f5f9;color:#1e293b;padding:12px 10px 76px;min-height:100vh;-webkit-tap-highlight-color:transparent}
.container{max-width:960px;margin:0 auto}
h1{font-size:1.2rem;background:linear-gradient(135deg,#2563eb,#1d4ed8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:2px}
.subtitle{color:#64748b;font-size:.78rem;margin-bottom:12px}
.card{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:10px}
.card-title{font-size:.92rem;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px}
textarea,.field{width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:.85rem;outline:none;font-family:inherit}
textarea:focus,.field:focus{border-color:#3b82f6;box-shadow:0 0 0 3px #dbeafe}
textarea{min-height:80px;line-height:1.5;resize:vertical}
.row{display:flex;gap:6px;margin-top:8px;align-items:center;flex-wrap:wrap}
.btn{padding:8px 18px;border-radius:8px;border:none;font-weight:500;cursor:pointer;font-size:.82rem;transition:opacity .15s}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-primary{background:#3b82f6;color:#fff}
.btn-primary:hover:not(:disabled){background:#2563eb}
.btn-outline{background:transparent;border:1px solid #e2e8f0;color:#64748b}
.btn-outline:hover{background:#f8fafc}
#status{font-size:.8rem;color:#64748b}
#status.loading{color:#3b82f6}
#status.done{color:#10b981}
#status.error{color:#ef4444}
table{width:100%;border-collapse:collapse;font-size:.78rem;margin-top:4px}
thead{background:#f8fafc}
th{padding:5px;text-align:left;font-weight:600;white-space:nowrap;border-bottom:2px solid #e2e8f0}
td{padding:5px;border-bottom:1px solid #e2e8f0}
tr:hover td{background:#f8fafc}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,1fr));gap:6px;margin-bottom:10px}
.s-card{text-align:center;padding:8px;border-radius:8px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.s-card .n{font-size:1.1rem;font-weight:700}
.s-card .l{font-size:.68rem;color:#64748b;margin-top:2px}
.blue .n{color:#3b82f6}.green .n{color:#10b981}.amber .n{color:#f59e0b}
.result-box{border:2px solid #10b981;border-radius:10px;padding:12px 14px;margin-bottom:10px;background:#f0fdf4}
.result-box .book-title{font-size:.95rem;font-weight:700;color:#065f46}
.result-box .meta{font-size:.7rem;color:#64748b;margin-top:2px}
.empty-state{text-align:center;color:#94a3b8;padding:20px;font-size:.82rem}
select{padding:5px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:.82rem;background:#fff;outline:none}

/* 折叠 */
.fold-header{display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none}
.fold-header .arrow{font-size:.75rem;color:#64748b;transition:transform .2s}
.fold-header .arrow.open{transform:rotate(90deg)}
.fold-body{max-height:0;overflow:hidden;transition:max-height .25s ease}
.fold-body.open{max-height:2000px}

/* 历史记录 */
.h-item{display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;margin-top:6px;gap:6px;flex-wrap:wrap}
.h-item .info{flex:1;min-width:120px}
.h-item .name{font-weight:500;font-size:.82rem}
.h-item .meta{font-size:.7rem;color:#64748b;margin-top:2px}
.h-item .actions{display:flex;gap:4px}
.h-item .actions button{padding:5px 10px;border-radius:6px;border:none;cursor:pointer;font-size:.72rem;font-weight:500}
.btn-h-q{background:#3b82f6;color:#fff}
.btn-h-c{background:#dc2626;color:#fff}
.btn-h-d{background:transparent;border:1px solid #e2e8f0!important;color:#94a3b8}

/* Cookie 条 */
#cookieBar{padding:8px 12px;border-radius:8px;cursor:pointer;display:none;margin-bottom:10px;font-size:.82rem;border:1px solid #e2e8f0}
#cookieBar.valid{border-color:#86efac;background:#f0fdf4}
#cookieBar.invalid{border-color:#fca5a5;background:#fef2f2}
#cookieBar.warning{border-color:#fde68a;background:#fffbeb}
.fail-chip{display:inline-flex;align-items:center;gap:3px;padding:3px 8px;border:1px solid #fca5a5;border-radius:14px;font-size:.72rem;font-family:monospace;background:#fff;cursor:pointer;color:#dc2626}
.save-bar{display:flex;gap:6px;align-items:center;justify-content:center;margin-bottom:10px;padding:8px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;flex-wrap:wrap}
.save-bar input{max-width:200px;padding:5px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:.8rem;outline:none}
.btn-save{background:#f59e0b;color:#fff;padding:5px 14px;border-radius:6px;border:none;cursor:pointer;font-weight:500;font-size:.8rem}
.pc-bar{display:flex;align-items:center;gap:8px;margin-top:8px;padding:8px 10px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;font-size:.8rem}

/* 底部导航 */
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #e2e8f0;display:flex;justify-content:space-around;padding:6px 0 env(safe-area-inset-bottom,6px);z-index:100}
.bottom-nav button{display:flex;flex-direction:column;align-items:center;gap:2px;background:none;border:none;color:#64748b;font-size:.65rem;cursor:pointer;padding:4px 16px}
.bottom-nav button svg{width:22px;height:22px;stroke:currentColor;stroke-width:2;fill:none}
.bottom-nav button:active{color:#2563eb}
.toast{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,.75);color:#fff;padding:10px 20px;border-radius:8px;font-size:.85rem;z-index:999;display:none;max-width:80vw;text-align:center;pointer-events:none}

/* 手机专用 */
@media(max-width:480px){
  body{padding:10px 8px 72px}
  .card{padding:10px;margin-bottom:8px}
  .result-box{padding:10px}
}
/* 库存 */
.inv-bar{display:flex;gap:8px;overflow-x:auto;padding:6px 0;margin-bottom:8px}
.inv-bar .c{flex:1;min-width:60px;text-align:center;padding:8px 4px;border-radius:8px;background:#f8fafc}
.inv-bar .c .n{font-size:1rem;font-weight:700;color:#1e293b}
.inv-bar .c .l{font-size:.65rem;color:#64748b;margin-top:1px}
.inv-tabs{display:flex;gap:4px;margin:6px 0;overflow-x:auto}
.inv-tabs button{padding:4px 12px;border-radius:14px;border:1px solid #e2e8f0;background:#fff;font-size:.78rem;white-space:nowrap;cursor:pointer;color:#64748b}
.inv-tabs button.on{background:#3b82f6;color:#fff;border-color:#3b82f6}
.inv-item{display:flex;padding:10px;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:6px;gap:8px;align-items:center}
.inv-item .i-info{flex:1;min-width:0}
.inv-item .i-t{font-weight:500;font-size:.85rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.inv-item .i-m{font-size:.7rem;color:#64748b;margin-top:2px}
.inv-item .i-act{flex-shrink:0;display:flex;gap:4px}
.inv-item .i-act button{padding:4px 10px;border-radius:6px;border:none;cursor:pointer;font-size:.72rem;font-weight:500}
.btn-g{background:#059669;color:#fff}.btn-b{background:#3b82f6;color:#fff}.btn-r{background:#dc2626;color:#fff}.btn-ghost{background:transparent;border:1px solid #e2e8f0!important;color:#94a3b8}
.stats-card{background:linear-gradient(135deg,#065f46,#059669);color:#fff;border-radius:10px;padding:14px;margin-bottom:10px}
.stats-card .sg{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center;margin-bottom:10px}
.stats-card .sg .n{font-size:1.3rem;font-weight:700}.stats-card .sg .l{font-size:.7rem;opacity:.8;margin-top:1px}
.stats-card .se{display:flex;justify-content:space-between;font-size:.8rem;padding:4px 0;border-top:1px solid rgba(255,255,255,.2)}
.per-btn{background:rgba(255,255,255,.15);color:#fff;border:none;padding:3px 10px;border-radius:10px;font-size:.72rem;cursor:pointer}
.per-btn.on{background:rgba(255,255,255,.35)}
.inv-empty{text-align:center;color:#94a3b8;padding:30px 10px;font-size:.82rem}
.inv-empty .big{font-size:2rem;margin-bottom:6px}
</style>
</head>
<body>
<div class="container">
  <h1>📚 孔夫子进货查价</h1>
  <p class="subtitle">输入 ISBN 查最低进货价+运费</p>

  <div class="card">
    <div class="card-title">📖 ISBN（每行一个）</div>
    <textarea id="inputArea" placeholder="9787108009821&#10;9787020002207&#10;可批量粘贴，自动识别 ISBN"></textarea>
    <div class="row">
      <label style="font-size:.8rem;color:#64748b">品相:</label>
      <select id="qualitySelect">
        <option value="">不限</option><option value="100~100">全新</option>
        <option value="95~100">九五品+</option><option value="90~100">九品+</option>
        <option value="85~100">八五品+</option>
      </select>
      <button class="btn btn-primary" id="btnQuery">🔍 查最低价</button>
      <button class="btn btn-outline" id="btnClear">清空</button>
      <span id="status">就绪</span>
    </div>
    <div style="margin-top:8px;padding:8px;border:1px dashed #cbd5e1;border-radius:8px;text-align:center;font-size:.75rem;color:#94a3b8;cursor:pointer" onclick="document.getElementById('ocrInp').click()">
      📷 上传截图自动识别 ISBN
      <input type="file" id="ocrInp" accept="image/*" multiple style="display:none" onchange="doOcr(this.files)">
    </div>
    <div id="ocrSt" style="display:none;margin-top:4px;font-size:.78rem"></div>
  </div>

  <!-- Cookie 状态条 -->
  <div id="cookieBar" onclick="fold('cookie')">
    <span id="cookIcon">🟢</span> <span id="cookText"></span> <span id="cookAct" style="font-size:.75rem;color:#64748b;float:right">→</span>
  </div>

  <div class="card" style="border:1px solid #fde68a">
    <div class="fold-header" onclick="fold('cookie')">
      <div class="card-title" style="margin-bottom:0">🍪 Cookie 设置</div>
      <span><span id="cookDot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#94a3b8;margin-right:4px"></span><span class="arrow" id="cookArrow">▶</span></span>
    </div>
    <div class="fold-body" id="fold_cookie">
      <div style="margin-top:6px;font-size:.8rem;color:#475569;line-height:1.6">
        <div id="cookSt" style="padding:6px 10px;border-radius:6px;background:#f8fafc;font-size:.78rem;border:1px solid #e2e8f0;margin-bottom:6px">检查中...</div>
        <details style="margin-bottom:6px;background:#eff6ff;border-radius:6px;padding:8px 10px;border:1px solid #bfdbfe;font-size:.75rem">
          <summary style="font-weight:600;color:#2563eb;cursor:pointer">📱 手机取 Cookie</summary>
          <div style="margin-top:6px;line-height:1.7">
            在手机浏览器打开 <strong>kongfz.com</strong> 并登录 → 地址栏输入 <code style="background:#e2e8f0;padding:1px 4px;border-radius:3px;word-break:break-all">javascript:prompt('',document.cookie)</code> → 复制弹窗内容
          </div>
        </details>
        <textarea id="cookInp" placeholder="粘贴 Cookie 字符串或 cURL 命令" style="width:100%;min-height:50px;font-family:monospace;font-size:.78rem"></textarea>
        <div class="row">
          <button class="btn btn-primary" onclick="saveCookie()" style="background:#f59e0b;font-size:.8rem">💾 保存</button>
          <span id="cookMsg" style="font-size:.8rem"></span>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="fold-header" onclick="fold('hist')">
      <div class="card-title" style="margin-bottom:0">📋 历史记录</div>
      <span class="arrow" id="histArrow">▶</span>
    </div>
    <div class="fold-body" id="fold_hist"><div id="histList" style="margin-top:4px"><div style="text-align:center;color:#94a3b8;font-size:.8rem;padding:10px">暂无</div></div></div>
  </div>

  <div id="results"></div>
  <div id="empty" class="empty-state">📝 输入 ISBN 后点查最低价</div>
</div>

<div class="bottom-nav">
  <button onclick="scrollTo(0,0)"><svg viewBox="0 0 24 24"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg><span>顶部</span></button>
  <button onclick="showInv()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg><span>📒 账本</span></button>
  <button onclick="fold('cookie')"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg><span>Cookie</span></button>
  <button onclick="fold('hist')"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span>历史</span></button>
  <button onclick="cleanupAddr()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg><span>清理地址</span></button>
  <button onclick="selfCheck()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg><span>自检</span></button>
</div>
<div class="toast" id="toast"></div>

<script>
var R=false,L=[],I=id('inputArea'),S=id('status'),E=id('results'),N=id('empty'),Q=id('btnQuery');
function id(s){return document.getElementById(s)}
function esc(s){return(s||'').replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})}
function ss(t,c){S.textContent=t;S.className=c||''}
function fj(u,o){return fetch(u,o||{}).then(function(r){return r.json()})}

// 折叠
function fold(n){
  var b=id('fold_'+n),a=id(n+'Arrow');
  if(!b)return;
  b.classList.toggle('open');
  if(a)a.classList.toggle('open');
  if(b.classList.contains('open')&&n==='hist')loadH();
  if(b.classList.contains('open')&&n==='cookie')ckC();
}

// 粘贴
var pt;I.addEventListener('paste',function(){clearTimeout(pt);pt=setTimeout(function(){var is=[],v={};I.value.split(/[\\s,，、\\n\\r]+/).forEach(function(s){s=s.trim().replace(/-/g,'').replace(/ /g,'');if(/^\\d{10,13}$/.test(s)&&!v[s]){v[s]=1;is.push(s)}});if(is.length){var b=id('pc');if(!b){b=document.createElement('div');b.className='pc-bar';b.id='pc';b.innerHTML='📋 识别到 <strong id="pcN"></strong> 个 ISBN <button onclick="cp()" style="padding:5px 12px;border-radius:6px;border:none;background:#2563eb;color:#fff;font-weight:600;cursor:pointer;font-size:.8rem">🔍 查价</button><button onclick="document.getElementById(\\'pc\\').remove()" style="padding:4px;border:none;background:transparent;color:#94a3b8;cursor:pointer">✕</button>';I.closest('.card').appendChild(b)}id('pcN').textContent=is.length}},150)});
I.addEventListener('keydown',function(e){if((e.metaKey||e.ctrlKey)&&e.key==='Enter')Q.click()});
function cp(){var b=id('pc');if(b)b.remove();Q.click()}

// 查价（批量 API — 一次请求查所有 ISBN，服务器端并行处理）
Q.onclick=function(){
  if(R)return;
  var t=I.value.trim();
  if(!t){ss('请输入 ISBN','error');return}
  var is=[],v={};
  t.split(/[\\s,]+/).forEach(function(s){s=s.trim().replace(/-/g,'');if(/^\\d{8,13}$/.test(s)&&!v[s]){v[s]=1;is.push(s)}});
  if(!is.length){ss('无效 ISBN','error');return}
  R=1;Q.disabled=1;N.style.display='none';E.innerHTML='';
  var ql=id('qualitySelect').value,st=Date.now();
  ss('⏳ 批量查询 '+is.length+' 本...','loading');
  E.innerHTML='<div class="summary"><div class="s-card blue"><div class="n">'+is.length+'</div><div class="l">查询中</div></div><div class="s-card green"><div class="n"><span id="batchSec">0</span>s</div><div class="l">已用时</div></div></div>';
  var tmr=setInterval(function(){var el=id('batchSec');if(el)el.textContent=((Date.now()-st)/1000).toFixed(1)},500);
  var u='/api/batch_query?isbns='+is.map(function(s){return encodeURIComponent(s)}).join(',');
  if(ql)u+='&quality='+encodeURIComponent(ql);
  fj(u).then(function(d){
    clearInterval(tmr);
    if(d.error){ss('❌ '+d.error,'error');R=0;Q.disabled=0;return}
    L=d.results;
    var bid='b_'+Date.now();L.forEach(function(r){r._batchId=bid});
    var ok=L.filter(function(r){return !r.error}),ng=L.filter(function(r){return r.error});
    sh(L);
    R=0;Q.disabled=0;
    ss('✅ 完成！查到 '+ok.length+'/'+L.length+' 本 · 用时 '+((Date.now()-st)/1000).toFixed(1)+'s','done')
  }).catch(function(e){
    clearInterval(tmr);
    ss('❌ 网络错误','error');R=0;Q.disabled=0
  })
};

function sh(data){
  var ok=data.filter(function(r){return !r.error}),pd=ok.filter(function(r){return r.cheapest}),fl=data.filter(function(r){return r.error}),html='';
  if(fl.length){
    html+='<div class="card" style="border:2px solid #ef4444;background:#fef2f2;margin-bottom:10px"><div class="card-title" style="color:#dc2626">⚠️ 异常 '+fl.length+' 个</div><div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px">';
    fl.forEach(function(f){html+='<span class="fail-chip" onclick="rq(\\''+f.isbn+'\\')">🔍 '+f.isbn+' <span style="color:#fca5a5">('+esc(f.error||'')+')</span></span>'});
    html+='</div><div style="display:flex;gap:6px;flex-wrap:wrap"><button class="btn btn-primary" onclick="rqA()" style="background:#dc2626;font-size:.8rem">🔍 重查全部</button><button onclick="cpyFail()" style="padding:5px 10px;border-radius:6px;border:1px solid #94a3b8;background:transparent;color:#64748b;cursor:pointer;font-size:.78rem">📋 复制异常书号</button></div></div>';
  }
  html+='<div class="summary"><div class="s-card blue"><div class="n">'+data.length+'</div><div class="l">查询</div></div><div class="s-card green"><div class="n">'+ok.length+'</div><div class="l">查到</div></div><div class="s-card amber"><div class="n">'+(data.length-ok.length)+'</div><div class="l">异常</div></div>';
  if(pd.length){var tot=0;pd.forEach(function(r){tot+=r.cheapest.total});html+='<div class="s-card green"><div class="n">¥'+tot.toFixed(1)+'</div><div class="l">最低总价</div></div><div class="s-card" style="background:#f0fdf4"><div class="n" style="color:#10b981;font-size:1.1rem">¥'+(Math.round(tot*1.25*100)/100).toFixed(1)+'</div><div class="l">建议售价</div></div><div style="grid-column:1/-1;text-align:center;margin-top:4px"><button onclick="ba()" style="padding:8px 24px;border-radius:8px;border:none;background:#dc2626;color:#fff;cursor:pointer;font-weight:600;font-size:1rem;box-shadow:0 2px 8px rgba(220,38,38,.3)">🛒 一键加购全部 '+pd.length+' 本</button></div>'}
  html+='</div>';
  data.forEach(function(r){
    if(r.error){html+='<div class="card" style="border-left:3px solid #ef4444"><div style="font-family:monospace;font-size:.75rem;color:#94a3b8">'+esc(r.isbn)+'</div><div style="color:#ef4444;font-size:.8rem;margin-top:2px">'+esc(r.error)+'</div></div>'}
    else if(r.cheapest){
      html+='<div class="result-box"><div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:4px"><div class="book-title">'+esc(r.title)+'</div><span style="font-size:.7rem;color:#94a3b8">'+esc(r.isbn)+'</span></div>';
      if(r.author||r.press)html+='<div class="meta">'+esc(r.author)+(r.author&&r.press?' · ':'')+esc(r.press)+'</div>';
      var pr=r.price_range||{},prmin=pr.min||0,pravg=pr.avg||0,prmax=pr.max||0;
      html+='<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px;margin:3px 0 6px;padding:4px 8px;background:#f8fafc;border-radius:6px;font-size:.72rem;text-align:center"><div><div style="font-size:.6rem;color:#94a3b8">最低书价</div><strong style="color:#dc2626;font-size:.85rem">¥'+prmin.toFixed(1)+'</strong></div><div><div style="font-size:.6rem;color:#94a3b8">均价</div><strong style="font-size:.85rem">¥'+pravg.toFixed(1)+'</strong></div><div><div style="font-size:.6rem;color:#94a3b8">最高</div><strong style="color:#94a3b8;font-size:.85rem">¥'+prmax.toFixed(1)+'</strong></div></div><div style="font-size:.65rem;color:#94a3b8;margin:-3px 0 2px;text-align:center">在售 '+r.total_count+' 本</div>';
      if(r.cheapest.itemId&&r.cheapest.shopId){var c=r.cheapest;html+='<div style="margin:4px 0;display:flex;gap:6px;align-items:center;flex-wrap:wrap"><button onclick="ac('+c.itemId+','+c.shopId+',this)" style="padding:5px 14px;border-radius:6px;border:none;background:#059669;color:#fff;cursor:pointer;font-size:.82rem;font-weight:500">🛒 最低价 ¥'+c.total.toFixed(1)+'</button><span style="font-size:.7rem;color:#64748b">'+esc(c.shop)+' · '+esc(c.quality_text)+'</span></div>'}
      // 记账按钮
      var aun=r.author||''; var p=r.cheapest?r.cheapest.price:0; var sp=r.cheapest?r.cheapest.shipping:0;
      html+='<div style="margin:2px 0;display:flex;gap:6px;align-items:center;flex-wrap:wrap"><button data-isbn="'+esc(r.isbn)+'" data-title="'+esc(r.title||'')+'" data-author="'+esc(aun)+'" data-price="'+p+'" data-shipping="'+sp+'" onclick="bookBuy(this)" style="padding:5px 14px;border-radius:6px;border:none;background:#f59e0b;color:#fff;cursor:pointer;font-size:.82rem;font-weight:500">📝 记一笔</button></div>';
      var items=r.top_cheapest||[r.cheapest];
      html+='<table><thead><tr><th>#</th><th>店铺</th><th>品相</th><th style="text-align:right">书价</th><th style="text-align:right">运费</th><th style="text-align:right;color:#dc2626">总价</th><th></th></tr></thead><tbody>';
      items.forEach(function(it,j){
        html+='<tr><td>'+(j+1)+'</td><td>'+esc(it.shop)+(it.area?'<div class="meta">'+esc(it.area)+'</div>':'')+'</td><td>'+esc(it.quality_text||'—')+'</td><td style="text-align:right">¥'+it.price.toFixed(2)+'</td><td style="text-align:right">¥'+it.shipping.toFixed(1)+'</td><td style="text-align:right'+(j===0?';font-weight:700;color:#dc2626':'')+'">¥'+it.total.toFixed(1)+'</td><td style="text-align:center">'+(it.itemId&&it.shopId?'<button onclick="ac('+it.itemId+','+it.shopId+',this)" style="padding:2px 6px;border-radius:4px;border:1px solid #3b82f6;background:transparent;color:#3b82f6;cursor:pointer;font-size:.72rem">🛒</button>':'')+'</td></tr>'
      });
      html+='</tbody></table><div style="font-size:.65rem;color:#94a3b8;margin-top:3px">扫描'+(r.pages_scanned||1)+'页 · 在售'+r.total_count+'本</div></div>'
    }
  });
  E.innerHTML=html;L=data;
  var sb='sb_'+Date.now();E.insertAdjacentHTML('afterbegin','<div class="save-bar" id="'+sb+'"><span>💾</span><input id="si" placeholder="命名（可选）"><button class="btn-save" onclick="sH(\\''+sb+'\\')">保存查询</button><button class="btn-save" onclick="cpyQuote(0)" style="background:#059669;margin-left:4px">📋 我的成本</button><button class="btn-save" onclick="cpyQuote(1)" style="background:#2563eb;margin-left:2px">📤 发给买家</button></div>');
}

// 加购
function ac(iid,sid,btn){
  var o=btn.textContent;btn.textContent='⏳';btn.disabled=1;btn.style.opacity='.6';
  fj('/api/addtocart?itemId='+iid+'&shopId='+sid).then(function(d){
    if(d.success){btn.textContent='✅';btn.style.borderColor='#10b981';btn.style.color='#10b981';toast('已加购')}
    else{btn.textContent='❌';setTimeout(function(){btn.textContent=o;btn.disabled=0;btn.style.opacity='1'},2000)}
  }).catch(function(){btn.textContent='❌';setTimeout(function(){btn.textContent=o;btn.disabled=0;btn.style.opacity='1'},2000)})
}
function ba(){
  var is=L.filter(function(r){return r.cheapest&&r.cheapest.itemId&&r.cheapest.shopId});if(!is.length){toast('无商品');return}
  var btn=document.querySelector('[onclick="ba()"]');btn.disabled=1;btn.textContent='⏳ 0/'+is.length;var ok=0,ng=0;
  function nx(i){if(i>=is.length){btn.textContent='✅ '+ok+'/'+is.length+(ng?' ('+ng+'失败)':'');btn.style.background=ok>0?'#059669':'#dc2626';toast('已完成 '+ok+'/'+is.length);return}btn.textContent='⏳ '+(i+1)+'/'+is.length;fj('/api/addtocart?itemId='+is[i].cheapest.itemId+'&shopId='+is[i].cheapest.shopId).then(function(d){if(d.success)ok++;else ng++;setTimeout(function(){nx(i+1)},1200)}).catch(function(){ng++;setTimeout(function(){nx(i+1)},1200)})}nx(0)
}

// 复制报价单：forBuyer=1 精简版（给买家），否则详细版（自用）
function cpyQuote(forBuyer){
  var ok=L.filter(function(r){return r.cheapest});
  if(!ok.length){toast('无有效数据');return}
  var lines=[], i=0, totalCost=0, totalSug=0;
  ok.forEach(function(r){
    i++;
    var c=r.cheapest, p=c.price, s=c.shipping, t=p+s, sug=Math.round(t*1.25*100)/100;
    totalCost+=t; totalSug+=sug;
    if(forBuyer){
      lines.push(i+'. '+(r.title||'无书名'));
      lines.push('   ISBN: '+r.isbn);
      lines.push('   ¥'+sug.toFixed(1));
    }else{
      lines.push(i+'. '+(r.title||'无书名'));
      lines.push('   ISBN: '+r.isbn);
      lines.push('   最低进价: ¥'+p.toFixed(1)+'+¥'+s.toFixed(1)+'=¥'+t.toFixed(1));
      lines.push('   建议售价: ¥'+sug.toFixed(1)+' (125%)');
    }
  });
  lines.push('');
  lines.push('合计: '+ok.length+' 本');
  if(forBuyer){
    lines.push('总价: ¥'+totalSug.toFixed(1));
  }else{
    lines.push('总进价: ¥'+totalCost.toFixed(1)+'  总建议售价: ¥'+totalSug.toFixed(1));
  }
  var label=forBuyer?'报价单已复制，可直接发给买家':'已复制成本报价单';
  doCopy(lines.join('\\n'),function(){toast('✅ '+label)},function(){prompt('📋 '+(forBuyer?'报价单':'成本单')+'，复制后关闭：',lines.join('\\n'))});
}

// 复制异常书号（一键复制转发消息）
function cpyFail(){
  var fail=[];
  document.querySelectorAll('.fail-chip').forEach(function(el){var m=(el.textContent||'').match(/\\d{8,13}/);if(m)fail.push(m[0])});
  if(!fail.length){toast('无异常书号');return}
  var txt='📋 以下书号暂未查到结果，请确认：\\n'+fail.join('\\n');
  doCopy(txt,function(){toast('✅ 已复制 '+fail.length+' 个异常书号，可直接转发')},function(){prompt('📋 异常书号（'+fail.length+' 个），复制后关闭：',txt)})
}
function doCopy(txt,onOk,onFail){
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(txt).then(onOk).catch(function(){cpyEl(txt,onOk,onFail)})
  }else{cpyEl(txt,onOk,onFail)}
}
function cpyEl(txt,onOk,onFail){
  var ta=document.createElement('textarea');
  ta.value=txt;
  ta.style.position='fixed';ta.style.left='-9999px';ta.style.top='0';ta.style.width='1px';ta.style.height='1px';ta.style.opacity='0';ta.style.zIndex='-1';
  document.body.appendChild(ta);
  var r=ta.createTextRange?ta.createTextRange():null;
  if(r){r.moveToElementText(ta);r.select()}
  else{ta.focus();ta.setSelectionRange(0,txt.length)}
  try{if(document.execCommand('copy')){document.body.removeChild(ta);onOk();return}}catch(e){}
  document.body.removeChild(ta);onFail()
}
// 重查
function rq(is){I.value=is;E.innerHTML='';N.style.display='none';scrollTo(0,0);setTimeout(function(){Q.click()},300)}
function rqA(){var is=[];document.querySelectorAll('.fail-chip').forEach(function(el){var m=(el.textContent||'').match(/\\d{8,13}/);if(m)is.push(m[0])});if(!is.length)return;I.value=is.join('\\n');rq(is[0])}

// 历史
function loadH(){
  fj('/api/history/list').then(function(d){
    var el=id('histList');
    if(!d.records||!d.records.length){el.innerHTML='<div style="text-align:center;color:#94a3b8;font-size:.8rem;padding:10px">暂无记录</div>';return}
    el.innerHTML=d.records.map(function(r){
      return '<div class="h-item" id="hi_'+r.id+'"><div class="info"><div class="name">'+esc(r.name)+'</div><div class="meta">'+(r.created_at||'')+' · '+r.book_count+'本'+(r.priced_count?' · 🏷️ ¥'+r.total_cost.toFixed(1):'')+'</div></div><div class="actions"><button class="btn-h-q" onclick="rH(\\''+r.id+'\\')">🔍</button>'+(r.priced_count?'<button class="btn-h-c" onclick="cH(\\''+r.id+'\\')">🛒</button>':'')+'<button class="btn-h-d" onclick="dH(\\''+r.id+'\\')">🗑️</button></div></div>'
    }).join('')
  }).catch(function(){})
}
function sH(sbId){
  var btn=document.querySelector('#'+sbId+' .btn-save');if(!btn)return;
  var nm=(id('si').value||'').trim()||('查询 '+new Date().toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}));
  btn.disabled=1;btn.textContent='⏳';
  fj('/api/history/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:nm,results:L,quality_filter:id('qualitySelect').value})}).then(function(d){
    if(d.success){btn.textContent='✅';btn.style.background='#10b981';fold('hist');id('histArrow')&&id('histArrow').classList.add('open');loadH()}
    else{btn.textContent='❌';setTimeout(function(){btn.disabled=0;btn.textContent='保存';btn.style.background='#f59e0b'},2000)}
  }).catch(function(){btn.textContent='❌';setTimeout(function(){btn.disabled=0;btn.textContent='保存';btn.style.background='#f59e0b'},2000)})
}
function rH(id){
  fj('/api/history/get?id='+encodeURIComponent(id)).then(function(rec){
    if(rec.error||!rec.isbns||!rec.isbns.length){toast('无数据');return}
    I.value=rec.isbns.join('\\n');if(rec.quality_filter)id('qualitySelect').value=rec.quality_filter;
    E.innerHTML='';N.style.display='none';scrollTo(0,0);setTimeout(function(){Q.click()},300)
  }).catch(function(){toast('获取失败')})
}
function cH(id){
  fj('/api/history/get?id='+encodeURIComponent(id)).then(function(rec){
    if(rec.error){toast(rec.error);return}
    var is=(rec.results||[]).filter(function(r){return r.cheapest&&r.cheapest.itemId&&r.cheapest.shopId});
    if(!is.length){toast('无商品');return}
    var btn=event&&event.target;if(btn){btn.disabled=1;btn.textContent='⏳ 0/'+is.length}
    var ok=0,ng=0;
    function nx(i){if(i>=is.length){if(btn){btn.textContent='✅ '+ok+'/'+is.length+(ng?' ('+ng+'失败)':'');btn.style.background=ok>0?'#059669':'#dc2626';setTimeout(function(){btn.disabled=0},2000)}return}if(btn)btn.textContent='⏳ '+(i+1)+'/'+is.length;fj('/api/addtocart?itemId='+encodeURIComponent(is[i].cheapest.itemId)+'&shopId='+encodeURIComponent(is[i].cheapest.shopId)).then(function(d){if(d.success)ok++;else ng++;setTimeout(function(){nx(i+1)},1200)}).catch(function(){ng++;setTimeout(function(){nx(i+1)},1200)})}nx(0)
  }).catch(function(){toast('获取记录失败')})
}
function dH(id){
  if(!confirm('删除？'))return;
  fj('/api/history/delete?id='+encodeURIComponent(id)).then(function(d){if(d.success){var el=document.getElementById('hi_'+id);if(el)el.style.display='none';loadH()}}).catch(function(){})
}

// Cookie
function ckC(){
  fj('/api/cookie/status').then(function(d){
    var el=id('cookSt'),dot=id('cookDot'),bar=id('cookieBar'),ico=id('cookIcon'),txt=id('cookText'),act=id('cookAct');
    if(d.has_cookie){el.innerHTML='✅ Cookie 已设置 · '+d.cookie_len+' 字符';el.style.background='#f0fdf4';dot.style.background='#10b981'}
    else{el.innerHTML='❌ 未设置 Cookie';el.style.background='#fef2f2';dot.style.background='#ef4444'}
    if(!d.has_cookie){bar.style.display='flex';bar.className='invalid';ico.textContent='🔴';txt.textContent='未设置 Cookie';act.textContent='设置 →'}
    else if(d.is_valid){bar.style.display='flex';bar.className='valid';ico.textContent='🟢';txt.textContent='Cookie 正常'+(d.days_since_update>7?'，已用 '+d.days_since_update.toFixed(0)+' 天':'');act.textContent='→'}
    else{bar.style.display='flex';bar.className='invalid';ico.textContent='🔴';txt.textContent='Cookie 已失效';act.textContent='更新 →'}
    if(!d.has_cookie||!d.is_valid){id('fold_cookie')&&id('fold_cookie').classList.add('open');id('cookArrow')&&id('cookArrow').classList.add('open')}
  }).catch(function(){id('cookSt').innerHTML='⚠️ 获取失败';id('cookDot').style.background='#94a3b8'})
}
function saveCookie(){
  var inp=id('cookInp'),msg=id('cookMsg'),raw=inp.value.trim();
  if(!raw){msg.textContent='❌ 请输入';msg.style.color='#ef4444';return}
  fj('/api/cookie/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookie:raw})}).then(function(d){
    if(d.success){msg.textContent=d.warning?'⚠️ '+d.warning:'✅ 保存成功';msg.style.color=d.warning?'#f59e0b':'#10b981';ckC();inp.value=''}
    else{msg.textContent='❌ '+(d.error||'失败');msg.style.color='#ef4444'}
  }).catch(function(){msg.textContent='❌ 网络错误';msg.style.color='#ef4444'})
}

// OCR
function doOcr(files){
  var st=id('ocrSt');st.style.display='block';st.innerHTML='⏳ 识别 '+files.length+' 张...';st.style.color='#3b82f6';
  var all=[];
  function p(i){
    if(i>=files.length){
      if(all.length){st.innerHTML='✅ 识别到 <strong>'+all.length+'</strong> 个 ISBN';st.style.color='#059669';I.value=(I.value.trim()?I.value.trim()+'\\n':'')+all.join('\\n')}
      else{st.innerHTML='⚠️ 未识别到 ISBN';st.style.color='#d97706'}
      return
    }
    if(!files[i].type.startsWith('image/')){p(i+1);return}
    var fd=new FormData();fd.append('image',files[i]);
    fetch('/api/ocr',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
      if(d.isbns&&d.isbns.length)d.isbns.forEach(function(v){if(all.indexOf(v)===-1)all.push(v)});st.innerHTML='⏳ 已提取 '+all.length+' 个';p(i+1)
    }).catch(function(){p(i+1)})
  }
  p(0)
}

function toast(t){var el=id('toast');el.textContent=t;el.style.display='block';clearTimeout(el._t);el._t=setTimeout(function(){el.style.display='none'},2000)}

// 地址清理
function cleanupAddr(isAuto){
  var label=isAuto?'⏳':'🧹';
  fetch('/api/address/cleanup?dry_run=1').then(function(r){return r.json()}).then(function(d){
    if(d.error){toast('❌ '+d.error);return}
    if(d.success===false){
      if(!isAuto){
        var el=id('results');
        el.innerHTML='<div class="card" style="border:2px solid #fca5a5;background:#fef2f2;margin-bottom:10px"><div class="card-title" style="color:#dc2626">🧹 地址清理</div><div style="font-size:.8rem;color:#64748b">'+(d.error||'Cookie 未登录地址管理')+'<br><br>请先在浏览器登录 <strong>kongfz.com</strong>，然后更新 Cookie。</div></div>'+el.innerHTML;
      }
      return;
    }
    if(d.to_delete&&d.to_delete.length){
      var msg=label+' 发现 '+d.to_delete.length+' 个旧地址，清理中...';
      ss(msg,'loading');
      fetch('/api/address/cleanup?max='+d.max_count).then(function(r){return r.json()}).then(function(r2){
        if(r2.error){toast('❌ '+r2.error);return}
        if(r2.success===false){toast('⚠️ '+(r2.error||'失败'));return}
        toast('🧹 已删除 '+r2.deleted+' 个旧地址，保留 '+r2.kept+' 个');
        if(isAuto)return;
        var h='<div class="card" style="border:2px solid #10b981;background:#f0fdf4;margin-bottom:10px"><div class="card-title" style="color:#065f46">🧹 地址清理结果</div><div style="font-size:.8rem">共 <strong>'+d.total+'</strong> 个地址（上限 '+d.max_count+'），默认 <strong>'+d.default_count+'</strong> 个</div>';
        if(r2.deleted>0)h+='<div style="font-size:.78rem;color:#64748b;margin-top:4px">已删除 '+r2.deleted+' 个旧地址</div>';
        h+='</div>';
        var el=id('results');
        el.innerHTML=h+el.innerHTML;
        ss('✅ 清理完成','done');
      }).catch(function(){})
    }else{
      if(d.message&&d.message.indexOf('超过')===-1&&d.message.indexOf('未超过')===-1)return;
      if(!isAuto)toast('✅ 地址数量正常（共 '+d.total+' 个，上限 '+d.max_count+'）');
    }
  }).catch(function(){})
}

// 初始化
id('btnClear').onclick=function(){I.value='';E.innerHTML='';N.style.display='block';ss('就绪','')};
setTimeout(function(){ckC();loadH()},500);
// 启动时静默检查地址
setTimeout(function(){cleanupAddr(true)},3000);

// === 自检功能 ===
function selfCheck(){
  var btn = event && event.target;
  if(btn){btn.disabled=1;btn.style.opacity='.5'}
  var el = document.querySelector('.container');
  var html='<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px"><button onclick="loc()" style="padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;font-size:.8rem;cursor:pointer">← 返回查价</button><strong style="font-size:.9rem">🔍 系统自检</strong></div>';
  html+='<div class="card"><div class="card-title">⏳ 检测中...</div><div style="text-align:center;padding:20px;color:#94a3b8">正在检查各项功能...</div></div>';
  el.innerHTML = html;

  fj('/api/self_check').then(function(d){
    if(!d){el.innerHTML='<div class="card">❌ 自检失败</div>';return}
    var h='<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px"><button onclick="loc()" style="padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;font-size:.8rem;cursor:pointer">← 返回查价</button><strong style="font-size:.9rem">🔍 系统自检</strong><span style="font-size:.72rem;color:#94a3b8">'+d.time+'</span></div>';

    h += '<div class="card"><div class="card-title">📌 版本</div><table><tbody>';
    h += '<tr><td>Git 版本</td><td>'+esc(d.git_commit||'无')+'</td></tr>';
    h += '<tr><td>远程版本</td><td>'+(d.git_remote?esc(d.git_remote):'<span style="color:#f59e0b">未部署</span>')+'</td></tr>';
    var synced = d.git_commit && d.git_remote && d.git_commit.split(' ')[0] === d.git_remote.split(' ')[0];
    h += '<tr><td>本地↔云端</td><td>'+(synced?'<span style="color:#10b981">✅ 一致</span>':'<span style="color:#ef4444">❌ 不一致</span>')+'</td></tr>';
    if(d.git_dirty && d.git_dirty.length){
      h += '<tr><td>未提交改动</td><td><span style="color:#f59e0b">'+d.git_dirty.length+' 个文件</span></td></tr>';
    }
    h += '</tbody></table></div>';

    var cok = d.cookie||{};
    h += '<div class="card"><div class="card-title">🍪 Cookie</div><table><tbody>';
    h += '<tr><td>状态</td><td>'+(cok.valid?'<span style="color:#10b981">✅ 有效</span>':'<span style="color:#ef4444">❌ 无效</span>')+'</td></tr>';
    h += '<tr><td>长度</td><td>'+cok.len+' 字符</td></tr>';
    h += '</tbody></table></div>';

    var aq = d.api_query||{}, ac = d.api_addtocart||{};
    h += '<div class="card"><div class="card-title">📡 API 测试</div><table><tbody>';
    h += '<tr><td>查价</td><td>'+(aq.ok?'<span style="color:#10b981">✅</span>':'<span style="color:#ef4444">❌</span>')+'</td><td style="font-size:.75rem;color:#64748b">'+esc(aq.detail||'')+'</td></tr>';
    h += '<tr><td>加购</td><td>'+(ac.ok?'<span style="color:#10b981">✅</span>':'<span style="color:#ef4444">❌</span>')+'</td><td style="font-size:.75rem;color:#64748b">'+esc(ac.detail||'')+'</td></tr>';
    h += '</tbody></table></div>';

    h += '<div class="card"><div class="card-title">📄 关键文件</div><table><thead><tr><th>文件</th><th>修改时间</th><th>Hash</th></tr></thead><tbody>';
    var files = d.files||{};
    var fnames = Object.keys(files).sort();
    fnames.forEach(function(fn){
      var fi = files[fn];
      h += '<tr><td style="font-family:monospace;font-size:.72rem">'+esc(fn)+'</td><td>'+(fi.mtime||'-')+'</td><td style="font-family:monospace;font-size:.72rem;color:#64748b">'+(fi.hash||'-')+'</td></tr>';
    });
    h += '</tbody></table></div>';

    el.innerHTML = h;
    if(btn){btn.disabled=0;btn.style.opacity='1'}
  }).catch(function(){
    el.innerHTML = '<div class="card">❌ 自检请求失败</div>';
    if(btn){btn.disabled=0;btn.style.opacity='1'}
  })
}

// 一键记账（不弹窗，自动用最低总价）
function bookBuy(btn){
  var isbn=btn.dataset.isbn, title=btn.dataset.title, author=btn.dataset.author;
  var price=parseFloat(btn.dataset.price), shipping=parseFloat(btn.dataset.shipping);
  if(isNaN(price))price=0; if(isNaN(shipping))shipping=0;
  var cost=price+shipping;
  btn.disabled=1;btn.textContent='⏳';
  fj('/api/inventory/add',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({isbn:isbn,title:title,author:author,cost_price:cost,shipping:shipping,source_batch:''})
  }).then(function(d){
    if(d.success){btn.textContent='✅ 已记账';btn.style.background='#10b981';toast('📝 已记录进货 ¥'+cost.toFixed(1))}
    else{btn.textContent='❌';setTimeout(function(){btn.textContent='📝 记一笔';btn.disabled=0;btn.style.background='#f59e0b'},1500)}
  }).catch(function(){btn.textContent='❌';setTimeout(function(){btn.textContent='📝 记一笔';btn.disabled=0;btn.style.background='#f59e0b'},1500)})
}

function showInv(period){
  var cont=document.querySelector('.container');
  var html='<div class="stats-card" id="invStats">';
  html+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">';
  html+='<span style="font-weight:600;font-size:.95rem">📊 盈亏看板</span>';
  var d=new Date(),ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');
  d.setMonth(d.getMonth()-1); var lm=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');
  html+='<div style="display:flex;gap:4px">';
  html+='<button class="per-btn'+(period===''||period===undefined?' on':'')+'" onclick="showInv(\\'\\')">全部</button>';
  html+='<button class="per-btn'+(period===ym?' on':'')+'" onclick="showInv(\\''+ym+'\\')">本月</button>';
  html+='<button class="per-btn'+(period===lm?' on':'')+'" onclick="showInv(\\''+lm+'\\')">上月</button>';
  html+='</div></div><div id="invStatsBody"><div class="sg"><div><div class="n">—</div><div class="l">收入</div></div><div><div class="n">—</div><div class="l">成本</div></div><div><div class="n">—</div><div class="l">利润</div></div></div></div></div>';

  html+='<div style="display:flex;gap:6px;margin-bottom:6px">';
  html+='<input id="invQ" placeholder="🔍 搜书名/ISBN" style="flex:1;padding:6px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:.82rem;outline:none" oninput="invFilter()">';
  html+='</div>';
  html+='<div class="inv-tabs" id="invTabs">';
  html+='<button class="on" data-s="" onclick="invTab(this)">全部</button>';
  html+='<button data-s="in_stock" onclick="invTab(this)">📦 在库</button>';
  html+='<button data-s="sold" onclick="invTab(this)">💰 已售</button>';
  html+='</div><div id="invList"><div class="inv-empty"><div class="big">📦</div>加载中...</div></div>';

  cont.insertAdjacentHTML('afterbegin','<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px"><button onclick="loc()" style="padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;font-size:.8rem;cursor:pointer">← 返回查价</button><strong style="font-size:.9rem">📒 账本</strong></div>');
  cont.innerHTML=html;
  setTimeout(function(){invFilter();loadStats(period||'')}, 100);
}

function loc(){location.reload()}
function invTab(btn){
  document.querySelectorAll('#invTabs button').forEach(function(b){b.classList.remove('on')});
  btn.classList.add('on'); invFilter()
}
function invFilter(){
  var el=document.getElementById('invQ'); var q=el?el.value.trim().toLowerCase():'';
  var sel=document.querySelector('#invTabs .on'); var s=sel?sel.dataset.s:'';
  var u='/api/inventory/list?'; if(s)u+='status='+s+'&'; if(q)u+='q='+encodeURIComponent(q);
  fetch(u).then(function(r){return r.json()}).then(function(d){renderInv(d.items||[])}).catch(function(){})
}
function renderInv(items){
  var el=document.getElementById('invList'); if(!el)return;
  if(!items.length){el.innerHTML='<div class="inv-empty"><div class="big">📦</div>还没有记录<br>查价后点「标记已买」开始记录</div>'; return}
  el.innerHTML=items.map(function(i){
    var act='';
    if(i.status==='in_stock'){
      act='<button class="btn-g" onclick="sellInv('+i.id+')">💰 卖出</button><button class="btn-ghost" onclick="delInv('+i.id+')">✕</button>';
    }else{
      var pf=((i.sale_price||0)-i.total_cost).toFixed(1);
      act='<span style="font-weight:600;color:'+(pf>=0?'#059669':'#dc2626')+'">¥'+pf+'</span>';
      act+='<button class="btn-ghost" onclick="modPrice('+i.id+','+(i.sale_price||0)+')">✏️</button>';
    }
    var info=esc(i.title||'')+' <span style="color:#94a3b8;font-size:.7rem">'+(i.isbn||'')+'</span>';
    var meta='成本 ¥'+(i.total_cost||0).toFixed(1);
    if(i.status==='sold'&&i.sale_price)meta+=' → 卖 ¥'+(i.sale_price||0).toFixed(1);
    meta+=' · '+i.buy_date; if(i.sale_date)meta+=' → '+i.sale_date;
    return '<div class="inv-item"><div class="i-info"><div class="i-t">'+info+'</div><div class="i-m">'+meta+'</div></div><div class="i-act">'+act+'</div></div>'
  }).join('')
}
function sellInv(id){
  var p=prompt('💰 卖了多少钱？','');
  if(p===null)return; p=parseFloat(p); if(isNaN(p)||p<=0){toast('无效价格');return}
  fj('/api/inventory/sell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,sale_price:p})}).then(function(d){
    if(d.success){toast('✅ 已记录');invFilter();loadStats()}
    else{toast('❌ 保存失败')}
  }).catch(function(){toast('❌ 网络错误')})
}
function modPrice(id,old){
  var p=prompt('✏️ 修改售价：',old.toFixed(1));
  if(p===null)return; p=parseFloat(p); if(isNaN(p)||p<=0){toast('无效价格');return}
  fj('/api/inventory/update_sale_price',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,sale_price:p})}).then(function(d){
    if(d.success){toast('✅ 已更新');invFilter();loadStats()}
    else{toast('❌ 保存失败')}
  }).catch(function(){toast('❌ 网络错误')})
}
function delInv(id){
  if(!confirm('删除这条记录？'))return;
  fj('/api/inventory/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})}).then(function(d){
    if(d.success){toast('已删除');invFilter();loadStats()}
  }).catch(function(){})
}
function loadStats(period){
  var u='/api/inventory/stats'; if(period)u+='?period='+encodeURIComponent(period);
  fetch(u).then(function(r){return r.json()}).then(function(d){
    var el=document.getElementById('invStatsBody'); if(!el)return;
    var c=d.profit>=0?'#86efac':'#fca5a5';
    var h='<div class="sg"><div><div class="n">¥'+(d.total_revenue||0).toFixed(1)+'</div><div class="l">收入</div></div>';
    h+='<div><div class="n">¥'+(d.total_cost||0).toFixed(1)+'</div><div class="l">成本</div></div>';
    h+='<div><div class="n" style="color:'+c+'">¥'+(d.profit||0).toFixed(1)+'</div><div class="l">利润</div></div></div>';
    h+='<div class="se"><span>毛利率</span><span>'+(d.margin||0)+'%</span></div>';
    h+='<div class="se"><span>已售</span><span>'+d.sold_count+' 本</span></div>';
    h+='<div class="se"><span>在库</span><span>'+d.in_stock_count+' 本</span></div>';
    if(d.best_book)h+='<div class="se"><span>最赚的书</span><span>'+esc(d.best_book.title)+'  +¥'+d.best_book.profit.toFixed(1)+'</span></div>';
    el.innerHTML=h;
  }).catch(function(){}
)}
</script>
</body>
</html>

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
