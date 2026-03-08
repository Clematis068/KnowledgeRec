<template>
  <el-card shadow="hover" class="rec-card">
    <div class="card-header">
      <router-link :to="`/posts/${item.post_id}`" class="title">
        {{ item.title || `帖子 #${item.post_id}` }}
      </router-link>
      <el-tag size="small" type="warning">{{ item.final_score?.toFixed(4) ?? item.score?.toFixed(4) }}</el-tag>
    </div>
    <p class="summary">{{ item.summary || '暂无摘要' }}</p>
    <ScoreBar
      :cf-score="item.cf_score || 0"
      :graph-score="item.graph_score || 0"
      :semantic-score="item.semantic_score || 0"
    />
    <div class="card-footer">
      <div class="score-legend">
        <span class="legend cf">CF {{ (item.cf_score || 0).toFixed(3) }}</span>
        <span class="legend graph">Graph {{ (item.graph_score || 0).toFixed(3) }}</span>
        <span class="legend semantic">Semantic {{ (item.semantic_score || 0).toFixed(3) }}</span>
      </div>
      <el-button size="small" type="primary" link @click="$emit('showReason', item.post_id)">
        <el-icon><ChatDotRound /></el-icon>
        推荐理由
      </el-button>
    </div>
  </el-card>
</template>

<script setup>
import ScoreBar from './ScoreBar.vue'

defineProps({ item: { type: Object, required: true } })
defineEmits(['showReason'])
</script>

<style scoped>
.rec-card {
  margin-bottom: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.title:hover {
  color: #409eff;
}

.summary {
  font-size: 13px;
  color: #606266;
  margin-bottom: 10px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.score-legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  font-family: monospace;
}

.legend::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}

.cf::before { background: #409eff; }
.graph::before { background: #67c23a; }
.semantic::before { background: #e6a23c; }
</style>
