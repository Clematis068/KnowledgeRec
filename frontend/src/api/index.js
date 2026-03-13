import axios from 'axios'
import { ElMessage } from 'element-plus/es/components/message/index'
import router from '../router'
import { getClientContextHeaders } from '../utils/clientContext'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器：自动附加 JWT
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  config.headers = {
    ...(config.headers || {}),
    ...getClientContextHeaders(),
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：提取 data，401 自动登出
request.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
      ElMessage.warning('登录已过期，请重新登录')
      return Promise.reject(err)
    }
    const msg = err.response?.data?.error || err.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

export default request
