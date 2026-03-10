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
})

const emit = defineEmits(['update:code', 'send-code', 'verify-code'])

function handleInput(value) {
  emit('update:code', value)
}
</script>

<template>
  <div class="email-step">
    <el-alert
      title="我们会向你的邮箱发送 6 位验证码，验证通过后才能继续。"
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
        {{ countdown > 0 ? `${countdown}s 后重发` : '发送验证码' }}
      </el-button>
      <el-button type="primary" :loading="verifying" @click="$emit('verify-code')">
        验证邮箱
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
      title="邮箱验证成功"
      sub-title="可以继续选择兴趣标签了"
    />
  </div>
</template>

<style scoped>
.email-step {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.email-row {
  padding: 16px;
  border-radius: 12px;
  background: #f5f7fa;
}

.email-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.email-value {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.verify-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.code-input {
  flex: 1;
}
</style>
