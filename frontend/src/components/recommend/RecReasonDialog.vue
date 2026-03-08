<template>
  <el-dialog
    v-model="visible"
    title="推荐理由"
    width="500px"
    :close-on-click-modal="true"
  >
    <div v-if="loading" class="loading-area">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span style="margin-left: 8px">正在生成推荐理由...</span>
    </div>
    <div v-else class="reason-text">{{ reason }}</div>
  </el-dialog>
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
.loading-area {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: #909399;
}

.reason-text {
  line-height: 1.8;
  font-size: 14px;
  padding: 8px 0;
}
</style>
