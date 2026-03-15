<script setup>
import { onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Connection } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index'

import PasswordResetFormStep from '../components/auth/PasswordResetFormStep.vue'
import RegisterEmailStep from '../components/auth/RegisterEmailStep.vue'
import {
  resetPassword,
  sendResetPasswordCode,
  verifyResetPasswordCode,
} from '../api/auth'

const router = useRouter()
const emailFormRef = ref()
const resetFormStepRef = ref()

const currentStep = shallowRef(0)
const sendingCode = shallowRef(false)
const verifyingCode = shallowRef(false)
const resettingPassword = shallowRef(false)
const emailVerified = shallowRef(false)
const emailCode = shallowRef('')
const countdown = shallowRef(0)
const devCode = shallowRef('')

const form = reactive({
  email: '',
  password: '',
  confirmPassword: '',
})

let countdownTimer = null

const validateConfirm = (_rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次密码不一致'))
    return
  }
  callback()
}

const emailRules = {
  email: [
    { required: true, message: '请输入注册邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
}

const resetRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

watch(
  () => form.email,
  () => {
    emailVerified.value = false
    emailCode.value = ''
    devCode.value = ''
    clearCountdown()
    countdown.value = 0
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
  if (!countdownTimer) return
  window.clearInterval(countdownTimer)
  countdownTimer = null
}

async function goToEmailVerifyStep() {
  const valid = await emailFormRef.value?.validate().catch(() => false)
  if (!valid) return
  currentStep.value = 1
}

async function handleSendCode() {
  sendingCode.value = true
  try {
    const data = await sendResetPasswordCode(form.email)
    devCode.value = data.dev_code || ''
    startCountdown()
    ElMessage.success(devCode.value ? `验证码已生成：${devCode.value}` : '验证码已发送')
  } catch {
    // 错误已由 axios 拦截器处理
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
    await verifyResetPasswordCode(form.email, emailCode.value.trim())
    emailVerified.value = true
    ElMessage.success('邮箱验证成功')
  } catch {
    emailVerified.value = false
  } finally {
    verifyingCode.value = false
  }
}

function goToPasswordStep() {
  if (!emailVerified.value) {
    ElMessage.warning('请先完成邮箱验证')
    return
  }
  currentStep.value = 2
}

async function handleResetPassword() {
  const valid = await resetFormStepRef.value?.validate()
  if (!valid) return

  resettingPassword.value = true
  try {
    await resetPassword({
      email: form.email,
      password: form.password,
    })
    ElMessage.success('密码重置成功，请重新登录')
    router.push('/login')
  } catch {
    // 错误已由 axios 拦截器处理
  } finally {
    resettingPassword.value = false
  }
}

onBeforeUnmount(clearCountdown)
</script>

<template>
  <div class="forgot-page">
    <div class="forgot-shell">
      <section class="forgot-copy card-panel">
        <span class="page-kicker">重置密码</span>
        <h1>通过邮箱验证码重置你的密码。</h1>
        <p>输入注册邮箱，完成验证后即可设置一个新的登录密码。</p>

        <div class="copy-actions">
          <router-link to="/login">
            <el-button plain size="large">返回登录</el-button>
          </router-link>
          <router-link to="/register">
            <el-button text size="large">去注册</el-button>
          </router-link>
        </div>
      </section>

      <aside class="forgot-form-wrap">
        <el-card class="forgot-card" shadow="never">
          <div class="brand-row">
            <div class="brand-mark">
              <el-icon :size="20"><Connection /></el-icon>
            </div>
            <div>
              <h2>找回密码</h2>
              <p>三步完成邮箱校验与密码重置。</p>
            </div>
          </div>

          <el-steps :active="currentStep" finish-status="success" simple class="steps">
            <el-step title="邮箱" />
            <el-step title="验证" />
            <el-step title="新密码" />
          </el-steps>

          <div v-show="currentStep === 0" class="step-panel">
            <el-form ref="emailFormRef" :model="form" :rules="emailRules" label-position="top" size="large">
              <el-form-item label="注册邮箱" prop="email">
                <el-input v-model="form.email" placeholder="请输入注册时使用的邮箱" />
              </el-form-item>
              <el-button type="primary" class="submit-button" @click="goToEmailVerifyStep">
                下一步
              </el-button>
            </el-form>
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
              info-title="我们会向该邮箱发送 6 位重置密码验证码，验证通过后才能设置新密码。"
              success-subtitle="可以继续设置新密码了"
              @send-code="handleSendCode"
              @verify-code="handleVerifyCode"
            />

            <div class="step-actions">
              <el-button @click="currentStep = 0">返回修改邮箱</el-button>
              <el-button type="primary" @click="goToPasswordStep">下一步</el-button>
            </div>
          </div>

          <div v-show="currentStep === 2" class="step-panel">
            <PasswordResetFormStep
              ref="resetFormStepRef"
              :password="form.password"
              :confirm-password="form.confirmPassword"
              :rules="resetRules"
              :loading="resettingPassword"
              @back="currentStep = 1"
              @update:password="form.password = $event"
              @update:confirm-password="form.confirmPassword = $event"
              @submit="handleResetPassword"
            />
          </div>
        </el-card>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.forgot-page {
  min-height: 100vh;
  padding: 24px;
}

.forgot-shell {
  max-width: 1240px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) 440px;
  gap: 24px;
  align-items: stretch;
}

.card-panel,
.forgot-card {
  border: 1px solid var(--kr-border);
  border-radius: 34px;
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay);
}

.forgot-copy {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 540px;
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

.forgot-copy h1,
.brand-row h2 {
  letter-spacing: -0.05em;
}

.forgot-copy h1 {
  max-width: 10ch;
  font-size: clamp(3rem, 6vw, 5rem);
  line-height: 0.9;
}

.forgot-copy p,
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
  background: var(--kr-secondary);
  box-shadow: var(--kr-shadow-clay-soft);
}

.steps {
  margin-bottom: 20px;
}

.step-panel {
  display: grid;
  gap: 18px;
}

.submit-button {
  width: 100%;
  min-height: 50px;
}

.step-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

@media (max-width: 960px) {
  .forgot-shell {
    grid-template-columns: 1fr;
  }

  .forgot-copy {
    min-height: auto;
  }
}

@media (max-width: 640px) {
  .forgot-page {
    padding: 16px;
  }

  .copy-actions,
  .step-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
