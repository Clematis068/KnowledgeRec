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
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: #f1e3d4;
  box-shadow: inset 2px 2px 6px rgba(219, 191, 165, 0.32), inset -2px -2px 6px rgba(255, 255, 255, 0.85);
}

.segment {
  min-width: 2px;
  transition: width 0.3s ease;
}

.cf { background: linear-gradient(90deg, #2563eb, #4f8cff); }
.graph { background: linear-gradient(90deg, #22c55e, #5ee28a); }
.semantic { background: linear-gradient(90deg, #ffb800, #ffd667); }
.hot { background: linear-gradient(90deg, #ff4d8d, #ff7db2); }
.context { background: linear-gradient(90deg, #ff8f7a, #ffb29b); }
</style>
