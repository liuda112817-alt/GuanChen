# 观尘前端及前后端联调验收

## 实现结果

React + TypeScript 前端在 `frontend/`；雾白/青黛/朱砂设计，桌面三栏、手机导航、浅深主题。首页与回答界面使用「观尘」品牌，没有版本号。对接已有真实 FastAPI 契约：流式对话、引用、增量资料、匿名会话恢复、六爻确认/修改/取消。

真实浏览器测试发现「梦境后显式请求用八字分析」仍继续解梦，已补充后端高精度规则及领域切换回归测试。六爻显式用法一并补齐。恢复历史时将内部确认命令映射为用户可读文本。追加服务存活端点，以及语料导入不完整时非零退出，避免误认为初始化成功。

## 已验证

| 验证 | 结果 |
| --- | --- |
| 后端默认回归 | 470 passed |
| PostgreSQL 独立测试库集成 | 43 passed |
| 真实模型 + PostgreSQL + HTTP/SSE | 39 checks，PASS，见 stage11_backend/report.md |
| 桌面真实浏览器全链路 | PASS：知识/来源、梦境、八字缺失与补全、六爻中断、刷新、取消 |
| 手机真实浏览器全链路 | 同上，PASS |
| 桌面与手机契约浏览器测试 | 20 passed，覆盖确认只提交一次、修改、取消、刷新、401/409/422/504、SSE error、截断恢复、安全 Markdown |
| SSE 分帧与历史恢复单元测试 | 5 passed |
| TypeScript 与生产构建 | PASS，产物 frontend/dist |
| 首页/说明抽屉自动无障碍检查 | 浅深主题、桌面/手机 WCAG A/AA 自动规则通过；不等同人工全面认证 |
| npm 依赖检查 | 安装时全依赖审计零漏洞；生产依赖审计零漏洞 |
| Compose 结构检查 | 使用临时示例配置通过，测试配置已删除 |
| Python 修改文件 Ruff 检查 | PASS |

浏览器契约测试使用测试响应，不计作真实模型验证；两项 real.spec.ts 测试单独连接本地真实后端。所有使用的出生资料是合成测试资料。

本机并行启动多份模型进程曾触发 MemoryError；改为串行后 HTTP 全套包括进程重启、凭证/资料恢复、确定性起卦一次、重复确认拒绝都通过。

## 部署交接边界

准备了 API/前端 Dockerfile、PostgreSQL 持久卷、单 worker 服务、自动重启、日志轮转、Nginx SSE/安全头/限流、Caddy HTTPS 配置与数据库备份脚本。云服务器、域名和证书尚未操作。

容器镜像构建尝试失败于 Docker Hub 授权服务连接超时，尚未完成镜像构建及 Linux 容器实机启动验收。Compose 静态检查通过不能替代这些验证。下一阶段必须在网络可用的构建机或腾讯云上构建，并验证 HTTPS、域名、数据库备份恢复及实际资源容量，才能判定公开上线就绪。

本次结论：前端及本地真实前后端业务链路已完成，可以进入腾讯云部署验证；尚不能声明云端部署已验收或承诺特定并发容量。操作步骤见 `docs/frontend_and_deployment.md`。

界面截图：`frontend-home-desktop.png`、`frontend-home-mobile.png`、`frontend-home-dark.png`；真实问答截图：`frontend-desktop-answer.png`、`frontend-mobile-answer.png`。
