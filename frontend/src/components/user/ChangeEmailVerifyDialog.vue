<script setup>
import RegisterEmailStep from '../auth/RegisterEmailStep.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
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
  saving: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:visible',
  'update:code',
  'send-code',
  'verify-code',
  'confirm',
])
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="验证新邮箱"
    width="520px"
    destroy-on-close
    @update:model-value="emit('update:visible', $event)"
  >
    <RegisterEmailStep
      :email="email"
      :code="code"
      :countdown="countdown"
      :sending="sending"
      :verifying="verifying"
      :verified="verified"
      :dev-code="devCode"
      info-title="我们会向新邮箱发送 6 位验证码，验证通过后才允许保存邮箱变更。"
      success-title="新邮箱验证成功"
      success-subtitle="现在可以确认更新邮箱了"
      send-button-text="发送验证码"
      verify-button-text="验证邮箱"
      @update:code="emit('update:code', $event)"
      @send-code="emit('send-code')"
      @verify-code="emit('verify-code')"
    />

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button
          type="primary"
          :disabled="!verified"
          :loading="saving"
          @click="emit('confirm')"
        >
          确认更新邮箱
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
