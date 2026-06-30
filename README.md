<p align="center">
  <img src="./logo.png" alt="Academic Figure Generator Logo" width="220" />
</p>

# Academic Figure Generator

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

AI 驱动的学术论文配图生成工具（个人本地版）。上传论文 → AI 分析内容生成 Prompt → 一键生成高质量科研配图。

> **一句话**：把"写完论文还要画图"的痛点，变成「上传 → 确认 → 下载」三步流程。

## 示例配图

以下均为本平台实际生成的学术配图示例：

<table>
<tr>
<td align="center" width="50%">
<img src="docs/images/example-architecture.png" alt="网络架构图示例" />
<br/><sub><b>PMST 预测网络架构图</b></sub>
</td>
<td align="center" width="50%">
<img src="docs/images/example-signal.png" alt="信号处理流程图示例" />
<br/><sub><b>时频域信号处理流程图</b></sub>
</td>
</tr>
<tr>
<td align="center" width="50%">
<img src="docs/images/example-network.png" alt="深度学习模块详图示例" />
<br/><sub><b>深度学习模块详解图</b></sub>
</td>
<td align="center" width="50%">
<img src="docs/images/example-anatomy.png" alt="带标注的解剖图示例" />
<br/><sub><b>带标注的解剖结构图</b></sub>
</td>
</tr>
</table>

## 功能特性

| 功能 | 说明 |
|------|------|
| 🤖 **智能 Prompt 生成** | 上传 PDF/DOCX/TXT 论文，OpenAI Responses API 自动分析内容并生成配图描述 |
| 🖼️ **高质量配图** | 支持 1K/2K/4K 多分辨率，16:9/4:3/1:1 等多种比例 |
| 🎨 **配色方案** | 50+ 预设学术配色（含色盲友好方案），支持自定义配色 |
| ✏️ **图生图编辑** | 基于已有图片 + 文字指令进行二次编辑 |
| ⚡ **实时状态** | SSE 流式推送生成进度，无需手动刷新 |
| 📁 **项目管理** | 按项目组织论文、Prompt 和配图 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI · SQLAlchemy (Async) · Python 3.12+ |
| 前端 | React 19 · TypeScript · Vite · Tailwind CSS · Radix UI |
| 数据库 | SQLite (自动创建，零配置) |
| 存储 | 本地文件系统 (`backend/data/`) |
| AI (Prompt) | OpenAI Responses API (`gpt-5.5` 默认) |
| AI (配图) | OpenAI Images API (`gpt-image-2` 默认) |

## 项目结构

```
academic-figure-generator/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # API 路由 (projects, documents, prompts, images, color_schemes)
│   │   ├── models/           # SQLAlchemy ORM 模型 (SQLite)
│   │   ├── schemas/          # Pydantic 请求/响应 Schema
│   │   ├── services/         # 业务逻辑层
│   │   │   ├── openai_prompt_service.py # OpenAI Responses API 集成
│   │   │   ├── local_storage_service.py # 本地文件存储
│   │   │   ├── image_service.py         # OpenAI 图片生成/编辑
│   │   │   ├── document_service.py      # PDF/DOCX/TXT 解析
│   │   │   └── prompt_service.py        # Prompt CRUD
│   │   ├── core/             # 中间件、异常处理、Prompt 模板/配色
│   │   ├── config.py         # 环境变量配置
│   │   └── main.py           # FastAPI 应用工厂
│   ├── data/                 # 运行时数据 (SQLite DB, 上传文件, 生成图片)
│   └── pyproject.toml
├── frontend/                 # React SPA 前端
│   ├── src/
│   │   ├── pages/            # 页面组件 (Projects, ProjectWorkspace, Generate, ColorSchemes, Settings)
│   │   ├── components/ui/    # Radix UI 组件库
│   │   ├── store/            # Zustand 状态管理
│   │   └── lib/              # API 客户端
│   ├── package.json
│   └── vite.config.ts
├── academic-figure-prompt/   # AI Coding Agent Skill (SKILL.md)
├── .env                      # 环境变量
└── README.md
```

## 快速开始

### 前置要求

- **Python 3.12+**
- **Node.js 18+**
- **OpenAI API Key**：用于 Prompt 生成和图片生成

### 1. 克隆仓库

```bash
git clone https://github.com/amos689/academic-figure-generator.git
cd academic-figure-generator
```

### 2. 配置环境变量

推荐把 OpenAI API key 放在 Mac / 系统环境变量中：

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

也可以创建项目根目录或 `backend/` 目录下的 `.env` 文件：

```bash
OPENAI_API_KEY=your-openai-api-key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_TEXT_MODEL=gpt-5.5
OPENAI_TEXT_REASONING_EFFORT=medium
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=high
```

密钥读取优先级：系统环境变量 → 本地 `.env` → `backend/app/config.py` 中的默认空位。
开源提交前请勿提交任何真实 API key。

### 3. 启动后端

```bash
cd backend

# 创建虚拟环境 (推荐)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -e .

# 启动开发服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

首次启动时会自动创建 SQLite 数据库 (`backend/data/app.db`) 和数据目录。

### 4. 启动前端

```bash
cd frontend

