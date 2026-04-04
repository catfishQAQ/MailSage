# MailSage 安装指南

## 环境要求

| 工具 | 最低版本 | 说明 |
|---|---|---|
| Python | 3.11+ | 后端运行时 |
| Node.js | 18+ | 前端构建工具 |
| Ollama | 最新版 | 本地 AI 引擎 |

---

## 第一步：安装 Ollama 并下载模型

### 1.1 安装 Ollama

前往 [https://ollama.com/download](https://ollama.com/download) 下载对应系统的安装包并完成安装。

安装完成后，Ollama 会在后台自动运行（默认监听 `http://localhost:11434`）。

### 1.2 下载 qwen3:4b 模型

打开终端，执行：

```bash
ollama pull qwen3:4b
```

> 模型约 2.6 GB，下载时间取决于网络速度。下载完成后可用 `ollama list` 确认。

---

## 第二步：安装后端

> 以下命令均在项目根目录（含 `backend/` 和 `frontend/` 的那层）下执行。

### 2.1 进入后端目录

```bash
cd backend
```

### 2.2 创建并激活虚拟环境（推荐）

**Windows：**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux：**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

> 激活后终端前缀会出现 `(.venv)`，表示已进入虚拟环境。

### 2.3 安装 Python 依赖

```bash
pip install -r requirements.txt
```

> 国内网络可加镜像源加速：
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### 2.4 启动后端服务

```bash
uvicorn main:app --reload --port 8000
```

看到以下输出说明启动成功：
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     AI 队列 worker 已启动
INFO:     定时任务调度器已启动（每 2 小时）
```

**验证：** 浏览器打开 [http://localhost:8000/docs](http://localhost:8000/docs)，可看到完整的 API 文档界面。

---

## 第三步：安装前端

打开另一个终端窗口（保持后端运行）：

### 3.1 进入前端目录

```bash
cd frontend
```

### 3.2 安装 Node.js 依赖

```bash
npm install
```

### 3.3 启动前端开发服务器

```bash
npm run dev
```

看到以下输出说明启动成功：
```
  VITE v6.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

浏览器打开 [http://localhost:5173](http://localhost:5173) 即可使用。

---

## 第四步：首次配置

### 4.1 添加邮箱账号

打开 [http://localhost:5173](http://localhost:5173)，点击左侧边栏底部的 **＋ 添加账号** 按钮，弹出添加账号窗口。

填写以下信息：

| 字段 | 说明 |
|---|---|
| 邮箱地址 | 完整邮箱地址，例如 `your@163.com` |
| 显示名称 | 可选，仅用于界面显示 |
| 授权码 / 应用专用密码 | **不是登录密码**，需在邮箱设置中生成（见下方说明） |
| IMAP 服务器 / 端口 | 输入邮箱地址后失焦会自动填充，常见邮箱无需手动填写 |
| SMTP 服务器 / 端口 | 同上，自动填充 |

点击 **添加** 后，系统会自动触发首次同步（拉取最近 200 封邮件）。

> **自动填充支持：** 163、126、yeah.net、QQ、Foxmail、Gmail、Outlook、Hotmail、Live

#### 如何获取授权码

**QQ 邮箱：**
1. 打开 QQ 邮箱网页版 → 设置 → 账号
2. 找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务」
3. 开启「IMAP/SMTP 服务」，按提示发送短信验证
4. 生成并复制授权码

**163 邮箱：**
1. 打开 163 邮箱 → 设置 → POP3/SMTP/IMAP
2. 开启 IMAP/SMTP 服务，设置授权密码

**Gmail：**
1. 开启两步验证（账号安全设置）
2. 搜索「应用专用密码」，为 MailSage 生成一个 16 位密码

### 4.2 设置个人身份预设（Persona）

在前端界面左侧边栏底部点击 **⚙️ 身份预设**，填入你的角色信息：

- **职业角色：** 例如「计算机视觉研究员」
- **关注领域：** 例如「自动驾驶模型的对抗性攻击、VAEs 架构调试」
- **语气偏好：** 例如「专业、客观、直接」

这些信息会作为 AI 的上下文，让摘要和回复更贴近你的实际工作场景。

### 4.3 运行 AI 批处理

确认 Ollama 正在运行后，点击左侧边栏底部 **AI 控制台** 中的 **⚡️ 批量处理未读邮件** 按钮。

- 状态灯 🟢 = Ollama 运行中，可触发
- 状态灯 🟡 = 正在处理队列中
- 状态灯 ⚪️ = Ollama 未运行，请先启动 Ollama

处理完成后，邮件列表中重要邮件会显示 ⚡️ 标记，点击邮件可查看 AI 摘要卡片和幽灵文本回复建议。

---

## 常用命令速查

```bash
# 启动 Ollama（若未自动运行）
ollama serve

# 启动后端（在 backend/ 目录，激活虚拟环境后）
uvicorn main:app --reload --port 8000

# 启动前端（在 frontend/ 目录）
npm run dev
```

---

## 常见问题

**Q: 前端显示「Ollama 未运行」**
- 检查 Ollama 是否启动：打开终端运行 `ollama list`，若无响应则运行 `ollama serve`

**Q: 邮件同步失败**
- 确认 IMAP 服务已在邮箱设置中开启
- 确认填写的是授权码/应用密码，不是登录密码
- QQ 邮箱需每隔一段时间重新生成授权码

**Q: AI 处理结果一直是 `failed`**
- 确认 `qwen3:4b` 已成功下载：`ollama list`
- 查看后端终端输出的错误日志
- 检查系统剩余内存/显存是否足够（qwen3:4b 约需 4GB 内存）

**Q: `pip install` 报错**
- 确认 Python 版本 ≥ 3.11：`python --version`
- 尝试升级 pip：`pip install --upgrade pip`

**Q: 首次启动后端报数据库错误**
- 删除 `backend/omnimail.db` 文件后重新启动，数据库会自动重建
