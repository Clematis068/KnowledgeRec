<template>
  <el-card shadow="never" class="rec-card">
    <div class="card-top">
      <div>
        <span class="card-kicker">Recommended For You</span>
        <router-link :to="`/posts/${item.post_id}`" class="title">
          {{ item.title || `帖子 #${item.post_id}` }}
        </router-link>
      </div>
      <div class="score-chip">
        {{ displayScore }}
      </div>
    </div>

    <p class="summary">{{ item.summary || '暂时没有摘要，但这篇内容与你当前的知识探索路径高度相关。' }}</p>

    <ScoreBar
      :cf-score="item.cf_score || 0"
      :graph-score="item.graph_score || 0"
      :semantic-score="item.semantic_score || 0"
    />

    <div class="score-legend">
      <span class="legend cf">CF {{ (item.cf_score || 0).toFixed(3) }}</span>
      <span class="legend graph">Graph {{ (item.graph_score || 0).toFixed(3) }}</span>
      <span class="legend semantic">Semantic {{ (item.semantic_score || 0).toFixed(3) }}</span>
    </div>

    <div class="card-footer">
      <el-button size="small" type="primary" plain @click="$emit('showReason', item.post_id)">
        <el-icon><ChatDotRound /></el-icon>
        推荐理由
      </el-button>
      <el-button
        v-if="allowFeedback"
        size="small"
        text
        class="feedback-button"
        @click="$emit('dislike', item.post_id)"
      >
        <el-icon><CircleClose /></el-icon>
        不感兴趣
      </el-button>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import ScoreBar from './ScoreBar.vue'

const props = defineProps({
  item: { type: Object, required: true },
  allowFeedback: { type: Boolean, default: false },
})

defineEmits(['showReason', 'dislike'])

const displayScore = computed(() => {
  const score = props.item.final_score ?? props.item.score
  return score == null ? '--' : score.toFixed(4)
})
</script>

<style scoped>
.rec-card {
  margin-bottom: 14px;
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.card-kicker {
  display: inline-flex;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-primary);
}

.title {
  display: inline-block;
  font-size: 22px;
  line-height: 1.2;
  letter-spacing: -0.03em;
  font-weight: 700;
}

.title:hover {
  color: var(--kr-primary-strong);
}

.score-chip {
  flex-shrink: 0;
  padding: 10px 14px;
  border-radius: 999px;
  font-weight: 700;
  color: #8a3b12;
  background: rgba(249, 115, 22, 0.14);
}

.summary {
  margin: 16px 0;
  color: var(--kr-text-soft);
  line-height: 1.8;
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.score-legend,
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.score-legend {
  margin-top: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--kr-text-muted);
}

.legend::before {
  content: '';
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 6px;
  border-radius: 999px;
}

.cf::before {
  background: #409eff;
}

.graph::before {
  background: #67c23a;
}

.semantic::before {
  background: #e6a23c;
}

.card-footer {
  margin-top: 18px;
}

.feedback-button {
  color: #b42318;
}
</style>
