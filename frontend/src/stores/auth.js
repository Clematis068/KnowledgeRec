import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, getMe } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const userId = computed(() => user.value?.id)
  const username = computed(() => user.value?.username)

  async function login(username, password) {
    const data = await apiLogin(username, password)
    token.value = data.token
    user.value = data.user
    localStorage.setItem('token', data.token)
  }

  async function register(form) {
    const data = await apiRegister(form)
    token.value = data.token
    user.value = data.user
    localStorage.setItem('token', data.token)
  }

  async function fetchUser() {
    const data = await getMe()
    user.value = data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  async function init() {
    if (!token.value) return
    try {
      await fetchUser()
    } catch {
      // 401 时 axios 拦截器已清除 token 并跳转登录页
      // 其他错误（网络波动、页面刷新等）保留 token 不清空登录态
      if (!localStorage.getItem('token')) {
        // token 已被拦截器移除，说明是 401，彻底清空
        user.value = null
        token.value = ''
      }
    }
  }

  return { token, user, isLoggedIn, userId, username, login, register, fetchUser, logout, init }
})
