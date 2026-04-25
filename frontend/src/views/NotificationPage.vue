<template>
  <div class="notification-page">
    <div class="page-header">
      <h2>消息中心</h2>
    </div>

    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-item', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span v-if="tab.badge > 0" class="badge">{{ tab.badge > 99 ? '99+' : tab.badge }}</span>
      </button>
      <button
        v-if="activeTab !== 'message'"
        class="mark-all-btn"
        @click="handleMarkAllRead"
      >
        全部已读
      </button>
    </div>

    <!-- 互动 / 系统 Tab -->
    <div v-if="activeTab !== 'message'" v-loading="loading" class="notification-list">
      <div
        v-for="item in notifications"
        :key="item.id"
        :class="['notification-item', { unread: !item.is_read }]"
        @click="handleNotificationClick(item)"
      >
        <div class="noti-avatar">
          <el-avatar :size="40" :icon="UserFilled" />
        </div>
        <div class="noti-body">
          <div class="noti-text">
            <span class="noti-sender">{{ item.sender_name || '系统' }}</span>
            <span class="noti-action">{{ actionText(item) }}</span>
          </div>
          <div class="noti-time">{{ formatTime(item.created_at) }}</div>
        </div>
        <div class="noti-actions">
          <button class="delete-btn" @click.stop="handleDeleteNotification(item)">删除</button>
          <span v-if="!item.is_read" class="unread-dot" />
        </div>
      </div>
      <el-empty v-if="!loading && notifications.length === 0" description="暂无通知" />
      <div v-if="hasMore" class="load-more">
        <el-button text :loading="loading" @click="loadMore">加载更多</el-button>
      </div>
    </div>

    <!-- 系统通知详情 -->
    <el-dialog v-model="systemNoticeVisible" title="系统通知详情" width="560px">
      <div v-if="systemNoticeText" class="system-notice-summary">
        {{ systemNoticeText }}
      </div>
      <div v-if="systemNoticeEntries.length" class="system-notice-entries">
        <div v-for="entry in systemNoticeEntries" :key="entry.label" class="system-notice-entry">
          <span class="system-entry-label">{{ entry.label }}</span>
          <span class="system-entry-value">{{ entry.value }}</span>
        </div>
      </div>
      <el-empty v-else-if="!systemNoticeText" description="暂无可展示内容" />
      <template #footer>
        <el-button type="primary" @click="systemNoticeVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 私信 Tab -->
    <div v-if="activeTab === 'message'" class="message-section">
      <!-- 会话列表 -->
      <div v-if="!chatTarget" v-loading="msgLoading" class="conversation-list">
        <!-- 新建对话 -->
        <div class="new-chat-bar">
          <el-autocomplete
            v-model="newChatQuery"
            :fetch-suggestions="searchUsers"
            placeholder="搜索用户发起私信..."
            value-key="username"
            clearable
            class="new-chat-input"
            @select="handleSelectUser"
          >
            <template #default="{ item }">
              <div class="user-suggestion">
                <el-avatar :size="28" :icon="UserFilled" />
                <span>{{ item.username }}</span>
              </div>
            </template>
          </el-autocomplete>
        </div>
        <div
          v-for="conv in conversations"
          :key="conv.user_id"
          class="conversation-item"
          @click="openChat(conv)"
        >
          <el-avatar :size="44" :icon="UserFilled" />
          <div class="conv-body">
            <div class="conv-header">
              <span class="conv-name">{{ conv.username }}</span>
              <span class="conv-time">{{ formatTime(conv.last_time) }}</span>
            </div>
            <div class="conv-preview">{{ conv.last_message }}</div>
          </div>
          <span v-if="conv.unread_count > 0" class="badge conv-badge">
            {{ conv.unread_count > 99 ? '99+' : conv.unread_count }}
          </span>
        </div>
        <el-empty v-if="!msgLoading && conversations.length === 0" description="暂无私信，搜索用户名发起对话" />
      </div>

      <!-- 聊天详情 -->
      <div v-else class="chat-detail">
        <div class="chat-header">
          <button class="back-btn" @click="closeChat">
            <el-icon><ArrowLeft /></el-icon>
          </button>
          <span class="chat-title">{{ chatTarget.username }}</span>
        </div>
        <div ref="chatBoxRef" class="chat-messages" v-loading="chatLoading">
          <div v-if="chatHasMore" class="load-more">
            <el-button text size="small" @click="loadMoreMessages">加载更早消息</el-button>
          </div>
          <div
            v-for="msg in chatMessages"
            :key="msg.id"
            :class="['chat-bubble-row', msg.sender_id === authStore.userId ? 'mine' : 'theirs']"
          >
            <div class="chat-bubble">
              <!-- 文本消息 -->
              <div v-if="!msg.msg_type || msg.msg_type === 'text'" class="bubble-content">{{ msg.content }}</div>
              <!-- 图片消息 -->
              <div v-else-if="msg.msg_type === 'image'" class="bubble-image" @click="previewImage(msg.image_url)">
                <img :src="msg.image_url" alt="图片" />
              </div>
              <!-- 帖子链接消息 -->
              <div
                v-else-if="msg.msg_type === 'post_link' && msg.linked_post"
                class="bubble-post-link"
                @click="router.push(`/posts/${msg.linked_post.id}`)"
              >
                <div class="post-link-title">{{ msg.linked_post.title }}</div>
                <div v-if="msg.linked_post.summary" class="post-link-summary">{{ msg.linked_post.summary }}</div>
              </div>
              <div class="bubble-time">{{ formatTime(msg.created_at) }}</div>
            </div>
          </div>
        </div>
        <div class="chat-input-bar">
          <div class="chat-actions">
            <button class="action-btn" @click="triggerImageUpload" title="发送图片">
              <el-icon><Picture /></el-icon>
            </button>
            <button class="action-btn" @click="showSharePostDialog = true" title="分享帖子">
              <el-icon><Share /></el-icon>
            </button>
          </div>
          <el-input
            v-model="chatInput"
            placeholder="输入消息..."
            @keyup.enter="handleSend"
            :disabled="sending"
          />
          <el-button type="primary" :loading="sending" @click="handleSend">发送</el-button>
        </div>
        <input
          ref="imageInputRef"
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          style="display: none"
          @change="handleImageSelected"
        />
      </div>
    </div>

    <!-- 图片预览 -->
    <teleport to="body">
      <div v-if="previewImageUrl" class="image-preview-overlay" @click="previewImageUrl = null">
        <img :src="previewImageUrl" class="image-preview-img" />
      </div>
    </teleport>

    <!-- 分享帖子对话框 -->
    <el-dialog v-model="showSharePostDialog" title="分享帖子" width="400px">
      <el-autocomplete
        v-model="sharePostQuery"
        :fetch-suggestions="searchSharePosts"
        placeholder="搜索帖子标题..."
        value-key="title"
        clearable
        style="width: 100%"
        @select="handleSharePostSelect"
      >
        <template #default="{ item }">
          <div style="display: flex; flex-direction: column; gap: 2px; padding: 4px 0">
            <span style="font-weight: 600; font-size: 13px">{{ item.title }}</span>
            <span style="font-size: 11px; color: #999">{{ item.author_name || '匿名' }} · {{ item.like_count || 0 }} 赞</span>
          </div>
        </template>
      </el-autocomplete>
      <template #footer>
        <el-button @click="showSharePostDialog = false">取消</el-button>
        <el-button type="primary" :loading="sending" :disabled="!sharePostId" @click="handleSharePost">分享</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, UserFilled, Picture, Share } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getNotifications,
  markRead,
  deleteNotification,
  markAllRead,
  getConversations,
  getMessageDetail,
  sendMessage,
  uploadImage,
} from '../api/notification'
import { searchPosts } from '../api/post'
import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notification'
import { onSocketEvent, offSocketEvent } from '../utils/socket'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

