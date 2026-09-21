# 观尘前端与部署交接

产品名称统一为「观尘」。前端现由本仓库直接实现，原 Bolt Prompt 保留为设计背景，不再依赖 Bolt。

## 本地使用

首次安装前端依赖：

```powershell
cd frontend
npm ci
```

在项目根目录启动数据库和后端：

```powershell
docker start guanchen_eval_db
.venv\Scripts\python.exe scripts/serve_api.py
```

另一个终端启动前端：

```powershell
cd frontend
npm run dev
```

访问 http://127.0.0.1:5173 。Vite 把 `/api` 转发到 `127.0.0.1:8000`。前端 `VITE_API_BASE_URL` 默认为空，同源模式不需要设置 CORS，也不会把 localhost 硬编码进生产文件。如使用独立 API 域名，必须配置该变量并在后端配置准确的 CORS 来源。

前端使用 React、TypeScript、Vite、Lucide 和安全 Markdown；主题跟随系统，手动选择后记住偏好。会话凭证只在 sessionStorage，主题偏好在 localStorage。匿名历史限当前标签页；没有账号、跨设备历史或用户自助服务端删除功能，不作相关承诺。

## 核心行为

- 首屏不收出生资料；四个示例只填入输入框。
- 流式请求采用带 Authorization 的 POST fetch，处理分帧、分字节中文、心跳、终止错误和不完整连接。
- 出生资料按后端 required_input.fields 收集，也可主动在「我的资料」中更正。前端不计算八字或卦象。
- 六爻确认、修改、取消全部使用当前 thread_id 和 confirmation_id；操作期间锁定提交。断线不自动重发，不自动重复起卦。
- 刷新和历史恢复读取服务端状态，409/504 先尝试取回状态；其他失败提供手动恢复。不会因 401 清空本地凭证。
- 引用原文从当前会话授权端点读取。后端只允许当前回答的引用，历史回答过期引用会提示不可用。
- 正文不执行 HTML，不加载模型输出中的远程图片；原文和模型解释分开展示。
- 输入支持中文输入法、桌面 Enter/Shift+Enter、手机发送按钮；滚动时尊重用户的阅读位置。

## 验证命令

```powershell
# 项目根目录
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/eval_stage11_backend.py

# frontend 目录
npm run build
npm test
npx playwright install chromium
npm run test:e2e

# 真实 API 浏览器联调：先启动本地 API，使用合成资料，消耗模型额度。
$env:GUANCHEN_REAL_E2E='1'
npx playwright test tests/real.spec.ts --project=desktop --workers=1
Remove-Item Env:GUANCHEN_REAL_E2E
```

常规浏览器测试使用测试路由响应，覆盖手机和桌面状态流；真实测试直接经过 Vite 代理、FastAPI、数据库和外部模型。两者不能互相替代。低内存电脑请串行运行模型验收，避免同时启动多份后端。

## 腾讯云单机部署方案

目录中提供的是部署准备文件；未连接或修改云主机、DNS、证书和备案。

```text
用户 HTTPS → 主机 Caddy :443 → 127.0.0.1:8080 Docker Nginx
                                     ├── 前端 dist
                                     └── /api → api:8000 → db:5432
```

API 固定一个 worker，沿用现有进程内会话锁，不能直接加 worker 或横向扩容。多副本需要先实现分布式锁和共享幂等。数据库和 API 不映射公网端口。Nginx 配置流式透传、请求限速、连接上限、安全头与静态资源缓存；Caddy 负责自动 HTTPS。Nginx 仅信任私网代理的 X-Real-IP，web 端口必须保持绑定 127.0.0.1，不能改成公网暴露。

建议在有足够内存和磁盘余量的新系统上部署；2GB 主机能否承载必须实测，不作为正式负载承诺。模型镜像和缓存占用需计入磁盘预算。首版只加载 BGE embedding；当前 reranker_enabled=False，重排适配器按需加载。

### 1. 准备文件与凭证

上传仓库源代码、锁文件、部署文件和 `data/knowledge/raw_verified`。不上传 `.venv`、`frontend/node_modules`、本地 `.env`、测试输出或 Git 历史。安装 Docker Engine/Compose 和 Caddy 后：

```sh
cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
```

填写数据库强密码和服务端模型配置。数据库密码使用随机十六进制字符串，避免 URL 编码歧义。所有模型密钥只存在 `deploy/.env`，绝不能写入 VITE_ 变量。

### 2. 构建、初始化和启动

在项目根目录执行：

```sh
docker compose --env-file deploy/.env -f deploy/compose.yml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yml build
docker compose --env-file deploy/.env -f deploy/compose.yml up -d db
docker compose --env-file deploy/.env -f deploy/compose.yml run --rm --no-deps api /app/.venv/bin/python scripts/ingest_corpus.py
docker compose --env-file deploy/.env -f deploy/compose.yml up -d
curl --fail http://127.0.0.1:8080/api/v1/health
```

必须先导入知识库，否则 API 会拒绝以空知识库启动。已有数据库也可通过 pg_dump/pg_restore 迁移，此时无需重复导入。不要把 Windows 的数据库物理目录直接复制给 Linux PostgreSQL。部署的 PostgreSQL 使用命名卷持久化；不要执行 `docker compose down -v`。

首次构建需要访问 Python/npm/Docker 镜像源，模型首次启动需要下载 Hugging Face 模型；服务器网络应先验证。`/api/v1/health` 只检查服务完成启动并能响应，不能替代模型、知识库和数据库的真实问答验收。

### 3. 域名与 HTTPS

先核对现有域名解析和大陆云主机备案状态，再将 `guanchen.online` 及 `www` 指向目标公网 IP。将 `deploy/Caddyfile` 部署到主机 Caddy 配置，验证后重载。安全组只开放业务所需 80/443；SSH 限制管理来源。第一次签发证书需要域名已经指向服务器且相关端口可达。

在 HTTPS 页面分别验证知识、梦境、八字补充资料、六爻确认/修改/取消、刷新恢复和手机布局。仍需检查服务重启、持久卷和备份恢复，才能对外宣布上线。

### 4. 备份、更新与回退

```sh
sh deploy/backup.sh
```

脚本在 `deploy/backups` 输出权限受限的 PostgreSQL 自定义格式备份，先写临时文件，成功后重命名。安排每日任务，并复制到另一台机器或对象存储；本机备份不能抵御整机丢失。恢复演练请在独立库执行 `pg_restore`，不要直接覆盖生产库。更新前备份数据库并记录旧镜像；保留旧镜像以便回退。容器日志按大小轮转。

部署文件参考：[Vite 构建说明](https://vite.dev/guide/build)、[Nginx 代理缓冲与超时](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)。
