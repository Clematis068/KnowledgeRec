<script setup>
import { computed } from 'vue'

const ROUTE_META = {
  cf: { label: '协同过滤', color: '#409eff' },
  graph: { label: '图谱召回', color: '#67c23a' },
  semantic: { label: '语义召回', color: '#e6a23c' },
  hot: { label: '热门召回', color: '#f56c6c' },
}

const TIME_SLOT_LABELS = {
  night: '夜间',
  morning: '上午',
  noon: '中午',
  afternoon: '下午',
  evening: '晚上',
}

const STAGE_LABELS = {
  cold: '冷启动',
  warm: '成长期',
  active: '活跃期',
}

const props = defineProps({
  visible: { type: Boolean, default: false },
  debug: { type: Object, default: null },
})

const emit = defineEmits(['update:visible'])

const weightRows = computed(() => (
  ['cf', 'graph', 'semantic', 'hot'].map((key) => ({
    key,
    label: ROUTE_META[key].label,
    color: ROUTE_META[key].color,
    base: Number(props.debug?.weights_base?.[key] || 0),
    used: Number(props.debug?.weights_used?.[key] || 0),
  }))
))

const routeRows = computed(() => (
  ['cf', 'graph', 'semantic', 'hot'].map((key) => ({
    key,
    label: ROUTE_META[key].label,
    color: ROUTE_META[key].color,
    available: Boolean(props.debug?.route_availability?.[key]),
    count: Number(props.debug?.route_counts?.[key] || 0),
    samples: props.debug?.route_samples?.[key] || [],
  }))
))

const fusionPreview = computed(() => props.debug?.fusion_preview || [])
const finalPreview = computed(() => props.debug?.final_preview || [])
const stageLabel = computed(() => STAGE_LABELS[props.debug?.user_stage] || '未知')

function closePanel() {
  emit('update:visible', false)
}

function formatPercent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function formatScore(value) {
  return Number(value || 0).toFixed(4)
}

