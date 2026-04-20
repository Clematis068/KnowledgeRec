<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Connection, Lock, Right, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index'
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
        <div class="login-copy-main">
          <p class="copy-eyebrow">Member Access</p>
          <h1>欢迎回来</h1>
          <p class="copy-lead">登录后即可进入推荐流，继续浏览关注内容、热门趋势与作者关系。</p>

          <div class="copy-points">
            <div class="copy-point">
              <span class="point-index">01</span>
              <p>进入个性化推荐页，按推荐、关注、最新三种视图浏览内容。</p>
            </div>
            <div class="copy-point">
              <span class="point-index">02</span>
              <p>继续追踪感兴趣的作者与话题，查看社区热点与实时更新。</p>
            </div>
          </div>
        </div>

        <div class="copy-footer">
          <p class="copy-footer-text">首次使用的话，先创建账号并完成兴趣选择。</p>
          <div class="copy-actions">
            <router-link to="/">
              <el-button plain size="large">返回首页</el-button>
            </router-link>
            <router-link to="/register">
              <el-button text size="large">去注册</el-button>
            </router-link>
          </div>
        </div>
      </section>

      <aside class="login-form-wrap">
        <el-card class="login-card" shadow="never">
          <div class="brand-row">
            <div class="brand-mark">
              <el-icon :size="20"><Connection /></el-icon>
            </div>
            <div>
              <h2>知识推荐</h2>
              <p>输入账号信息登录社区。</p>
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
              <router-link to="/forgot-password">忘记密码？</router-link>
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
  padding: 32px;
}

.login-shell {
  max-width: var(--cds-layout-max-width);
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) 430px;
  gap: 32px;
  align-items: stretch;
}

.card-panel,
.login-card {
  border: none;
  border-radius: 0;
}

.login-copy {
  display: grid;
  grid-template-rows: 1fr auto;
  gap: 40px;
  position: relative;
  min-height: 540px;
  padding: 48px;
  background: var(--cds-background) !important;
  color: var(--cds-text-primary);
}

.login-copy::before {
  content: '';
  position: absolute;
  top: 24px;
  left: 24px;
  right: 24px;
  height: 4px;
  background: var(--cds-link-primary);
}

.login-copy-main {
  display: grid;
  align-content: start;
  gap: 24px;
}

.copy-eyebrow {
  color: var(--cds-text-muted);
  font-family: 'IBM Plex Mono', 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
  letter-spacing: 0.32px;
  text-transform: uppercase;
}

.login-copy h1,
.brand-row h2,
.welcome-panel h3 {
  letter-spacing: 0;
}

.login-copy h1 {
  max-width: 10ch;
  font-size: clamp(2.75rem, 6vw, 5rem);
  line-height: 1.08;
  color: var(--cds-text-primary);
}

.copy-lead,
.copy-footer-text {
  max-width: 34rem;
  color: var(--cds-text-secondary);
  font-size: 18px;
  line-height: 1.6;
}

.copy-points {
  display: grid;
  gap: 16px;
  max-width: 36rem;
}

.copy-point {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  padding-top: 16px;
  border-top: 1px solid var(--cds-border-subtle);
}

.point-index {
  color: var(--cds-text-muted);
  font-family: 'IBM Plex Mono', 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
  letter-spacing: 0.32px;
}

.copy-point p {
  color: var(--cds-text-secondary);
  line-height: 1.6;
}

.copy-footer {
  display: grid;
  gap: 16px;
}

.brand-row h2,
.welcome-panel h3 {
  color: var(--cds-text-primary);
}

.brand-row p {
  margin-top: 16px;
  color: var(--cds-text-secondary);
  line-height: 1.6;
}

.copy-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.login-copy :deep(.el-button--default),
.login-copy :deep(.el-button.is-plain) {
  color: var(--cds-text-primary);
  border-color: var(--cds-text-primary);
}

.login-copy :deep(.el-button--default:hover),
.login-copy :deep(.el-button.is-plain:hover) {
  color: var(--cds-text-primary);
  border-color: var(--cds-text-primary);
  background: var(--cds-layer-hover) !important;
}

.login-copy :deep(.el-button--text:not(.is-disabled)) {
  color: var(--cds-link-primary);
}

.login-copy :deep(.el-button--text:not(.is-disabled):hover) {
  color: var(--cds-link-primary-hover);
  background: var(--cds-blue-10) !important;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  color: #ffffff;
  background: var(--cds-link-primary);
}

.login-form-wrap {
  display: grid;
}

.login-card {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  position: relative;
  min-height: 540px;
  background: var(--cds-background) !important;
}

.login-card::before {
  content: '';
  position: absolute;
  top: 24px;
  left: 24px;
  right: 24px;
  height: 4px;
  background: var(--cds-background-inverse);
  z-index: 1;
}

.login-card :deep(.el-card__body) {
  display: grid;
  align-content: start;
  height: 100%;
  padding: 56px 48px 48px;
}

.submit-button {
  width: 100%;
  min-height: 54px;
}

.login-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  font-size: 14px;
  font-weight: 400;
  color: var(--cds-link-primary);
}

.welcome-panel {
  display: grid;
  gap: 18px;
}

.button-icon {
  margin-left: 6px;
}

@media (max-width: 960px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-copy {
    min-height: auto;
    padding: 32px 24px;
  }

  .login-copy::before {
    top: 16px;
    left: 16px;
    right: 16px;
  }

  .login-card {
    min-height: auto;
  }

  .login-card::before {
    top: 16px;
    left: 16px;
    right: 16px;
  }

  .login-card :deep(.el-card__body) {
    padding: 40px 24px 32px;
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
