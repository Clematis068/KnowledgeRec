<script setup>
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'

import RegisterEmailStep from '../components/auth/RegisterEmailStep.vue'
import RegisterInterestStep from '../components/auth/RegisterInterestStep.vue'
import { getTags, sendEmailCode, verifyEmailCode } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const MIN_INTEREST_SELECTION = 3

const router = useRouter()
const authStore = useAuthStore()

const accountFormRef = ref()
const currentStep = ref(0)
const loading = ref(false)
const tagsLoading = ref(false)
const tagGroups = ref([])
const tagError = ref(false)
const sendingCode = ref(false)
const verifyingCode = ref(false)
const emailVerified = ref(false)
const emailCode = ref('')
const countdown = ref(0)
const devCode = ref('')

let countdownTimer = null

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  gender: 'male',
  email: '',
  tag_ids: [],
})

const validateConfirm = (_rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度 2-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
}

watch(
  () => form.email,
  () => {
    emailVerified.value = false
    emailCode.value = ''
    devCode.value = ''
  },
)

function startCountdown(seconds = 60) {
  countdown.value = seconds
  clearCountdown()
  countdownTimer = window.setInterval(() => {
    if (countdown.value <= 1) {
      clearCountdown()
      countdown.value = 0
      return
    }
    countdown.value -= 1
  }, 1000)
}

function clearCountdown() {
  if (countdownTimer) {
    window.clearInterval(countdownTimer)
    countdownTimer = null
  }
}

async function ensureTagsLoaded() {
  if (tagGroups.value.length || tagsLoading.value) return
  tagsLoading.value = true
  try {
    const data = await getTags()
    tagGroups.value = data.groups || []
  } finally {
    tagsLoading.value = false
  }
}

async function goToEmailStep() {
  const valid = await accountFormRef.value.validate().catch(() => false)
  if (!valid) return
  currentStep.value = 1
}

async function handleSendCode() {
  sendingCode.value = true
  try {
    const data = await sendEmailCode(form.email)
    devCode.value = data.dev_code || ''
    startCountdown()
    ElMessage.success(devCode.value ? `验证码已生成：${devCode.value}` : '验证码已发送')
  } catch {
    // 错误已由拦截器处理
  } finally {
    sendingCode.value = false
  }
}

async function handleVerifyCode() {
  if (!emailCode.value.trim()) {
    ElMessage.warning('请输入验证码')
    return
  }

  verifyingCode.value = true
  try {
    await verifyEmailCode(form.email, emailCode.value.trim())
    emailVerified.value = true
    ElMessage.success('邮箱验证成功')
  } catch {
    emailVerified.value = false
  } finally {
    verifyingCode.value = false
  }
}

async function goToInterestStep() {
  if (!emailVerified.value) {
    ElMessage.warning('请先完成邮箱验证')
    return
  }
  await ensureTagsLoaded()
  currentStep.value = 2
}

