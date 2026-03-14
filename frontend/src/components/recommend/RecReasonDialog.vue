<template>
  <el-drawer
    v-model="visible"
    title="推荐解释"
    direction="rtl"
    size="min(460px, calc(100vw - 24px))"
    :lock-scroll="false"
    destroy-on-close
    class="reason-drawer"
  >
    <div v-if="loading" class="loading-area">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span class="loading-text">正在生成推荐理由...</span>
    </div>
    <div v-else class="reason-panel">
      <div class="reason-head">
        <span class="reason-kicker">推荐说明</span>
        <h3>推荐给你的原因</h3>
      </div>
      <div class="reason-scroll">
        <div class="reason-text">{{ reason }}</div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getRecommendReason } from '../../api/recommendation'

const props = defineProps({
  modelValue: Boolean,
  userId: Number,
  postId: Number,
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const reason = ref('')
const loading = ref(false)

watch(() => props.modelValue, async (val) => {
  visible.value = val
  if (val && props.userId && props.postId) {
    loading.value = true
    reason.value = ''
    try {
      const data = await getRecommendReason(props.userId, props.postId)
      reason.value = data.reason
    } catch {
      reason.value = '获取推荐理由失败'
    } finally {
      loading.value = false
    }
  }
})

watch(visible, (val) => {
  if (!val) emit('update:modelValue', false)
})
</script>

<style scoped>
:deep(.reason-drawer) {
  max-width: calc(100vw - 24px);
}

:deep(.reason-drawer .el-drawer__body) {
  padding-top: 0;
  overflow: auto;
}

.loading-area {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--kr-text-soft);
}

.loading-text {
  margin-left: 8px;
}

.reason-panel {
  display: grid;
  gap: 18px;
}

.reason-head h3 {
  margin: 8px 0 0;
  font-size: 28px;
  line-height: 1.02;
  letter-spacing: -0.05em;
}

.reason-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--kr-text);
  background: rgba(255, 255, 255, 0.78);
}

.reason-scroll {
  max-height: calc(100vh - 170px);
  overflow: auto;
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(239, 247, 255, 0.92));
  box-shadow: var(--kr-shadow-clay-soft);
}

.reason-text {
  line-height: 1.95;
  font-size: 14px;
  color: var(--kr-text);
  white-space: pre-wrap;
}
</style>
