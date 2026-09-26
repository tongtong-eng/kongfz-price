# 📚 孔夫子 ISBN 查价 · 云服务

批量查 ISBN 在孔夫子旧书网的最低进货价，支持一键加购。

## 🚀 一键部署

### 推荐：Zeabur（国内速度快）

[Zeabur](https://zeabur.com) 是国内开发者做的平台，国内访问速度快，免费额度足够个人用。

1. 注册 [Zeabur](https://zeabur.com)
2. 创建新项目 → 选择 GitHub 仓库部署
3. 或使用 zeabur CLI：
   ```bash
   # 安装 CLI（Mac）
   brew install zeabur
   # 或 curl -fsSL https://zeabur.com/install.sh | sh
   
   cd /path/to/kongfz_cloud
   zeabur deploy
   ```
4. 部署完成后，Zeabur 会分配一个 `*.zeabur.app` 域名
5. **关键：将环境变量 `PORT` 设置为 `5000`**（Zeabur 默认会设置，无需手动操作）

### 备选：Railway（国际）

1. 注册 [Railway](https://railway.app)
2. New Project → Deploy from GitHub repo
3. 选择包含本项目文件的仓库
4. Railway 会自动识别 `Procfile` 和 `requirements.txt`
5. 部署完成后获得 `*.railway.app` 域名

### 备选：Fly.io

```bash
# 安装 flyctl
brew install flyctl

# 登录并部署
cd /path/to/kongfz_cloud
fly launch --name kongfz-price
fly deploy
```

## 📲 手机使用（PWA）

部署完成后，**用手机浏览器打开你的域名**：

1. **iPhone（Safari）**：
   - 打开域名 → 点底部分享按钮 → **「添加到主屏幕」**
   - 之后在桌面像 App 一样打开，全屏无浏览器栏

2. **Android（Chrome）**：
   - 打开域名 → 底部会弹出「添加到主屏幕」提示
   - 或点菜单 → 「添加到主屏幕」
   - 之后在桌面以独立窗口运行

## 🍪 获取 Cookie

**手机操作：**

1. 在手机 Safari/Chrome 打开 [kongfz.com](https://www.kongfz.com) 并登录
2. 在地址栏输入（完整复制粘贴）：
   ```
   javascript:prompt('复制 Cookie',document.cookie)
   ```
3. 回车后会弹出提示框，**全选文本 → 复制**
4. 回到查价工具 → Cookie 设置 → 粘贴 → 保存

**电脑操作（更简单）：**

1. 电脑浏览器打开 kongfz.com 并登录
2. `F12` → `Network` 标签 → 刷新页面
3. 点第一个请求 → 复制请求的 `Cookie` 头
4. 发送到手机 → 在查价工具中粘贴保存

## ⚙️ 本地开发

```bash
cd kongfz_cloud
python app.py
# 打开 http://localhost:5000
```

## 📂 文件说明

```
kongfz_cloud/
├── app.py              # 主服务（支持 PORT 环境变量）
├── index.html          # 前端页面（PWA 支持）
├── kongfz_cookie.py    # Cookie 管理模块
├── static/
│   ├── manifest.json   # PWA 清单
│   ├── sw.js           # Service Worker
│   └── icon.svg        # 应用图标
├── data/               # 数据持久化目录
├── Procfile            # Railway 配置
├── zeabur.json         # Zeabur 配置
├── Dockerfile          # Docker 部署
└── requirements.txt
```

## 🔒 注意

- Cookie 会过期，过期后需要重新获取
- Cookie 存储在服务器 `data/` 目录下
- 部分云平台（如 Railway Free Plan）可能因不活动而休眠，首次访问需等几秒

## 🔑 访问口令（可选，推荐生产环境开启）

默认所有 `/api/*` 接口开放。为防止他人白嫖你的服务器去爬孔夫子、增删你的收货地址，
建议在部署平台设置环境变量 `ACCESS_TOKEN`（一个只有你知道的随机字符串）：

1. 在 Railway / Zeabur 的项目环境变量里添加 `ACCESS_TOKEN`（值随意，建议用长随机串）
2. 重新部署后，打开网站 → 底部「Cookie」→ 找到「🔒 访问口令」输入框
3. 填入与 `ACCESS_TOKEN` 完全一致的值，点「💾 保存口令」

设置后，未携带正确口令的请求会被拒绝（返回 401）。健康检查 `/api/health` 和首页不受影响。

## 📊 结构化日志 & 熔断状态

新增 `/api/logs` 接口（需携带访问口令），返回：

- `logs`：最近 200 条结构化日志（查询耗时、失败原因、限流/熔断事件）
- `stats`：累计统计（查询成功/失败数、限流命中数、熔断次数）
- `breaker`：熔断器实时状态（是否打开、连续失败次数）

反爬加固：限流退避从固定 3 秒改为**指数退避**（3s→6s→12s→…→60s 封顶），
连续 5 次触发限流会**打开熔断**，暂停 120 秒出站请求，避免硬碰孔夫子风控导致账号被封。
