import request from './index'

/** 获取通知列表 */
export function getNotifications(page = 1, perPage = 20, type = '') {
  return request.get('/notification/list', { params: { page, per_page: perPage, type } })
}

/** 获取未读数 */
export function getUnreadCount() {
  return request.get('/notification/unread-count')
}

/** 标记单条已读 */
export function markRead(notificationId) {
  return request.put(`/notification/read/${notificationId}`)
}

/** 删除单条通知 */
export function deleteNotification(notificationId) {
  return request.delete(`/notification/${notificationId}`)
}

/** 全部已读 */
export function markAllRead(type = '') {
  return request.put('/notification/read-all', null, { params: { type } })
}

/** 获取私信会话列表 */
export function getConversations() {
  return request.get('/notification/messages')
}

/** 获取与某用户的对话详情 */
export function getMessageDetail(userId, page = 1, perPage = 30) {
  return request.get(`/notification/messages/${userId}`, { params: { page, per_page: perPage } })
}

/** 发送私信 */
export function sendMessage(userId, { content = '', msgType = 'text', imageUrl = '', linkedPostId = null } = {}) {
  return request.post(`/notification/messages/${userId}`, {
    content,
    msg_type: msgType,
    image_url: imageUrl || undefined,
    linked_post_id: linkedPostId || undefined,
  })
}

/** 上传图片 */
export function uploadImage(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/upload/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
