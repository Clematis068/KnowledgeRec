<script setup>
import { reactive, ref, watch } from 'vue'

const props = defineProps({
  password: {
    type: String,
    default: '',
  },
  confirmPassword: {
    type: String,
    default: '',
  },
  rules: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['submit', 'back', 'update:password', 'update:confirmPassword'])
const formRef = ref()
const localForm = reactive({
  password: props.password,
  confirmPassword: props.confirmPassword,
})

watch(
  () => props.password,
  (value) => {
    localForm.password = value
  },
)

watch(
  () => props.confirmPassword,
  (value) => {
    localForm.confirmPassword = value
  },
)

async function validate() {
  return formRef.value?.validate().catch(() => false)
}

function handlePasswordInput(value) {
  localForm.password = value
  emit('update:password', value)
}

function handleConfirmPasswordInput(value) {
  localForm.confirmPassword = value
  emit('update:confirmPassword', value)
}

defineExpose({ validate })
</script>

<template>
  <div class="password-reset-step">
    <el-alert
      title="请输入新的登录密码，提交后使用新密码登录。"
      type="success"
      :closable="false"
      show-icon
    />

    <el-form ref="formRef" :model="localForm" :rules="rules" label-position="top" size="large">
      <el-form-item label="新密码" prop="password">
        <el-input
          :model-value="localForm.password"
          type="password"
          show-password
          placeholder="请输入至少 6 位新密码"
          @update:model-value="handlePasswordInput"
        />
      </el-form-item>

      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input
          :model-value="localForm.confirmPassword"
          type="password"
          show-password
          placeholder="再次输入新密码"
          @update:model-value="handleConfirmPasswordInput"
          @keyup.enter="$emit('submit')"
        />
      </el-form-item>

      <div class="actions">
        <el-button @click="$emit('back')">返回上一步</el-button>
        <el-button type="primary" :loading="loading" @click="$emit('submit')">
          重置密码
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.password-reset-step {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
</style>