npm install
npm run dev
```

### 5. 访问

| 服务 | 地址 |
|------|------|
| 应用首页 | http://localhost:5173 |
| API 文档 (Swagger) | http://localhost:8000/docs |

## 使用流程

### 核心工作流

```
上传论文 (PDF/DOCX/TXT)
    │
    ▼
后端解析 → 提取文本和章节结构
    │
    ▼
OpenAI Responses API → 分析论文 → 生成配图 Prompt
    │
    ▼
确认/编辑 Prompt → 选择分辨率和比例
    │
    ▼
OpenAI Images API → 生成高质量配图
    │
    ▼
下载图片 / 图生图编辑
```

### 快捷生成

除了项目工作流，还支持**快捷生成**模式：直接输入 Prompt 文本，跳过论文上传步骤，快速生成配图。

## 架构概览

```
浏览器 (React SPA)
    │
    ▼
FastAPI 后端 (localhost:8000)
    │
    ├── SQLite (项目、文档、Prompt、图片元数据)
    ├── 本地文件系统 (上传文件、生成图片)
    │
    ├── OpenAI Responses API → Prompt 生成 (同步)
    └── OpenAI Images API → 图片生成/编辑 (异步后台任务)
```

## 环境变量参考

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `OPENAI_API_KEY` | 是 | — | OpenAI API Key，用于 Prompt 和图片生成 |
| `OPENAI_API_BASE` | 否 | `https://api.openai.com/v1` | OpenAI API 地址 |
| `OPENAI_TEXT_MODEL` | 否 | `gpt-5.5` | Prompt 生成模型 |
| `OPENAI_TEXT_REASONING_EFFORT` | 否 | `medium` | Prompt 生成推理强度 |
| `OPENAI_TEXT_MAX_OUTPUT_TOKENS` | 否 | `12000` | Prompt 生成最大输出 token |
| `OPENAI_IMAGE_MODEL` | 否 | `gpt-image-2` | 图片生成/编辑模型 |
| `OPENAI_IMAGE_QUALITY` | 否 | `high` | 图片质量 |
| `DATABASE_PATH` | 否 | `./data/app.db` | SQLite 数据库路径 |
| `DATA_DIR` | 否 | `./data` | 数据存储目录 |
| `DEBUG` | 否 | `true` | 调试模式 (启用 API 文档) |
| `CORS_ORIGINS` | 否 | `["http://localhost:3000","http://localhost:5173"]` | CORS 允许来源 |
| `MAX_UPLOAD_SIZE_MB` | 否 | `50` | 最大上传文件大小 (MB) |

## AI 学术配图 Prompt 技能（AI Coding Agent Skill）

本项目附带了两个独立的 **AI Coding Agent Skill**——`academic-figure-prompt` 与 `academic-figure-prompt-pastel`。它们可直接在 Codex 或其他支持本地 Skill 的 AI 编程助手中使用，也可作为后端 OpenAI Prompt 模板的参考来源；无需部署完整平台即可获得顶会级学术论文配图提示词生成能力。

### 功能简介

`academic-figure-prompt` 是一个专为学术论文设计的 AI 提示词生成器，能够：

- 📄 阅读并分析论文内容（PDF / LaTeX / Word）
- 🎨 提供 **8 种预设学术配色方案**（Okabe-Ito、Blue 单色系、Teal+Amber 等），含色盲友好选项
- 🖼️ 生成极其详细的英文提示词，用于 AI 图片工具生成顶会级别的专业配图
- 📐 覆盖多种图表类型：框架图、网络架构图、模块详解图、对比/消融图、数据模板图

### 安装方式

#### 方式 1：使用 npx skills 一键安装（推荐）

```bash
npx skills add amos689/academic-figure-generator
```

#### 方式 2：手动安装

```bash
git clone https://github.com/amos689/academic-figure-generator.git

# Codex
cp -r academic-figure-generator/academic-figure-prompt ~/.codex/skills/
cp -r academic-figure-generator/academic-figure-prompt-pastel ~/.codex/skills/
```

### 使用方法

安装后，在 AI 编程助手对话中直接触发即可：

```
You: 帮我看一下这篇论文，生成论文配图提示词
AI:  [分析论文内容 → 展示配色方案选择 → 生成详细英文提示词]

You: 用 Teal+Amber 配色，帮我画一个网络架构图的提示词
AI:  [直接使用方案C生成网络架构图提示词]
```

在 Codex 中也可以直接使用本仓库随附的 Skill：

```
帮我阅读这篇论文，生成论文配图提示词
pastel风格论文配图
modern ML figure prompt
```

## 开发指南

### 后端开发

```bash
cd backend
source .venv/bin/activate

# 运行测试
pytest -v

# 代码检查
ruff check app/
ruff format app/
```

### 前端开发

```bash
cd frontend
npm run dev     # 启动开发服务器 (localhost:5173)
npm run build   # 生产构建
npm run lint    # ESLint 检查
```

前端开发服务器会自动将 `/api` 请求代理到 `localhost:8000`。

## 致谢

感谢 [Linux DO](https://linux.do/) 社区的支持与帮助 🙏

## 许可证

本项目基于 [MIT License](./LICENSE) 开源。
