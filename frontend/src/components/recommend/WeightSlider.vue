<template>
  <div class="weight-slider">
    <div class="slider-row" v-for="(item, idx) in sliders" :key="item.key">
      <span class="label" :style="{ color: item.color }">{{ item.name }}</span>
      <el-slider
        v-model="item.value"
        :min="0"
        :max="100"
        :step="1"
        :show-tooltip="true"
        :format-tooltip="(v) => (v / 100).toFixed(2)"
        style="flex: 1; margin: 0 12px"
        @input="onSliderChange(idx)"
      />
      <span class="value">{{ (item.value / 100).toFixed(2) }}</span>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const emit = defineEmits(['update:weights'])

const sliders = reactive([
  { key: 'cf', name: 'CF协同过滤', color: '#409eff', value: 35 },
  { key: 'graph', name: 'Graph图谱', color: '#67c23a', value: 35 },
  { key: 'semantic', name: 'Semantic语义', color: '#e6a23c', value: 30 },
])

function onSliderChange(changedIdx) {
  const changed = sliders[changedIdx].value
  const remaining = 100 - changed
  const others = sliders.filter((_, i) => i !== changedIdx)
  const otherSum = others.reduce((s, o) => s + o.value, 0)

  if (otherSum === 0) {
    // 平分剩余
    others.forEach((o) => { o.value = Math.round(remaining / others.length) })
  } else {
    // 按原比例分配
    others.forEach((o) => { o.value = Math.round((o.value / otherSum) * remaining) })
  }

  // 修正舍入误差
  const total = sliders.reduce((s, o) => s + o.value, 0)
  if (total !== 100) {
    const fixIdx = changedIdx === 0 ? 1 : 0
    sliders[fixIdx].value += 100 - total
  }

  emitWeights()
}

function emitWeights() {
  emit('update:weights', {
    cf: sliders[0].value / 100,
    graph: sliders[1].value / 100,
    semantic: sliders[2].value / 100,
  })
}
</script>

<style scoped>
.weight-slider {
  padding: 8px 0;
}

.slider-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.label {
  width: 120px;
  font-size: 13px;
  font-weight: 600;
}

.value {
  width: 40px;
  text-align: right;
  font-size: 13px;
  font-family: monospace;
}
</style>
