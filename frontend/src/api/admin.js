import request from './index'

export function getAdminStats() {
  return request.get('/admin/stats')
}

export function getAdminUsers(params) {
  return request.get('/admin/users', { params })
}

export function banUser(userId) {
  return request.post(`/admin/users/${userId}/ban`)
}

export function unbanUser(userId) {
  return request.post(`/admin/users/${userId}/unban`)
}

export function getAdminPosts(params) {
  return request.get('/admin/posts', { params })
}

export function approvePost(postId) {
  return request.post(`/admin/posts/${postId}/approve`)
}

export function rejectPost(postId, reason) {
  return request.post(`/admin/posts/${postId}/reject`, { reason })
}

export function removePost(postId) {
  return request.post(`/admin/posts/${postId}/remove`)
}
