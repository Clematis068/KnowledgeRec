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

/** 更新帖子 */
export function updatePost(postId, { title, content, domain_id, tag_ids, tags }) {
  return request.put(`/post/${postId}`, { title, content, domain_id, tag_ids, tags })
}

/** 删除帖子 */
export function deletePost(postId) {
  return request.delete(`/post/${postId}`)
}

/** 获取热门帖子 */
export function getHotPosts(limit = 20) {
  return request.get('/post/hot', { params: { limit } })
}

/** 获取关注用户的帖子流 */
export function getFollowingPosts(page = 1, perPage = 20) {
  return request.get('/post/following', { params: { page, per_page: perPage } })
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

/** 获取帖子评论列表 */
export function getComments(postId, page = 1, perPage = 20) {
  return request.get(`/post/${postId}/comments`, { params: { page, per_page: perPage } })
}

/** 发表评论 */
export function postComment(postId, commentText, parentId = null) {
  const data = { behavior_type: 'comment', comment_text: commentText }
  if (parentId) data.parent_id = parentId
  return request.post(`/post/${postId}/behavior`, data)
}

/** 删除评论 */
export function deleteComment(postId, commentId) {
  return request.delete(`/post/${postId}/comments/${commentId}`)
}

/** 取消收藏 */
export function unfavoritePost(postId) {
  return request.delete(`/post/${postId}/favorite`)
}

/** 取消不感兴趣 */
export function undislikePost(postId) {
  return request.delete(`/post/${postId}/dislike`)
}

/** 屏蔽作者 */
export function blockPostAuthor(postId) {
  return request.post(`/post/${postId}/block-author`)
}

/** 取消屏蔽作者 */
export function unblockPostAuthor(postId) {
  return request.delete(`/post/${postId}/block-author`)
}

/** 屏蔽领域 */
export function blockPostDomain(postId) {
  return request.post(`/post/${postId}/block-domain`)
}

/** 取消屏蔽领域 */
export function unblockPostDomain(postId) {
  return request.delete(`/post/${postId}/block-domain`)
}

/** 创建帖子 */
export function createPost({ title, content, domain_id, tag_ids, tags }) {
  return request.post('/post/create', { title, content, domain_id, tag_ids, tags })
}

/** 搜索帖子或用户 */
export function searchPosts(q, page = 1, perPage = 20, type = 'post') {
  return request.get('/search', { params: { q, page, per_page: perPage, type } })
}