const activeTab = ref('interaction')
const loading = ref(false)
const notifications = ref([])
const page = ref(1)
const total = ref(0)
const hasMore = computed(() => notifications.value.length < total.value)

// 私信状态
const msgLoading = ref(false)
const conversations = ref([])
const chatTarget = ref(null)
const chatMessages = ref([])
const chatLoading = ref(false)
const chatInput = ref('')
const sending = ref(false)
const chatPage = ref(1)
const chatTotal = ref(0)
const chatHasMore = computed(() => chatMessages.value.length < chatTotal.value)
const chatBoxRef = ref(null)

// 图片上传
const imageInputRef = ref(null)
const previewImageUrl = ref(null)

// 帖子分享
const showSharePostDialog = ref(false)
const sharePostId = ref('')
const sharePostQuery = ref('')
const systemNoticeVisible = ref(false)
const systemNoticePayload = ref(null)

// 新建对话搜索
const newChatQuery = ref('')

const tabs = computed(() => [
  { key: 'interaction', label: '互动', badge: notificationStore.interactionCount },
  { key: 'system', label: '系统', badge: notificationStore.systemCount },
  { key: 'message', label: '私信', badge: notificationStore.messageCount },
])

function actionText(item) {
  const map = {
    follow: '关注了你',
    like: '赞了你的帖子',
    favorite: '收藏了你的帖子',
    comment: '评论了你的帖子',
  }
  if (item.type === 'system') {
    const payload = parseSystemContent(item.content)
    const fallback = typeof item.content === 'string' && !item.content.trim().startsWith('{')
      ? item.content
      : '系统通知'
    return systemNotificationSummary(payload, fallback)
  }
  return map[item.type] || '向你发来了通知'
}

