# KnowledgeRec · 知识社区推荐系统

面向知识社区的内容发布与个性化推荐平台。后端采用 Flask 提供 REST + WebSocket，推荐侧实现 **多路召回 + GBDT/XGBoost/LightGBM精排 + 后处理重排** 的可解释推荐管线；前端基于 Vue 3 + Element Plus 提供发帖、阅读、推荐流、互动、管理后台等完整体验。

仓库地址：<https://github.com/Clematis068/KnowledgeRec>

## 功能概览

- **内容生产**：发帖 / 编辑 / 删除、富文本摘要、标签与领域分类、封面缩略图
- **互动行为**：浏览、点赞、收藏、评论、关注、屏蔽、负反馈
- **个性化推荐**：6 路召回 + 加权融合 + 上下文加分 / 多样性 / 探索补足
- **推荐解释**：曝光时回溯每条推荐的命中路径与评分细节
- **搜索与热榜**：关键字检索、领域热门
- **管理后台**：用户 / 帖子 / 标签管理、内容过滤、系统监控
- **实时通知**：基于 Flask-SocketIO 的关注、评论、@ 提醒
- **冷启动 / 评估**：批量评估脚本、消融实验、在线 AB 框架

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.13、Flask、Flask-SQLAlchemy、Flask-SocketIO、APScheduler |
| 推荐 | LightGBM、scikit-learn、Faiss、NumPy、SciPy、千问 DashScope Embedding/LLM |
| 存储 | MySQL（业务数据）、Neo4j（知识图谱 / 社交图）、Redis（缓存） |
| 前端 | Vue 3 (`<script setup>`)、Vite、Element Plus、Pinia、Vue Router |
| 测试 | pytest、pytest-flask、Vitest、Vue Test Utils |
| 包管理 | uv（后端）、npm（前端） |

## 目录结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/              # 用户 / 帖子 / 推荐 / 通知 / 管理等蓝图
│   │   ├── services/
│   │   │   ├── recommendation/  # 6 路召回引擎 + 融合 + 精排 + 特征
│   │   │   ├── qwen_service.py  # 千问 Embedding / LLM 封装
│   │   │   └── vector_index.py  # Faiss 向量索引
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── utils/            # 通用工具、内容过滤、通知载荷
│   │   └── config.py
│   ├── scripts/              # 评估、导入、压测、绘图脚本
│   ├── tests/                # pytest 单元 / 集成测试
│   ├── reports/              # 评估输出
│   ├── pyproject.toml
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── views/            # 页面（推荐、搜索、热榜、详情、管理…）
│   │   ├── components/       # 推荐卡、用户、布局、管理等组件
│   │   ├── api/              # axios 接口封装
│   │   └── store/            # Pinia stores
│   ├── tests/                # Vitest 单测
│   └── vite.config.js
├── DESIGN.md                 # 系统设计说明
└── STARTUP.md                # 启动 / 部署手册
```

## 快速开始

### 环境准备

- Python ≥ 3.13、Node.js ≥ 18
- MySQL ≥ 8、Neo4j ≥ 5、Redis ≥ 7
- 千问 DashScope API Key（推荐与 LLM 解释依赖）

### 后端

```bash
cd backend
uv sync                  # 安装依赖
cp .env.example .env     # 配置数据库、Redis、Neo4j、DashScope 密钥
uv run python run.py     # 启动 Flask + SocketIO（默认 5000 端口）
```

### 前端

```bash
cd frontend
npm install
npm run dev              # 开发模式（默认 5173 端口）
npm run build            # 生产构建
npm run test             # Vitest
```

> 项目根目录提供 `st.sh` 一键启动脚本，可同时拉起后端和前端开发服务（详见 `STARTUP.md`）。

## License

仅用于本科毕业设计与学习交流，未单独声明开源协议，请勿用于商用或未经授权的二次发布。
