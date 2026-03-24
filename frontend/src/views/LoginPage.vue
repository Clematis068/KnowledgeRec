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
        <h1>欢迎回来</h1>
        <p>登录后可以获取个性化推荐，关注你感兴趣的话题和作者。</p>

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
  padding: 24px;
}

.login-shell {
  max-width: 1240px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) 430px;
  gap: 24px;
  align-items: stretch;
}

.card-panel,
.login-card {
  border: 1px solid var(--kr-border);
  border-radius: 34px;
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay);
}

.login-copy {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 540px;
  padding: 34px;
  background: var(--kr-bg-soft);
}

.login-copy h1,
.brand-row h2,
.welcome-panel h3 {
  letter-spacing: -0.05em;
}

.login-copy h1 {
  max-width: 10ch;
  font-size: clamp(3rem, 6vw, 5.4rem);
  line-height: 0.9;
}

.login-copy p,
.brand-row p {
  margin-top: 16px;
  color: var(--kr-text-soft);
  line-height: 1.8;
}

.copy-actions {
  display: flex;
  gap: 12px;
  margin-top: 28px;
  flex-wrap: wrap;
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
  border-radius: 18px;
  color: #fff;
  background: var(--kr-primary);
  box-shadow: var(--kr-shadow-clay-soft);
}

.login-form-wrap {
  display: grid;
}

.login-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
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
  font-weight: 700;
  color: var(--kr-primary-strong);
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
