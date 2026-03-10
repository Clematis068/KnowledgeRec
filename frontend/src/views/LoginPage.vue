<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Connection, Lock, Right, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const dashboardRoute = computed(() => route.query.redirect || '/recommend')

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push(dashboardRoute.value)
  } catch {
    // 错误已被 axios 拦截器处理
  } finally {
    loading.value = false
  }
}

function goToDashboard() {
  router.push(dashboardRoute.value)
}
</script>

<template>
  <div class="login-page">
    <div class="login-shell">
      <section class="login-copy card-panel">
        <span class="page-kicker">Login</span>
        <h1>登录后进入你的推荐页。</h1>
        <p>未登录时先到这里，已登录时可直接返回推荐页。</p>

        <div class="copy-actions">
          <router-link to="/">
            <el-button plain size="large">返回首页</el-button>
          </router-link>
          <router-link to="/register">
            <el-button text size="large">去注册</el-button>
          </router-link>
        </div>
      </section>

      <aside class="login-form-wrap">
        <el-card class="login-card" shadow="never">
          <div class="brand-row">
            <div class="brand-mark">
              <el-icon :size="20"><Connection /></el-icon>
            </div>
            <div>
              <h2>KnowledgeRec</h2>
              <p>登录 / 注册分开处理。</p>
            </div>
          </div>

          <template v-if="!authStore.isLoggedIn">
            <el-form ref="formRef" :model="form" :rules="rules" label-width="0" size="large">
              <el-form-item prop="username">
                <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="form.password"
                  type="password"
                  placeholder="密码"
                  show-password
                  :prefix-icon="Lock"
                  @keyup.enter="handleLogin"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="loading" class="submit-button" @click="handleLogin">
                  登录并进入推荐页
                </el-button>
              </el-form-item>
            </el-form>

            <div class="login-links">
              <router-link to="/register">没有账号？去注册</router-link>
              <router-link to="/">回首页</router-link>
            </div>
          </template>

          <template v-else>
            <div class="welcome-panel">
              <el-tag type="success" effect="dark" round>已登录</el-tag>
              <h3>{{ authStore.username }}，欢迎回来</h3>
              <el-button type="primary" class="submit-button" @click="goToDashboard">
                进入推荐页
                <el-icon class="button-icon"><Right /></el-icon>
              </el-button>
              <div class="login-links">
                <router-link to="/my-posts">我的发帖</router-link>
                <router-link to="/">回首页</router-link>
              </div>
            </div>
          </template>
        </el-card>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  padding: 24px;
}

.login-shell {
  max-width: 1180px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 20px;
  align-items: center;
}

.card-panel,
.login-card {
  border: 1px solid rgba(124, 58, 237, 0.12);
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.76);
  box-shadow: 0 18px 44px rgba(76, 29, 149, 0.08);
  backdrop-filter: blur(18px);
}

.login-copy {
  padding: 34px;
}

.page-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-primary);
}

.login-copy h1,
.brand-row h2,
.welcome-panel h3 {
  letter-spacing: -0.04em;
}

.login-copy h1 {
  max-width: 12ch;
  font-size: clamp(2.6rem, 5vw, 4.6rem);
  line-height: 0.95;
}

.login-copy p,
.brand-row p {
  margin-top: 14px;
  color: var(--kr-text-soft);
  line-height: 1.75;
}

.copy-actions {
  display: flex;
  gap: 12px;
  margin-top: 22px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 22px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  color: #fff;
  background: linear-gradient(135deg, var(--kr-primary), #9f67ff);
}

.submit-button {
  width: 100%;
  min-height: 50px;
}

.login-links {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--kr-primary-strong);
}

.welcome-panel {
  display: grid;
  gap: 16px;
}

.button-icon {
  margin-left: 6px;
}

@media (max-width: 960px) {
  .login-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .login-page {
    padding: 16px;
  }

  .copy-actions,
  .login-links {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
