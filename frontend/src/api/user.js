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
