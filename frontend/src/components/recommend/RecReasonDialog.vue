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
      <div v-if="graphPaths.length" class="reason-evidence">
        <span class="evidence-label">Graph-RAG 检索路径</span>
        <ul class="path-list">
          <li v-for="(p, idx) in graphPaths" :key="idx" class="path-item">
            <span class="path-badge" :class="`path-badge--${p.type}`">
              {{ pathTypeLabel(p.type) }}
            </span>
            <span class="path-text">{{ p.text }}</span>
          </li>
        </ul>
      </div>
      <div v-else-if="graphPathText" class="reason-evidence">
        <span class="evidence-label">图谱依据</span>
        <div class="evidence-text">{{ graphPathText }}</div>
      </div>
      <div v-if="topChannels.length" class="reason-channels">
        <span class="evidence-label">主要召回来源</span>
        <div class="channel-list">
          <span v-for="c in topChannels" :key="c.channel" class="channel-chip">
            {{ c.label }} · {{ (c.score * 100).toFixed(0) }}%
          </span>
        </div>
      </div>
      <div class="reason-scroll">
        <div class="reason-text">{{ reason }}</div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { streamRecommendReason } from '../../api/recommendation'

const props = defineProps({
  modelValue: Boolean,
  userId: Number,
  postId: Number,
  recItem: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const reason = ref('')
const graphPath = ref(null)
const graphPaths = ref([])
const topChannels = ref([])
const loading = ref(false)

const graphPathText = computed(() => (
  graphPath.value?.text || props.recItem?.graph_path_text || ''
))

const PATH_TYPE_LABELS = {
  social_1hop: '直接社交',
  social_2hop: '二阶社交',
  shared_tag: '标签关联',
  interest_tag: '兴趣命中',
  interest_domain: '领域匹配',
}
const pathTypeLabel = (t) => PATH_TYPE_LABELS[t] || t || '图路径'

function extractChannelScores(item) {
  if (!item) return null
  const fields = ['cf_score', 'swing_score', 'graph_score', 'semantic_score', 'knowledge_score', 'hot_score']
  const scores = {}
  for (const f of fields) {
    if (item[f] !== undefined && item[f] !== null) scores[f] = item[f]
  }
  return Object.keys(scores).length ? scores : null
}

let closeStream = null

function teardown() {
  if (closeStream) {
    closeStream()
    closeStream = null
  }
}

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && props.userId && props.postId) {
    teardown()
    loading.value = true
    reason.value = ''
    graphPath.value = null
    graphPaths.value = []
    topChannels.value = []

    const scores = extractChannelScores(props.recItem)
    closeStream = streamRecommendReason(props.userId, props.postId, scores, {
      onMeta: (meta) => {
        graphPath.value = meta.graph_path || null
        graphPaths.value = Array.isArray(meta.graph_paths) ? meta.graph_paths : []
        topChannels.value = meta.top_channels || []
        // meta 到达即可关闭骨架屏，文本区域开始显示增量内容
        loading.value = false
      },
      onDelta: (text) => {
        reason.value += text
      },
      onDone: () => {
        loading.value = false
        closeStream = null
      },
      onError: (msg) => {
        if (!reason.value) reason.value = msg || '获取推荐理由失败'
        loading.value = false
        closeStream = null
      },
    })
  } else if (!val) {
    teardown()
  }
})

onBeforeUnmount(teardown)

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
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay-soft);
}

.reason-text {
  line-height: 1.95;
  font-size: 14px;
  color: var(--kr-text);
  white-space: pre-wrap;
}

.reason-evidence,
.reason-channels {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.6);
}

.evidence-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--kr-text-soft);
  text-transform: uppercase;
}

.evidence-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--kr-text);
}

.channel-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.channel-chip {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--kr-text);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.path-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.path-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--kr-text);
}

.path-badge {
  flex-shrink: 0;
  margin-top: 2px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #fff;
  background: var(--kr-text-soft);
}

.path-badge--social_1hop { background: #3b82f6; }
.path-badge--social_2hop { background: #8b5cf6; }
.path-badge--shared_tag { background: #10b981; }
.path-badge--interest_tag { background: #f59e0b; }
.path-badge--interest_domain { background: #6b7280; }

.path-text {
  flex: 1;
}
</style>
