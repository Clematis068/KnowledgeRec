import request from './index'

/** 获取用户列表 */
export function getUserList(page = 1, perPage = 20) {
  return request.get('/user/list', { params: { page, per_page: perPage } })
}

/** 获取用户详情 */
export function getUserDetail(userId) {
  return request.get(`/user/${userId}`)
}

/** 获取用户行为记录 */
export function getUserBehaviors(userId, limit = 50) {
  return request.get(`/user/${userId}/behaviors`, { params: { limit } })
}

/** 获取用户发布的帖子 */
export function getUserPosts(userId, page = 1, perPage = 20) {
  return request.get(`/user/${userId}/posts`, { params: { page, per_page: perPage } })
}

/** 获取用户收藏的帖子 */
export function getUserFavorites(userId, page = 1, perPage = 20) {
  return request.get(`/user/${userId}/favorites`, { params: { page, per_page: perPage } })
}

/** 关注用户 */
export function followUser(userId) {
  return request.post(`/user/follow/${userId}`)
}

/** 取消关注 */
export function unfollowUser(userId) {
  return request.delete(`/user/follow/${userId}`)
}

/** 获取粉丝列表 */
export function getFollowers(userId) {
  return request.get(`/user/${userId}/followers`)
}

/** 获取关注列表 */
export function getFollowing(userId) {
  return request.get(`/user/${userId}/following`)
}

/** 获取关注状态 */
export function getFollowStatus(userId) {
  return request.get(`/user/${userId}/follow_status`)
}

/** 更新个人资料 */
export function updateProfile(data) {
  return request.put('/user/profile', data)
}
