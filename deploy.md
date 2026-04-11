# 部署文档：数据结构实验在线评测系统（GitHub Pages）

## 架构说明

本项目为纯静态网站，无需服务器后端：
- **前端**：HTML + CSS + JavaScript + CodeMirror 编辑器
- **代码执行**：调用免费的 [Piston API](https://github.com/engineer-man/piston) 在线编译运行 C 代码
- **部署**：GitHub Pages 静态托管

---

## 部署步骤

### 1. 创建 GitHub 仓库

1. 登录 GitHub，点击右上角 **+** → **New repository**
2. 仓库名填写 `code-judge`（或任意名称）
3. 选择 **Public**（GitHub Pages 免费版需要 Public，Pro 用户可以用 Private）
4. 点击 **Create repository**

### 2. 上传项目文件

方式一：命令行推送
```bash
cd D:/WORK/computer/code/Park/experiment

git init
git add index.html config.json static/ problems/
git commit -m "初始化评测系统"
git branch -M main
git remote add origin https://github.com/你的用户名/code-judge.git
git push -u origin main
```

> **注意**：不要上传 `.jpg` 图片文件和 `deploy.md`，只需要以下文件：
> - `index.html`
> - `config.json`
> - `static/` 目录
> - `problems/` 目录

方式二：网页上传

在仓库页面点击 **Add file** → **Upload files**，把上述文件拖拽上传。

### 3. 启用 GitHub Pages

1. 进入仓库页面 → **Settings** → 左侧 **Pages**
2. Source 选择 **Deploy from a branch**
3. Branch 选择 **main**，目录选 **/ (root)**
4. 点击 **Save**

等待 1-2 分钟，GitHub 会自动构建部署。

### 4. 访问网站

部署完成后，访问地址为：

```
https://你的用户名.github.io/code-judge/
```

---

## 更换周次与题目

### 1. 新建题目文件

在 `problems/` 目录下创建新的 JSON 文件，如 `week11.json`，格式参考 `week10.json`。

### 2. 修改配置

编辑 `config.json`：
```json
{
    "current_week": 11,
    "problems_file": "problems/week11.json"
}
```

或者直接修改 `static/js/main.js` 顶部的 `PROBLEMS_FILE` 变量：
```javascript
var PROBLEMS_FILE = "problems/week11.json";
```

### 3. 推送更新

```bash
git add -A
git commit -m "更新第11周题目"
git push
```

GitHub Pages 会在 1-2 分钟内自动更新。

---

## JSON 题目文件格式

```json
{
    "week": 11,
    "title": "第十一周实验课",
    "problems": [
        {
            "id": 1,
            "title": "题目标题",
            "description": "题目描述",
            "inputFormat": "输入格式说明",
            "outputFormat": "输出格式说明",
            "hint": "提示信息（可选）",
            "samples": [
                {
                    "input": "样例输入",
                    "output": "样例输出",
                    "explanation": "样例解释（可选）"
                }
            ],
            "testCases": [
                { "input": "测试输入", "output": "期望输出" }
            ],
            "template": "#include <stdio.h>\n// 代码模板..."
        }
    ]
}
```

---

## 注意事项

- **Piston API** 是免费公共服务，有一定的速率限制，适合课堂规模使用
- 测试用例数据存放在前端 JSON 中，学生可以查看（这是设计如此，仅供自检）
- GitHub Pages 更新有 1-2 分钟延迟，推送后稍等即可