function parseSystemContent(content) {
  if (!content || typeof content !== 'string') {
    return null
  }
  try {
    const parsed = JSON.parse(content)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

function isDisplayableValue(value) {
  if (value === true || value === '是' || value === 1) return true
  if (typeof value === 'number') return value !== 0
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.some((item) => isDisplayableValue(item))
  if (value && typeof value === 'object') return Object.keys(value).length > 0
  return false
}

function formatDisplayValue(value) {
  if (value === true || value === '是' || value === 1) return '是'
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number') return String(value)
  if (Array.isArray(value)) return value.map((item) => formatDisplayValue(item)).filter(Boolean).join('、')
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2)
  return ''
}

function pushDisplayEntry(entries, label, value) {
  if (!isDisplayableValue(value)) return
  entries.push({ label, value: formatDisplayValue(value) })
}

function systemNotificationSummary(payload, fallback = '系统通知') {
  if (!payload) {
    return fallback || '系统通知'
  }
  if (payload.type === 'post_audit_notice') {
    const title = payload.post_title || '未知帖子'
    return `帖子《${title}》未通过审核`
  }
  return payload.reason || fallback || '系统通知'
}

function buildSystemNoticeEntries(payload) {
  if (!payload || typeof payload !== 'object') {
    return []
  }

  const entries = []
  pushDisplayEntry(entries, '来源', payload.source)
  pushDisplayEntry(entries, '帖子ID', payload.post_id)
  pushDisplayEntry(entries, '帖子标题', payload.post_title)
  pushDisplayEntry(entries, '审核结果', payload.passed ? '是' : '')
  pushDisplayEntry(entries, '拒绝原因', payload.reason)
  pushDisplayEntry(entries, '审核标签', payload.audit_labels)

  if (payload.audit_details && typeof payload.audit_details === 'object' && !Array.isArray(payload.audit_details)) {
    Object.entries(payload.audit_details).forEach(([key, value]) => {
      pushDisplayEntry(entries, `审核详情.${key}`, value)
    })
  } else {
    pushDisplayEntry(entries, '审核详情', payload.audit_details)
  }

  return entries
}

const systemNoticeSummary = computed(() => {
  const payload = systemNoticePayload.value
  if (!payload) return ''
  if (typeof payload === 'string') return payload
  if (payload.type === 'post_audit_notice') {
    return payload.reason || systemNotificationSummary(payload, '系统通知')
  }
  return systemNotificationSummary(payload, '系统通知')
})

const systemNoticeEntries = computed(() => buildSystemNoticeEntries(systemNoticePayload.value))
const systemNoticeText = computed(() => {
  const value = systemNoticeSummary.value
  return typeof value === 'string' ? value.trim() : ''
})

function formatTime(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return d.toLocaleDateString('zh-CN')
}

async function fetchNotifications(reset = false) {
  if (reset) {
    page.value = 1
    notifications.value = []
  }
  loading.value = true
  try {
    const filterType = activeTab.value === 'system' ? 'system' : 'interaction'
    const data = await getNotifications(page.value, 20, filterType)
    notifications.value = reset ? data.notifications : [...notifications.value, ...data.notifications]
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function loadMore() {
  page.value++
  fetchNotifications()
}

async function handleNotificationClick(item) {
  if (!item.is_read) {
    await markRead(item.id)
    item.is_read = true
    notificationStore.fetchUnreadCount()
  }
  if (item.type === 'system') {
    systemNoticePayload.value = parseSystemContent(item.content) || item.content || null
    systemNoticeVisible.value = true
    return
  }
  if (item.post_id) {
    router.push(`/posts/${item.post_id}`)
  } else if (item.sender_id && item.type === 'follow') {
    router.push(`/users/${item.sender_id}`)
  }
}

async function handleDeleteNotification(item) {
  try {
    await ElMessageBox.confirm('确定删除这条通知吗？', '删除通知', { type: 'warning' })
    await deleteNotification(item.id)
    notifications.value = notifications.value.filter((n) => n.id !== item.id)
    total.value = Math.max(0, total.value - 1)
    notificationStore.fetchUnreadCount()
    ElMessage.success('通知已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      // 错误已由拦截器处理
    }
  }
}

async function handleMarkAllRead() {
  const filterType = activeTab.value === 'system' ? 'system' : 'interaction'
  await markAllRead(filterType)
  notifications.value.forEach((n) => (n.is_read = true))
  notificationStore.fetchUnreadCount()
}

async function searchUsers(queryString, callback) {
  if (!queryString?.trim()) {
    callback([])
    return
  }
  try {
    const data = await searchPosts(queryString.trim(), 1, 10, 'author')
    callback((data.users || []).filter((u) => u.id !== authStore.userId))
  } catch {
    callback([])
  }
}

function handleSelectUser(user) {
  newChatQuery.value = ''
  openChat({ user_id: user.id, username: user.username })
}

async function fetchConversations() {
  msgLoading.value = true
  try {
    const data = await getConversations()
    conversations.value = data.conversations
  } finally {
    msgLoading.value = false
  }
}

async function openChat(conv) {
  chatTarget.value = { user_id: conv.user_id, username: conv.username }
  chatPage.value = 1
  chatMessages.value = []
  chatLoading.value = true
  try {
    const data = await getMessageDetail(conv.user_id, 1, 30)
    chatMessages.value = data.messages
    chatTotal.value = data.total
    // 用接口返回的用户名补全（从 URL query 进来时可能没有）
    if (data.target_user?.username) {
      chatTarget.value.username = data.target_user.username
    }
    notificationStore.fetchUnreadCount()
    await nextTick()
    scrollToBottom()
  } finally {
    chatLoading.value = false
  }
}

function closeChat() {
  chatTarget.value = null
  // 清除 URL 的 chat query，但保持在私信 Tab
  if (route.query.chat) {
    router.replace({ path: '/notifications', query: { tab: 'message' } })
  }
  fetchConversations()
}

async function loadMoreMessages() {
  chatPage.value++
  chatLoading.value = true
  try {
    const data = await getMessageDetail(chatTarget.value.user_id, chatPage.value, 30)
    chatMessages.value = [...data.messages, ...chatMessages.value]
    chatTotal.value = data.total
  } finally {
    chatLoading.value = false
  }
}

async function handleSend() {
  const content = chatInput.value.trim()
  if (!content || sending.value) return
  sending.value = true
  try {
    const msg = await sendMessage(chatTarget.value.user_id, { content })
    chatMessages.value.push(msg)
    chatInput.value = ''
    await nextTick()
    scrollToBottom()
  } finally {
    sending.value = false
  }
}

function triggerImageUpload() {
  imageInputRef.value?.click()
}

async function handleImageSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''

  sending.value = true
  try {
    const uploadRes = await uploadImage(file)
    const msg = await sendMessage(chatTarget.value.user_id, {
      msgType: 'image',
      imageUrl: uploadRes.url,
    })
    chatMessages.value.push(msg)
    await nextTick()
    scrollToBottom()
  } catch {
    ElMessage.error('图片发送失败')
  } finally {
    sending.value = false
  }
}

async function handleSharePost() {
  const postId = parseInt(sharePostId.value)
  if (!postId) {
    ElMessage.warning('请先选择要分享的帖子')
    return
  }
  sending.value = true
  try {
    const msg = await sendMessage(chatTarget.value.user_id, {
      msgType: 'post_link',
      linkedPostId: postId,
    })
    chatMessages.value.push(msg)
    showSharePostDialog.value = false
    sharePostId.value = ''
    await nextTick()
    scrollToBottom()
  } catch {
    // API 层已处理错误提示
  } finally {
    sending.value = false
  }
}

function previewImage(url) {
  previewImageUrl.value = url
}

async function searchSharePosts(queryString, callback) {
  if (!queryString?.trim()) {
    callback([])
    return
  }
  try {
    const data = await searchPosts(queryString.trim(), 1, 8, 'post')
    callback(data.posts || [])
  } catch {
    callback([])
  }
}

function handleSharePostSelect(item) {
  sharePostId.value = String(item.id)
  sharePostQuery.value = item.title
}

function scrollToBottom() {
  if (chatBoxRef.value) {
    chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight
  }
}

// WebSocket 实时消息处理
function onNewMessage(data) {
  // 如果当前正在和发送者聊天，直接追加消息
  if (chatTarget.value && data.sender_id === chatTarget.value.user_id) {
    const exists = chatMessages.value.some((m) => m.id === data.id)
    if (!exists) {
      chatMessages.value.push(data)
      nextTick(() => scrollToBottom())
    }
  }
}

function onNewNotification(data) {
  // 通知列表页实时插入
  if (activeTab.value !== 'message') {
    const matchesTab =
      (activeTab.value === 'system' && data.type === 'system') ||
      (activeTab.value === 'interaction' && ['follow', 'like', 'favorite', 'comment'].includes(data.type))
    if (matchesTab) {
      notifications.value.unshift(data)
      total.value++
    }
  }
}

watch(activeTab, (val) => {
  if (val === 'message') {
    // 如果已有 chatTarget（从 URL query 进来），不要清除
    if (!chatTarget.value) {
      fetchConversations()
    }
  } else {
    chatTarget.value = null
    fetchNotifications(true)
  }
})

onMounted(() => {
  onSocketEvent('new_message', onNewMessage)
  onSocketEvent('new_notification', onNewNotification)

  // 支持从 ?chat=userId 直接打开聊天
  const chatUserId = Number(route.query.chat)
  if (chatUserId) {
    activeTab.value = 'message'
    openChat({
      user_id: chatUserId,
      username: route.query.username || '',
    })
  } else if (route.query.tab === 'message') {
    activeTab.value = 'message'
    fetchConversations()
  } else {
    fetchNotifications(true)
  }
})

onBeforeUnmount(() => {
  offSocketEvent('new_message', onNewMessage)
  offSocketEvent('new_notification', onNewNotification)
})
</script>

<style scoped>
.notification-page {
  max-width: 720px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.page-header h2 {
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  font-weight: 800;
  letter-spacing: -0.03em;
}

.tab-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--kr-border);
  padding-bottom: 0;
}

.tab-item {
  position: relative;
  padding: 10px 20px;
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 600;
  color: var(--kr-text-soft);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.tab-item.active {
  color: var(--kr-text);
  border-bottom-color: var(--kr-accent);
}

.mark-all-btn {
  margin-left: auto;
  padding: 6px 14px;
  border: 1px solid var(--kr-border);
  border-radius: 999px;
  background: none;
  font-size: 12px;
  color: var(--kr-text-soft);
  cursor: pointer;
  margin-bottom: 4px;
}

.mark-all-btn:hover {
  color: var(--kr-accent);
  border-color: var(--kr-accent);
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--kr-danger, #f56c6c);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  margin-left: 4px;
}

/* 通知列表 */
.notification-list {
  display: grid;
  gap: 2px;
}

.notification-item {
  display: grid;
  grid-template-columns: 40px 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.notification-item:hover {
  background: var(--kr-surface-alt);
}

.notification-item.unread {
  background: var(--kr-primary-soft, #f0f7ff);
}

.noti-body {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.noti-text {
  font-size: 14px;
  line-height: 1.5;
}

.noti-sender {
  font-weight: 700;
  margin-right: 6px;
}

.noti-action {
  color: var(--kr-text-soft);
}

.noti-time {
  font-size: 12px;
  color: var(--kr-text-muted);
}

.noti-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.delete-btn {
  border: none;
  background: transparent;
  color: var(--kr-text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.delete-btn:hover {
  color: var(--kr-danger, #f56c6c);
}

.unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--kr-accent, #1890ff);
}

.load-more {
  text-align: center;
  padding: 12px 0;
}

.system-notice-summary {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.6;
  margin-bottom: 14px;
  color: var(--kr-text);
}

.system-notice-entries {
  display: grid;
  gap: 10px;
}

.system-notice-entry {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--kr-border);
  border-radius: 10px;
  background: var(--kr-surface-alt);
}

.system-entry-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--kr-text-soft);
}

.system-entry-value {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--kr-text);
}

/* 新建对话搜索 */
.new-chat-bar {
  padding: 12px 16px;
  border-bottom: 1px solid var(--kr-border);
}

.new-chat-input {
  width: 100%;
}

.user-suggestion {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}

/* 会话列表 */
.conversation-list {
  display: grid;
  gap: 2px;
}

.conversation-item {
  display: grid;
  grid-template-columns: 44px 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.conversation-item:hover {
  background: var(--kr-surface-alt);
}

.conv-body {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conv-name {
  font-weight: 700;
  font-size: 14px;
}

.conv-time {
  font-size: 12px;
  color: var(--kr-text-muted);
}

.conv-preview {
  font-size: 13px;
  color: var(--kr-text-soft);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-badge {
  margin-left: 0;
}

/* 聊天详情 */
.chat-detail {
  display: grid;
  grid-template-rows: auto 1fr auto;
  height: calc(100vh - 220px);
  min-height: 400px;
  border: 1px solid var(--kr-border);
  border-radius: 12px;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--kr-border);
  background: var(--kr-surface);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--kr-border);
  border-radius: 8px;
  background: none;
  cursor: pointer;
  color: var(--kr-text);
}

.chat-title {
  font-weight: 700;
  font-size: 15px;
}

.chat-messages {
  overflow-y: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-bubble-row {
  display: flex;
}

.chat-bubble-row.mine {
  justify-content: flex-end;
}

.chat-bubble-row.theirs {
  justify-content: flex-start;
}

.chat-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
}

.chat-bubble-row.mine .chat-bubble {
  background: var(--kr-accent, #1890ff);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-bubble-row.theirs .chat-bubble {
  background: var(--kr-surface-alt, #f5f5f5);
  color: var(--kr-text);
  border-bottom-left-radius: 4px;
}

.bubble-content {
  word-break: break-word;
}

.bubble-time {
  font-size: 11px;
  margin-top: 4px;
  opacity: 0.7;
}

/* 图片消息 */
.bubble-image {
  cursor: pointer;
}

.bubble-image img {
  max-width: 240px;
  max-height: 200px;
  border-radius: 8px;
  display: block;
  object-fit: cover;
}

/* 帖子链接消息 */
.bubble-post-link {
  cursor: pointer;
  padding: 10px 12px;
  border: 1px solid rgba(128, 128, 128, 0.2);
  border-radius: 8px;
  background: rgba(128, 128, 128, 0.06);
  transition: background 0.15s;
}

.bubble-post-link:hover {
  background: rgba(128, 128, 128, 0.12);
}

.post-link-title {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 4px;
  line-height: 1.4;
}

.post-link-summary {
  font-size: 12px;
  opacity: 0.8;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 输入栏 */
.chat-input-bar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  padding: 12px 18px;
  border-top: 1px solid var(--kr-border);
  background: var(--kr-surface);
  align-items: center;
}

.chat-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--kr-border);
  border-radius: 8px;
  background: none;
  cursor: pointer;
  color: var(--kr-text-soft);
  transition: color 0.15s, border-color 0.15s;
}

.action-btn:hover {
  color: var(--kr-accent);
  border-color: var(--kr-accent);
}

/* 图片预览 */
.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}

.image-preview-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
}
</style>
