# 10 — API 接口

## 总览

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/llm/chat` | 千问对话 |
| POST | `/api/llm/extract_tags` | 提取标签 |
| GET | `/api/recommend/{user_id}` | 获取推荐 |
| GET | `/api/recommend/{user_id}/reason/{post_id}` | 推荐理由 |
| POST | `/api/precompute` | 触发预计算 |
| GET | `/api/user/{user_id}` | 用户详情 |
| GET | `/api/user/list` | 用户列表 |
| GET | `/api/user/{user_id}/behaviors` | 行为记录 |
| GET | `/api/post/{post_id}` | 帖子详情 |
| GET | `/api/post/list` | 帖子列表 |
| GET | `/api/post/hot` | 热门帖子 |

---

## 推荐 API (`/api`)

### GET `/api/recommend/{user_id}`
**参数**:
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| top_n | int | 20 | 推荐数量 |
| enable_llm | bool | true | 是否启用 LLM Reranking |
| w_cf | float | — | CF 权重 (三个都传才生效) |
| w_graph | float | — | Graph 权重 |
| w_semantic | float | — | Semantic 权重 |

**响应**:
```json
{
  "user_id": 1,
  "recommendations": [
    {
      "post_id": 42,
      "final_score": 0.8234,
      "cf_score": 0.7100,
      "graph_score": 0.9200,
      "semantic_score": 0.8500,
      "title": "深度学习在NLP中的应用",
      "summary": "关于深度学习的计算机科学领域探讨",
      "author_id": 5
    }
  ]
}
```

### GET `/api/recommend/{user_id}/reason/{post_id}`
**响应**: `{"reason": "该用户对NLP和深度学习感兴趣，这篇文章..."}`

### POST `/api/precompute`
**响应**: `{"status": "预计算完成"}`

---

## 用户 API (`/api/user`)

### GET `/api/user/list?page=1&per_page=20`
```json
{
  "users": [
    {"id": 1, "username": "...", "email": "...", "bio": "...",
     "interest_profile": "...", "created_at": "..."}
  ],
  "total": 500,
  "page": 1
}
```

### GET `/api/user/{user_id}`
单个用户对象 (同上字段)

### GET `/api/user/{user_id}/behaviors?limit=50`
```json
{
  "behaviors": [
    {"id": 1, "user_id": 1, "post_id": 42,
     "behavior_type": "like", "duration": null, "created_at": "..."}
  ]
}
```

---

## 帖子 API (`/api/post`)

### GET `/api/post/list?page=1&per_page=20&domain_id=1`
```json
{
  "posts": [
    {"id": 42, "title": "...", "content": "...", "summary": "...",
     "author_id": 5, "domain_id": 1, "view_count": 120, "like_count": 35,
     "tags": ["机器学习", "深度学习"], "created_at": "..."}
  ],
  "total": 2000,
  "page": 1
}
```

### GET `/api/post/{post_id}`
单个帖子对象 (同上字段)

### GET `/api/post/hot?limit=20`
按 `like_count` 降序排列的热门帖子列表

---

## LLM API (`/api/llm`)

### POST `/api/llm/chat`
**请求**: `{"message": "什么是协同过滤?"}`
**响应**: `{"reply": "协同过滤是一种..."}`

### POST `/api/llm/extract_tags`
**请求**: `{"content": "文章正文..."}`
**响应**: `{"tags": ["ML", "NLP"], "summary": "...", "domain": "计算机科学"}`
