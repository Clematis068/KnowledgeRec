<script setup>
const props = defineProps({
  email: {
    type: String,
    default: '',
  },
  code: {
    type: String,
    default: '',
  },
  countdown: {
    type: Number,
    default: 0,
  },
  sending: {
    type: Boolean,
    default: false,
  },
  verifying: {
    type: Boolean,
    default: false,
  },
  verified: {
    type: Boolean,
    default: false,
  },
  devCode: {
    type: String,
    default: '',
  },
  infoTitle: {
    type: String,
    default: '我们会向你的邮箱发送 6 位验证码，验证通过后才能继续。',
  },
  successTitle: {
    type: String,
    default: '邮箱验证成功',
  },
  successSubtitle: {
    type: String,
    default: '可以继续选择兴趣标签了',
  },
  sendButtonText: {
    type: String,
    default: '发送验证码',
  },
  verifyButtonText: {
    type: String,
    default: '验证邮箱',
  },
})

const emit = defineEmits(['update:code', 'send-code', 'verify-code'])

function handleInput(value) {
  emit('update:code', value)
}
</script>

<template>
  <div class="email-step">
    <el-alert
      :title="infoTitle"
      type="info"
      :closable="false"
      show-icon
    />

    <div class="email-row">
      <div class="email-label">当前邮箱</div>
      <div class="email-value">{{ email }}</div>
    </div>

    <div class="verify-row">
      <el-input
        :model-value="code"
        maxlength="6"
        placeholder="输入 6 位验证码"
        class="code-input"
        @update:model-value="handleInput"
      />
      <el-button :disabled="countdown > 0" :loading="sending" @click="$emit('send-code')">
        {{ countdown > 0 ? `${countdown}s 后重发` : sendButtonText }}
      </el-button>
      <el-button type="primary" :loading="verifying" @click="$emit('verify-code')">
        {{ verifyButtonText }}
      </el-button>
    </div>

    <el-alert
      v-if="devCode"
      :title="`开发模式验证码：${devCode}`"
      type="warning"
      :closable="false"
      show-icon
    />

    <el-result
      v-if="verified"
      icon="success"
      :title="successTitle"
      :sub-title="successSubtitle"
    />
  </div>
</template>

<style scoped>
.email-step {
  display: grid;
  gap: 16px;
}

.email-row {
  padding: 18px;
  border-radius: 24px;
  border: 1px solid var(--kr-border);
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay-soft);
}

.email-label {
  font-size: 12px;
  color: var(--kr-text-muted);
  margin-bottom: 6px;
  font-weight: 700;
}

.email-value {
  font-size: 15px;
  font-weight: 800;
  color: var(--kr-text);
}

.verify-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
}

.code-input {
  flex: 1;
}

@media (max-width: 720px) {
  .verify-row {
    grid-template-columns: 1fr;
  }
}
</style>
