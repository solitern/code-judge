# Code Judge

一个面向数据结构实验课的轻量级 C 语言在线判题系统。教师可以在后台维护周次、题目、公开样例、隐藏案例和标准答案，学生无需登录即可编写代码并运行样例、自定义输入或全部测试案例。

项目采用 Vue 3 + TypeScript 构建前端，FastAPI + SQLite 提供业务接口，独立 Runner 容器使用 GCC 编译并在受限环境中执行学生代码。默认通过 Docker Compose 部署，可选使用 Caddy 自动配置 HTTPS。

## 功能

- 周次支持草稿、定时发布、立即发布、取消发布和归档。
- 题目支持 Markdown、C 语言代码模板、资源限制、公开样例和隐藏案例。
- 后台可上传整周 JSON，批量填写周次标题、题目和测试案例。
- 标准答案仅保存在服务端，发布前可运行全部案例进行验证。
- 学生端支持样例运行、自定义输入和全部案例判题，隐藏案例内容不会返回浏览器。
- 题目修改会生成版本快照，支持恢复；SQLite 支持在线备份和恢复。

## 快速部署

需要 Linux、Docker Engine 和 Docker Compose 插件。克隆项目后复制环境变量模板：

```bash
git clone https://github.com/solitern/code-judge.git
cd code-judge
cp .env.example .env
```

编辑 `.env`，生产环境至少应修改 `ADMIN_PASSWORD` 和 `SECRET_KEY`；可用 `openssl rand -hex 32` 生成随机密钥。若通过 HTTPS 访问，请同时设置正确的 `ALLOWED_ORIGIN`，并将 `COOKIE_SECURE` 改为 `true`。

```bash
docker compose build
docker compose up -d
docker compose ps
curl http://127.0.0.1:8000/api/health
```

应用默认监听 `8000` 端口，学生页面为 `http://服务器地址:8000/`，后台登录地址为 `http://服务器地址:8000/admin/login`。

如需由 Caddy 提供 HTTPS，请将 `.env` 中的 `CADDY_SITE_ADDRESS`、`ALLOWED_ORIGIN` 和 Cookie 设置配置好，再启动对应 profile：

```bash
docker compose --profile caddy up -d
```

## 题目管理与 JSON 导入

登录后台后先新建周次，再进入编辑页填写通知、题目、案例和标准答案。编辑页可以修改周次序号和标题；新序号只要还没有被其他周次占用就可以保存。顶部的“导入 JSON”可一次导入整周内容；上传文件中的 `week` 必须与当前周次一致。同 ID 的题目及测试案例会被覆盖，新增 ID 会创建新题目，未出现在文件中的已有题目会保留。

[example/week1.json](example/week1.json) 是可直接导入的最小示例，复制后修改 `week`、`title` 和 `problems` 即可。主要字段包括题目 ID、标题、描述、输入输出格式、代码模板、资源限制、公开样例 `samples`、隐藏案例 `testCases`，以及可选的标准答案 `solution`（也可用 `standard_answer` 或 `answer`）。导入的标准答案会标记为未验证，发布前仍需在后台验证。JSON 文件须使用 UTF-8 编码，单文件最大 5 MB。

发布前应为每道题保存并验证标准答案，再使用“草稿预览”检查学生端效果。定时发布时间在后台按北京时间填写，服务端统一以 UTC 保存和比较。

## 更新与运维

拉取新版本后需要重新构建镜像，因为前端和后端代码都会打包进 app 镜像：

```bash
git pull --ff-only
docker compose build
docker compose up -d
```

查看运行状态和日志：

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f runner
```

数据库保存在名为 `code-judge-app-data` 的 Docker Volume 中，普通的 `docker compose down` 不会删除数据；不要在未备份时执行 `docker compose down -v`。创建备份并复制到宿主机：

```bash
docker compose exec app python /app/scripts/backup.py --output /app/data/backup.db
docker compose cp app:/app/data/backup.db ./backup.db
```

恢复前请先保留当前数据库备份，然后将备份文件复制到容器并停止 app：

```bash
docker compose cp ./backup.db app:/app/data/restore.db
docker compose stop app
docker compose run --rm app python /app/scripts/restore.py --input /app/data/restore.db --force
docker compose up -d app
```

## 本地开发与测试

后端和 Runner 需要 Python 3.13，前端需要 Node.js 22，Runner 测试还需要 Linux、GCC 和 `unshare`。在各自目录安装依赖后可运行：

```bash
python -m pytest -q backend/tests
python -m pytest -q runner/tests

cd frontend
npm ci
npm test
npm run build
```

项目的主要目录如下：

```text
backend/       FastAPI 接口、数据模型、迁移与测试
frontend/      Vue 3 管理端和学生端
runner/        独立的 C 语言编译与执行服务
example/       可导入的题目 JSON 示例
scripts/       数据备份、恢复和 JSON 导入工具
```

## 安全说明

Runner 不暴露公网端口、不挂载数据库，并以非 root 用户、只读根文件系统、独立临时目录、用户与网络命名空间及资源限制执行代码。它仍不能等同于完整虚拟机隔离；若系统面向不可信公网用户，建议额外使用 gVisor、Kata Containers 或专用隔离节点。请勿为 Runner 挂载 Docker Socket，也不要启用 `privileged` 模式。

遇到问题时先检查 `docker compose ps`、应用日志以及 `/api/health`。如更新后页面仍显示旧内容，可执行一次强制刷新；HTML 响应已配置为不缓存，带哈希的静态资源则会长期缓存。
