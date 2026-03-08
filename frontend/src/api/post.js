import request from './index'

/** 获取帖子列表 */
export function getPostList(page = 1, perPage = 20, domainId = null) {
  const params = { page, per_page: perPage }
  if (domainId) params.domain_id = domainId
  return request.get('/post/list', { params })
}

/** 获取帖子详情 */
export function getPostDetail(postId) {
  return request.get(`/post/${postId}`)
}

/** 获取热门帖子 */
export function getHotPosts(limit = 20) {
  return request.get('/post/hot', { params: { limit } })
}

/** 记录用户行为 (browse/like/favorite/comment) */
export function recordBehavior(postId, behaviorType, extra = {}) {
  return request.post(`/post/${postId}/behavior`, { behavior_type: behaviorType, ...extra })
}

/** 取消点赞 */
export function unlikePost(postId) {
  return request.delete(`/post/${postId}/like`)
}

/** 获取当前用户对帖子的交互状态 */
export function getPostUserStatus(postId) {
  return request.get(`/post/${postId}/user_status`)
}
