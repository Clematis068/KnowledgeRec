import request from './index'

function buildRecommendParams({
  topN = 20,
  enableLlm = true,
  weights,
  debug = false,
  excludePostIds = [],
} = {}) {
  const params = {
    top_n: topN,
    enable_llm: enableLlm,
    debug,
  }

  if (excludePostIds.length) {
    params.exclude_post_ids = excludePostIds.join(',')
  }

  if (weights) {
    params.w_cf = weights.cf
    params.w_graph = weights.graph
    params.w_semantic = weights.semantic
  }

  return params
}

/** 获取用户推荐列表 */
export function getRecommendations(
  userId,
  { topN = 20, enableLlm = true, weights, debug = false, excludePostIds = [] } = {},
) {
  return request.get(`/recommend/${userId}`, {
    params: buildRecommendParams({ topN, enableLlm, weights, debug, excludePostIds }),
  })
}

/** 获取当前登录用户的推荐 */
export function getMyRecommendations({ topN = 20, enableLlm = true, weights, debug = false, excludePostIds = [] } = {}) {
  return request.get('/recommend/me', {
    params: buildRecommendParams({ topN, enableLlm, weights, debug, excludePostIds }),
  })
}

/** 获取推荐理由（可附带召回通道分数，帮助 LLM 生成更具体的解释） */
export function getRecommendReason(userId, postId, channelScores = null) {
  const params = {}
  if (channelScores) {
    for (const key of ['cf', 'swing', 'graph', 'semantic', 'knowledge', 'hot']) {
      const val = channelScores[`${key}_score`]
      if (val !== undefined && val !== null) {
        params[`${key}_score`] = val
      }
    }
  }
  return request.get(`/recommend/${userId}/reason/${postId}`, { params })
}

/**
 * 流式获取推荐理由（SSE）
 *
 * 事件回调：
 *   onMeta({ graph_paths, graph_path?, top_channels? })  — 证据面板立即渲染
 *   onDelta(textChunk)                                    — LLM 增量文本
 *   onDone({ reason, cached })                            — 结束
 *   onError(msg)
 *
 * 返回 () => void，调用可主动关闭连接。
 */
export function streamRecommendReason(userId, postId, channelScores, handlers = {}) {
  const params = new URLSearchParams()
  if (channelScores) {
    for (const key of ['cf', 'swing', 'graph', 'semantic', 'knowledge', 'hot']) {
      const val = channelScores[`${key}_score`]
      if (val !== undefined && val !== null) params.set(`${key}_score`, val)
    }
  }
  const qs = params.toString()
  const url = `/api/recommend/${userId}/reason/${postId}/stream${qs ? `?${qs}` : ''}`
  const es = new EventSource(url)

  es.addEventListener('meta', (e) => handlers.onMeta?.(JSON.parse(e.data)))
  es.addEventListener('delta', (e) => handlers.onDelta?.(JSON.parse(e.data).text))
  es.addEventListener('done', (e) => {
    handlers.onDone?.(JSON.parse(e.data))
    es.close()
  })
  es.addEventListener('error', (e) => {
    // EventSource 在流结束后也会触发 error，用 readyState 区分真实错误
    if (es.readyState === EventSource.CLOSED) return
    handlers.onError?.(e?.data ? JSON.parse(e.data).message : '连接中断')
    es.close()
  })

  return () => es.close()
}

/** 触发预计算 */
export function triggerPrecompute() {
  return request.post('/precompute')
}
