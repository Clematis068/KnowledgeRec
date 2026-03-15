import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getUnreadCount } from '../api/notification'
import { connectSocket, disconnectSocket, onSocketEvent, offSocketEvent } from '../utils/socket'

export const useNotificationStore = defineStore('notification', () => {
  const systemCount = ref(0)
  const interactionCount = ref(0)
  const messageCount = ref(0)

  const totalCount = computed(() => systemCount.value + interactionCount.value + messageCount.value)

  let listening = false

  async function fetchUnreadCount() {
    try {
      const data = await getUnreadCount()
      systemCount.value = data.system || 0
      interactionCount.value = data.interaction || 0
      messageCount.value = data.message || 0
    } catch {
      // 静默失败
    }
  }

  function _onNewNotification(data) {
    const type = data?.type
    if (type === 'system') {
      systemCount.value++
    } else if (['follow', 'like', 'favorite', 'comment'].includes(type)) {
      interactionCount.value++
    }
  }

  function _onNewMessage() {
    messageCount.value++
  }

  function startListening(token) {
    if (listening) return
    listening = true

    fetchUnreadCount()
    connectSocket(token)
    onSocketEvent('new_notification', _onNewNotification)
    onSocketEvent('new_message', _onNewMessage)
  }

  function stopListening() {
    if (!listening) return
    listening = false

    offSocketEvent('new_notification', _onNewNotification)
    offSocketEvent('new_message', _onNewMessage)
    disconnectSocket()
  }

  return {
    systemCount,
    interactionCount,
    messageCount,
    totalCount,
    fetchUnreadCount,
    startListening,
    stopListening,
  }
})
