# 02 — API 层

## axios 实例 (`api/index.js`)

```js
const request = axios.create({
  baseURL: '/api',
  timeout: 30000,   // 30秒超时，因为推荐API耗时长
})

// 响应拦截器：自动提取 res.data，错误时 ElMessage 弹窗
request.interceptors.response.use(
  (res) => res.data,       // 成功直接返回 data
  (err) => { ElMessage.error(msg); return Promise.reject(err) }
)
```

**设计要点**：
- 拦截器自动解包 `res.data`，调用方无需 `.data`
- 统一错误处理，展示后端返回的 `error` 字段

---

## 推荐 API (`api/recommendation.js`)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `getRecommendations(userId, opts)` | GET | `/recommend/{userId}` | 获取推荐列表 |
| `getRecommendReason(userId, postId)` | GET | `/recommend/{userId}/reason/{postId}` | LLM 生成推荐理由 |
| `triggerPrecompute()` | POST | `/precompute` | 触发离线预计算 |

### `getRecommendations` 参数
```js
{
  topN: 20,           // 推荐数量
  enableLlm: true,    // 是否启用 LLM reranking
  weights: {          // 三路权重 (可选)
    cf: 0.35,
    graph: 0.35,
    semantic: 0.30
  }
}
```

### 响应格式
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
      "title": "...",
      "summary": "...",
      "author_id": 5
    }
  ]
}
```

---

## 用户 API (`api/user.js`)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `getUserList(page, perPage)` | GET | `/user/list` | 用户分页列表 |
| `getUserDetail(userId)` | GET | `/user/{userId}` | 用户详情 |
| `getUserBehaviors(userId, limit)` | GET | `/user/{userId}/behaviors` | 行为记录 |

### 用户对象字段
`id, username, email, bio, interest_profile, created_at`

### 行为对象字段
`id, user_id, post_id, behavior_type(view/like/comment/share), duration, created_at`

---

## 帖子 API (`api/post.js`)

| 函数 | 方法 | 路径 | 用途 |
|------|------|------|------|
| `getPostList(page, perPage, domainId)` | GET | `/post/list` | 帖子分页列表 |
| `getPostDetail(postId)` | GET | `/post/{postId}` | 帖子详情 |
| `getHotPosts(limit)` | GET | `/post/hot` | 热门帖子 |

### 帖子对象字段
`id, title, content, summary, author_id, domain_id, view_count, like_count, tags[], created_at`
