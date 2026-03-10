<script setup>
import { computed } from 'vue'

const ROUTE_META = {
  cf: { label: 'CF 协同过滤', color: '#409eff' },
  graph: { label: 'Graph 图谱', color: '#67c23a' },
  semantic: { label: 'Semantic 语义', color: '#e6a23c' },
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
  ['cf', 'graph', 'semantic'].map((key) => ({
    key,
    label: ROUTE_META[key].label,
    color: ROUTE_META[key].color,
    base: Number(props.debug?.weights_base?.[key] || 0),
    used: Number(props.debug?.weights_used?.[key] || 0),
  }))
))

const routeRows = computed(() => (
  ['cf', 'graph', 'semantic'].map((key) => ({
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
</script>

<template>
  <el-drawer
    :model-value="visible"
    title="推荐 Debug 面板"
    size="460px"
    destroy-on-close
    @close="closePanel"
  >
    <div class="debug-panel">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="这里展示当前推荐请求的实时调试信息，包括权重、候选池和融合结果。"
      />

      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>当前概况</span>
            <el-tag size="small" type="primary">{{ stageLabel }}</el-tag>
          </div>
        </template>

        <div v-if="debug" class="overview-grid">
          <div class="metric-item">
            <span class="metric-label">融合前结果</span>
            <span class="metric-value">{{ debug.result_count_before_filter || 0 }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">过滤后结果</span>
            <span class="metric-value">{{ debug.result_count_after_filter || 0 }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">负反馈过滤</span>
            <span class="metric-value">{{ debug.negative_feedback_applied ? '已开启' : '未开启' }}</span>
          </div>
        </div>
        <el-empty v-else description="还没有调试数据，先刷新一次推荐" :image-size="72" />
      </el-card>

      <el-card v-if="debug" shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>权重分配</span>
            <span class="panel-tip">基础权重 / 实际生效权重</span>
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
            <span class="panel-tip">展示每一路 top 5 备选</span>
          </div>
        </template>

        <div v-for="row in routeRows" :key="row.key" class="route-section">
          <div class="route-summary">
            <div class="route-title">
              <span class="route-dot" :style="{ backgroundColor: row.color }"></span>
              <span>{{ row.label }}</span>
            </div>
            <div class="route-status">
              <el-tag size="small" :type="row.available ? 'success' : 'info'">
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
                <el-tag v-if="sample.selected" size="small" type="warning">入选最终结果</el-tag>
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
            <span class="panel-tip">先融合，再做负反馈过滤</span>
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
              <span>CF {{ formatScore(item.cf_score) }}</span>
              <span>Graph {{ formatScore(item.graph_score) }}</span>
              <span>Semantic {{ formatScore(item.semantic_score) }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无融合结果" :image-size="56" />
      </el-card>

      <el-card v-if="debug" shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span>最终输出</span>
            <span class="panel-tip">已考虑负反馈/屏蔽</span>
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
              <span>Penalty {{ formatScore(item.negative_penalty) }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无最终结果" :image-size="56" />
      </el-card>
    </div>
  </el-drawer>
</template>

<style scoped>
.debug-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-card {
  border-radius: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-weight: 600;
}

.panel-tip {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 10px;
}

.metric-label {
  font-size: 12px;
  color: #909399;
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
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
  border-bottom: 1px solid #f0f2f5;
}

.weight-row:last-child {
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
  color: #c0c4cc;
}

.weight-used {
  font-weight: 600;
}

.route-section {
  padding: 12px 0;
  border-bottom: 1px solid #f0f2f5;
}

.route-section:last-child {
  border-bottom: none;
  padding-bottom: 0;
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
  gap: 6px;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 10px;
}

.sample-title {
  color: #303133;
  font-weight: 500;
  text-decoration: none;
}

.sample-title:hover {
  color: #409eff;
}

.sample-score {
  font-family: monospace;
  color: #606266;
}

.sample-meta,
.preview-breakdown {
  font-size: 12px;
  color: #909399;
}

.sample-alt {
  color: #909399;
}

.route-count {
  font-size: 12px;
  color: #909399;
}
</style>