async function handleRegister() {
  if (form.tag_ids.length < MIN_INTEREST_SELECTION) {
    tagError.value = true
    ElMessage.warning(`请至少选择 ${MIN_INTEREST_SELECTION} 个兴趣标签`)
    return
  }
  tagError.value = false

  loading.value = true
  try {
    await authStore.register({
      username: form.username,
      password: form.password,
      gender: form.gender,
      email: form.email,
      tag_ids: form.tag_ids,
    })
    ElMessage.success('注册成功')
    router.push('/recommend')
  } catch {
    // 错误已由 axios 拦截器处理
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(clearCountdown)
</script>

<template>
  <div class="register-page">
    <div class="register-shell">
      <section class="register-copy card-panel">
        <span class="page-kicker">注册</span>
        <h1>三步创建你的社区账号。</h1>
        <p>先填账号信息，再验证邮箱，最后选择兴趣。</p>

        <div class="copy-links">
          <router-link to="/login">
            <el-button plain size="large">已有账号，去登录</el-button>
          </router-link>
          <router-link to="/">
            <el-button text size="large">回首页</el-button>
          </router-link>
        </div>
      </section>

      <el-card class="register-card" shadow="never">
        <div class="brand-row">
          <div class="brand-mark">
            <el-icon :size="20"><Connection /></el-icon>
          </div>
          <div>
            <h2>注册账号</h2>
            <p>完成后直接进入推荐页。</p>
          </div>
        </div>

        <el-steps :active="currentStep" finish-status="success" simple class="steps">
          <el-step title="账号" />
          <el-step title="邮箱" />
          <el-step title="兴趣" />
        </el-steps>

        <div v-show="currentStep === 0" class="step-panel">
          <el-form ref="accountFormRef" :model="form" :rules="rules" label-position="top" size="large">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" placeholder="请输入用户名" />
            </el-form-item>

            <el-form-item label="邮箱" prop="email">
              <el-input v-model="form.email" placeholder="请输入常用邮箱" />
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" />
            </el-form-item>

            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input v-model="form.confirmPassword" type="password" show-password placeholder="再次输入密码" />
            </el-form-item>

            <el-form-item label="性别">
              <el-radio-group v-model="form.gender">
                <el-radio value="male">男</el-radio>
                <el-radio value="female">女</el-radio>
                <el-radio value="other">其他</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <div class="actions actions-end">
            <el-button type="primary" @click="goToEmailStep">下一步</el-button>
          </div>
        </div>

        <div v-show="currentStep === 1" class="step-panel">
          <RegisterEmailStep
            v-model:code="emailCode"
            :email="form.email"
            :countdown="countdown"
            :sending="sendingCode"
            :verifying="verifyingCode"
            :verified="emailVerified"
            :dev-code="devCode"
            @send-code="handleSendCode"
            @verify-code="handleVerifyCode"
          />

          <div class="actions">
            <el-button @click="currentStep = 0">上一步</el-button>
            <el-button type="primary" @click="goToInterestStep">下一步</el-button>
          </div>
        </div>

        <div v-show="currentStep === 2" class="step-panel">
          <RegisterInterestStep
            v-model:selected-tag-ids="form.tag_ids"
            :groups="tagGroups"
            :loading="tagsLoading"
            :min-selection="MIN_INTEREST_SELECTION"
          />

          <div v-if="tagError" class="tag-hint">
            请至少选择 {{ MIN_INTEREST_SELECTION }} 个兴趣标签
          </div>

          <div class="actions">
            <el-button @click="currentStep = 1">上一步</el-button>
            <el-button type="primary" :loading="loading" @click="handleRegister">完成注册</el-button>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  padding: 24px;
}

.register-shell {
  max-width: 1320px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 0.92fr) minmax(0, 1.08fr);
  gap: 24px;
  align-items: start;
}

.card-panel,
.register-card {
  border: 1px solid var(--kr-border);
  border-radius: 34px;
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay);
}

.register-copy {
  min-height: 320px;
  padding: 34px;
  background: var(--kr-bg-soft);
}

.page-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--kr-primary-strong);
  background: var(--kr-primary-soft);
}

.register-copy h1,
.brand-row h2 {
  letter-spacing: -0.05em;
}

.register-copy h1 {
  max-width: 9ch;
  font-size: clamp(3rem, 6vw, 5.4rem);
  line-height: 0.9;
}

.register-copy p,
.brand-row p,
.tag-hint {
  margin-top: 16px;
  color: var(--kr-text-soft);
  line-height: 1.8;
}

.copy-links {
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
  background: var(--kr-secondary);
  box-shadow: var(--kr-shadow-clay-soft);
}

.steps {
  margin-bottom: 26px;
}

.step-panel {
  display: grid;
  gap: 18px;
}

.actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.actions-end {
  justify-content: flex-end;
}

.tag-hint {
  margin-top: 0;
  color: var(--kr-danger);
  font-weight: 700;
}

@media (max-width: 1024px) {
  .register-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .register-page {
    padding: 16px;
  }

  .copy-links,
  .actions,
  .actions-end {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
