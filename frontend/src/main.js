import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  ArrowDown,
  ChatDotRound,
  CircleClose,
  Connection,
  Document,
  EditPen,
  Files,
  Loading,
  Star,
  SwitchButton,
  TrendCharts,
  User,
  View,
} from '@element-plus/icons-vue'
import { ElLoading } from 'element-plus/es/components/loading/index'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/notification/style/css'
import 'element-plus/es/components/overlay/style/css'
import router from './router'
import App from './App.vue'
import './style.css'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

const globalIcons = {
  ArrowDown,
  ChatDotRound,
  CircleClose,
  Connection,
  Document,
  EditPen,
  Files,
  Loading,
  Star,
  SwitchButton,
  TrendCharts,
  User,
  View,
}

for (const [name, component] of Object.entries(globalIcons)) {
  app.component(name, component)
}

app.use(ElLoading)
app.use(pinia)
app.use(router)

const authStore = useAuthStore()
authStore.init().finally(() => {
  app.mount('#app')
})
