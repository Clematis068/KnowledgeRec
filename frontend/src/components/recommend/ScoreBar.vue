<template>
  <div class="score-bar">
    <div
      class="segment cf"
      :style="{ width: pct(cfScore) }"
      :title="`CF: ${cfScore.toFixed(4)}`"
    />
    <div
      class="segment graph"
      :style="{ width: pct(graphScore) }"
      :title="`Graph: ${graphScore.toFixed(4)}`"
    />
    <div
      class="segment semantic"
      :style="{ width: pct(semanticScore) }"
      :title="`Semantic: ${semanticScore.toFixed(4)}`"
    />
    <div
      class="segment hot"
      :style="{ width: pct(hotScore) }"
      :title="`Hot: ${hotScore.toFixed(4)}`"
    />
    <div
      class="segment context"
      :style="{ width: pct(contextScore) }"
      :title="`Context: ${contextScore.toFixed(4)}`"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  cfScore: { type: Number, default: 0 },
  graphScore: { type: Number, default: 0 },
  semanticScore: { type: Number, default: 0 },
  hotScore: { type: Number, default: 0 },
  contextScore: { type: Number, default: 0 },
})

const total = computed(() => (
  props.cfScore + props.graphScore + props.semanticScore + props.hotScore + props.contextScore || 1
))

function pct(val) {
  return ((val / total.value) * 100).toFixed(1) + '%'
}
</script>

<style scoped>
.score-bar {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  background: #ebeef5;
}

.segment {
  min-width: 2px;
  transition: width 0.3s;
}

.cf { background: #409eff; }
.graph { background: #67c23a; }
.semantic { background: #e6a23c; }
.hot { background: #f56c6c; }
.context { background: #8b5cf6; }
</style>
