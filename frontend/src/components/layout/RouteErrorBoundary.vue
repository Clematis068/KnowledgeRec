<script setup>
import { ref, onErrorCaptured, watch } from 'vue'
import { useRoute } from 'vue-router'

const error = ref(null)
const route = useRoute()

onErrorCaptured((err) => {
  console.error('[RouteErrorBoundary]', err)
  error.value = err
  return false
})

watch(() => route.fullPath, () => {
  error.value = null
})

function reload() {
  window.location.reload()
}
</script>

<template>
  <div v-if="error" class="route-error">
    <h2>页面出错了</h2>
    <p>{{ error?.message || '渲染失败，请稍后再试' }}</p>
    <div class="actions">
      <button @click="reload">刷新页面</button>
      <button @click="$router.back()">返回上一页</button>
    </div>
  </div>
  <slot v-else />
</template>

<style scoped>
.route-error {
  padding: 32px;
  border: 1px solid var(--cds-border-subtle);
  background: var(--cds-layer-01);
  display: grid;
  gap: 12px;
  max-width: 640px;
  margin: 24px auto;
}
.route-error h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--cds-text-primary);
}
.route-error p {
  color: var(--cds-text-secondary);
  font-size: 14px;
  line-height: 1.6;
  word-break: break-all;
}
.actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.actions button {
  padding: 6px 16px;
  border: 1px solid var(--cds-border-subtle);
  background: var(--cds-background);
  cursor: pointer;
  font-size: 13px;
}
.actions button:hover {
  background: var(--cds-layer-02, #e5e7eb);
}
</style>