function formatTimeSlot(value) {
  return TIME_SLOT_LABELS[value] || value || '未提供'
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    title="推荐调试"
    direction="rtl"
    size="min(620px, calc(100vw - 24px))"
    destroy-on-close
    :lock-scroll="false"
    class="debug-drawer"
    @close="closePanel"
  >
    <div class="debug-panel">
      <div class="debug-head">
        <div>
          <span class="panel-kicker">实时调试</span>
          <h2>推荐过程面板</h2>
        </div>
        <el-tag size="small" type="primary">{{ stageLabel }}</el-tag>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="展示当前请求的权重、候选池、融合结果和最终输出。"
      />

      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>当前概况</span>
          </div>
        </template>

        <div v-if="debug" class="overview-grid">
          <div class="metric-item">
            <span class="metric-label">融合前</span>
            <span class="metric-value">{{ debug.result_count_before_filter || 0 }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">过滤后</span>
            <span class="metric-value">{{ debug.result_count_after_filter || 0 }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">负反馈过滤</span>
            <span class="metric-value">{{ debug.negative_feedback_applied ? '已开启' : '未开启' }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">上下文地区</span>
            <span class="metric-value">{{ debug.context?.region_code || '未提供' }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">上下文时段</span>
            <span class="metric-value">{{ formatTimeSlot(debug.context?.time_slot) }}</span>
          </div>
        </div>
        <el-empty v-else description="还没有调试数据，先刷新一次推荐" :image-size="72" />
      </el-card>

      <el-card v-if="debug" shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>权重分配</span>
            <span class="panel-tip">基础 / 实际</span>
          </div>
        </template>

        <div v-for="row in weightRows" :key="row.key" class="weight-row">
          <div class="route-title">
            <span class="route-dot" :style="{ backgroundColor: row.color }"></span>
            <span>{{ row.label }}</span>
          </div>
          <div class="weight-values">
            <span>{{ formatPercent(row.base) }}</span>
            <span class="weight-arrow">→</span>
            <span class="weight-used">{{ formatPercent(row.used) }}</span>
          </div>
        </div>
      </el-card>

      <el-card v-if="debug" shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>三路候选池</span>
            <span class="panel-tip">每路 top 5</span>
          </div>
        </template>

        <div v-for="row in routeRows" :key="row.key" class="route-section">
          <div class="route-summary">
            <div class="route-title">
              <span class="route-dot" :style="{ backgroundColor: row.color }"></span>
              <span>{{ row.label }}</span>
            </div>
            <div class="route-status">
              <el-tag size="small" effect="plain">
                {{ row.available ? '可用' : '无结果' }}
              </el-tag>
              <span class="route-count">{{ row.count }} 条</span>
            </div>
          </div>

          <div v-if="row.samples.length" class="sample-list">
            <div v-for="sample in row.samples" :key="`${row.key}-${sample.post_id}`" class="sample-item">
              <div class="sample-main">
                <router-link :to="`/posts/${sample.post_id}`" class="sample-title">
                  {{ sample.title || `帖子 #${sample.post_id}` }}
                </router-link>
                <span class="sample-score">{{ formatScore(sample.score) }}</span>
              </div>
              <div class="sample-meta">
                <el-tag v-if="sample.selected" size="small" effect="plain">入选</el-tag>
                <span v-else class="sample-alt">备选</span>
              </div>
            </div>
          </div>
          <el-empty v-else description="该路当前没有候选" :image-size="56" />
        </div>
      </el-card>

      <el-card v-if="debug" shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>融合预览</span>
            <span class="panel-tip">过滤前</span>
          </div>
        </template>

        <div v-if="fusionPreview.length" class="sample-list">
          <div v-for="item in fusionPreview" :key="`fusion-${item.post_id}`" class="sample-item">
            <div class="sample-main">
              <router-link :to="`/posts/${item.post_id}`" class="sample-title">
                {{ item.title || `帖子 #${item.post_id}` }}
              </router-link>
              <span class="sample-score">{{ formatScore(item.final_score) }}</span>
            </div>
            <div class="preview-breakdown">
              <span>协同过滤 {{ formatScore(item.cf_score) }}</span>
              <span>图谱 {{ formatScore(item.graph_score) }}</span>
              <span>语义 {{ formatScore(item.semantic_score) }}</span>
              <span>热门 {{ formatScore(item.hot_score) }}</span>
              <span>上下文 {{ formatScore(item.context_score) }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无融合结果" :image-size="56" />
      </el-card>

      <el-card v-if="debug" shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>最终输出</span>
            <span class="panel-tip">过滤后</span>
          </div>
        </template>

        <div v-if="finalPreview.length" class="sample-list">
          <div v-for="item in finalPreview" :key="`final-${item.post_id}`" class="sample-item">
            <div class="sample-main">
              <router-link :to="`/posts/${item.post_id}`" class="sample-title">
                {{ item.title || `帖子 #${item.post_id}` }}
              </router-link>
              <span class="sample-score">{{ formatScore(item.final_score) }}</span>
            </div>
            <div class="preview-breakdown">
              <span>上下文 {{ formatScore(item.context_score) }}</span>
              <span>惩罚 {{ formatScore(item.negative_penalty) }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无最终结果" :image-size="56" />
      </el-card>
    </div>
  </el-drawer>
</template>

<style scoped>
:deep(.debug-drawer) {
  max-width: calc(100vw - 24px);
}

:deep(.debug-drawer .el-drawer__body) {
  overflow: auto;
  padding-top: 0;
}

.debug-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 12px;
}

.debug-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-kicker {
  display: inline-flex;
  margin-bottom: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--kr-text);
  background: rgba(255, 255, 255, 0.78);
}

.debug-head h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1;
  letter-spacing: -0.05em;
}

.panel-card {
  border-radius: 24px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-weight: 800;
}

.panel-tip {
  font-size: 12px;
  color: var(--kr-text-muted);
  font-weight: 600;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  background: #fff0e8;
  border-radius: 16px;
}

.metric-label {
  font-size: 12px;
  color: var(--kr-text-muted);
}

.metric-value {
  font-size: 18px;
  font-weight: 800;
  color: var(--kr-text);
}

.weight-row,
.route-summary,
.sample-item,
.sample-main,
.preview-breakdown,
.weight-values,
.route-title,
.route-status {
  display: flex;
  align-items: center;
}

.weight-row,
.route-summary,
.sample-item {
  justify-content: space-between;
}

.weight-row {
  padding: 10px 0;
  border-bottom: 1px solid rgba(230, 205, 185, 0.8);
}

.weight-row:last-child,
.route-section:last-child {
  border-bottom: none;
}

.route-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.route-title,
.route-status,
.preview-breakdown,
.weight-values {
  gap: 8px;
}

.weight-arrow {
  color: var(--kr-text-muted);
}

.weight-used {
  font-weight: 800;
}

.route-section {
  padding: 12px 0;
  border-bottom: 1px solid rgba(230, 205, 185, 0.8);
}

.sample-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.sample-item {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  padding: 14px;
  background: #fff7f1;
  border-radius: 16px;
}

.sample-main {
  justify-content: space-between;
  gap: 12px;
}

.sample-title {
  color: var(--kr-text);
  font-weight: 700;
  line-height: 1.6;
  text-decoration: none;
}

.sample-title:hover {
  color: var(--kr-text);
}

.sample-score {
  flex-shrink: 0;
  font-family: monospace;
  color: var(--kr-text-soft);
}

.sample-meta,
.preview-breakdown,
.route-count,
.sample-alt {
  font-size: 12px;
  color: var(--kr-text-muted);
}

.preview-breakdown {
  flex-wrap: wrap;
}

@media (max-width: 720px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .sample-main,
  .route-summary,
  .debug-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
