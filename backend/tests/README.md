# 测试说明

## 后端测试（pytest）

环境：SQLite in-memory + mock Neo4j/Qwen，无需真实 MySQL/Neo4j/Redis。

```bash
cd backend
uv sync --group dev
uv run pytest tests/             # 全部
uv run pytest tests/test_auth_api.py -v
uv run pytest --cov=app tests/   # 覆盖率
```

### 测试文件

| 文件 | 覆盖 |
|------|------|
| `test_utils.py` | 余弦相似度、min-max 归一化、内容过滤 |
| `test_auth_api.py` | 注册/登录/JWT/封禁检查 |
| `test_post_api.py` | 帖子 CRUD、行为埋点、权限拦截 |
| `test_engines.py` | 六路召回引擎（CF/Swing/Graph/Semantic/Knowledge/Hot） |
| `test_feature_extractor.py` | 18 维特征输出维度与默认值 |
| `test_performance.py` | 关键接口与召回引擎响应时间回归 |

共 49 个用例。

## 前端测试（Vitest）

```bash
cd frontend
npm install
npm test                 # 全部
npm run test:watch       # 监听模式
npm run test:coverage    # 覆盖率
```

### 测试文件

| 文件 | 覆盖 |
|------|------|
| `tests/components/PostCard.spec.js` | 帖子卡片渲染 / 路由跳转 |
| `tests/components/RecCard.spec.js` | 推荐卡片、推荐理由与反馈事件 |
| `tests/api/post.spec.js` | 帖子 API 客户端参数拼接 |

共 17 个用例。
