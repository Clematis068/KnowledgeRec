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

/** 获取推荐理由 */
export function getRecommendReason(userId, postId) {
  return request.get(`/recommend/${userId}/reason/${postId}`)
}

/** 触发预计算 */
export function triggerPrecompute() {
  return request.post('/precompute')
}
