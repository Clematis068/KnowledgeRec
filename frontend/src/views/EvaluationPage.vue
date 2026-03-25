<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getEvaluationReports } from '../api/evaluation'

echarts.use([
  BarChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const DATASET_OPTIONS = [
  { label: 'Epinions / knowledge_community', value: 'epinions' },
  { label: 'knowledge_community_old', value: 'knowledge_community_old' },
]

const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#fc8452']

const loading = ref(true)
const data = ref({})
const activeTab = ref('ablation')
const selectedDataset = ref('epinions')

const ablationChartRef = ref(null)
const interestChartRef = ref(null)
const behaviorChartRef = ref(null)
const stageChartRef = ref(null)
const stratifiedChartRef = ref(null)
const coldStartPureChartRef = ref(null)

const charts = []

const empty = computed(() =>
  !loading.value
  && !data.value.ablation
  && !data.value.stratified
  && !data.value.coldstart_pure
  && !data.value.interest
  && !data.value.behavior
  && !data.value.stages,
)

function fmt(v) {
  if (v == null) return '-'
  return typeof v === 'number' ? v.toFixed(4) : v
}

function baseOption(title) {
  return {
    title: { text: title, left: 'center', textStyle: { fontSize: 15, fontWeight: 600 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 32 },
    grid: { top: 80, left: 60, right: 30, bottom: 40, containLabel: true },
  }
}

function initChart(el, option) {
  const chart = echarts.init(el)
  chart.setOption(option)
  charts.push(chart)
  return chart
}

function disposeCharts() {
  charts.splice(0).forEach((chart) => chart.dispose())
}

function buildAblationChart(el, rows) {
  const k10Rows = rows.filter((row) => row.k === 10)
  const configs = k10Rows.map((row) => row.config)
  return initChart(el, {
    ...baseOption('消融实验 — Precision / Recall / NDCG @10'),
    xAxis: { type: 'category', data: configs, axisLabel: { rotate: 35, fontSize: 11 } },
    yAxis: { type: 'value', name: '指标值' },
    series: [
      { name: 'P@10', type: 'bar', data: k10Rows.map((row) => row.precision), color: COLORS[0] },
      { name: 'R@10', type: 'bar', data: k10Rows.map((row) => row.recall), color: COLORS[1] },
      { name: 'NDCG@10', type: 'bar', data: k10Rows.map((row) => row.ndcg), color: COLORS[2] },
    ],
  })
}

function buildInterestChart(el, rows) {
  const k10Rows = rows.filter((row) => row.k === 10)
  const configs = k10Rows.map((row) => row.config)
  const metrics = ['precision', 'recall', 'hit_rate', 'interest_tag_recall']
  const labels = ['P@10', 'R@10', 'HR@10', 'TagRecall@10']
  return initChart(el, {
    ...baseOption('兴趣对齐指标 @10'),
    xAxis: { type: 'category', data: configs },
    yAxis: { type: 'value', name: '指标值' },
    series: metrics.map((metric, index) => ({
      name: labels[index],
      type: 'bar',
      data: k10Rows.map((row) => row[metric]),
      color: COLORS[index],
    })),
  })
}

function buildBehaviorChart(el, rows) {
  const k10Rows = rows.filter((row) => row.k === 10)
  const configs = k10Rows.map((row) => row.config)
  const metrics = ['behavior_ndcg', 'behavior_align', 'behavior_tag_recall', 'behavior_domain_recall']
  const labels = ['NDCG@10', 'Align@10', 'BTag@10', 'BDom@10']
  return initChart(el, {
    ...baseOption('行为影响指标 @10'),
    xAxis: { type: 'category', data: configs },
    yAxis: { type: 'value', name: '指标值' },
    series: metrics.map((metric, index) => ({
      name: labels[index],
      type: 'bar',
      data: k10Rows.map((row) => row[metric]),
      color: COLORS[index],
    })),
  })
}

function buildStageChart(el, rows) {
  const stageOrder = ['cold', 'warm', 'active']
  const sorted = stageOrder
    .filter((stage) => rows.find((row) => row.stage === stage))
    .map((stage) => rows.find((row) => row.stage === stage))
  const stages = sorted.map((row) => `${row.stage} (${row.users}人)`)
  const channels = ['cf', 'swing', 'graph', 'semantic', 'knowledge', 'hot']
  const labels = ['CF', 'Swing', 'Graph', 'Semantic', 'Knowledge', 'Hot']
  return initChart(el, {
    ...baseOption('用户阶段权重分布（堆叠）'),
    xAxis: { type: 'category', data: stages },
    yAxis: { type: 'value', name: '权重', max: 1 },
    series: channels.map((channel, index) => ({
      name: labels[index],
      type: 'bar',
      stack: 'weight',
      data: sorted.map((row) => row[channel]),
      color: COLORS[index % COLORS.length],
    })),
  })
}

function buildStratifiedChart(el, rows) {
  const k10Rows = rows.filter((row) => row.k === 10)
  const targetConfigs = ['CF_only', 'Semantic_only', 'Knowledge_only', 'Full_Fusion', 'GBDT_Ranking']
  const filtered = k10Rows.filter((row) => row.stage === 'cold' && targetConfigs.includes(row.config))
  return initChart(el, {
    ...baseOption('冷 / 温 / 活跃分层（Cold 用户 HR@10）'),
    xAxis: { type: 'category', data: filtered.map((row) => row.config), axisLabel: { rotate: 20 } },
    yAxis: { type: 'value', name: 'HR@10', max: 1 },
    series: [
      { name: 'Cold HR@10', type: 'bar', data: filtered.map((row) => row.hitrate), color: COLORS[3] },
    ],
  })
}

function buildColdStartPureChart(el, rows) {
  const k10Rows = rows.filter((row) => row.k === 10)
  return initChart(el, {
    ...baseOption('纯冷启动评估 @10'),
    xAxis: { type: 'category', data: k10Rows.map((row) => row.config), axisLabel: { rotate: 25 } },
    yAxis: { type: 'value', name: '指标值' },
    series: [
      { name: 'P@10', type: 'bar', data: k10Rows.map((row) => row.precision), color: COLORS[0] },
      { name: 'R@10', type: 'bar', data: k10Rows.map((row) => row.recall), color: COLORS[1] },
      { name: 'HR@10', type: 'bar', data: k10Rows.map((row) => row.hitrate), color: COLORS[2] },
      { name: 'NDCG@10', type: 'bar', data: k10Rows.map((row) => row.ndcg), color: COLORS[4] },
    ],
  })
}

async function renderCharts() {
  await nextTick()
  disposeCharts()

  if (data.value.ablation && ablationChartRef.value) {
    buildAblationChart(ablationChartRef.value, data.value.ablation)
  }
  if (data.value.stratified && stratifiedChartRef.value) {
    buildStratifiedChart(stratifiedChartRef.value, data.value.stratified)
  }
  if (data.value.coldstart_pure && coldStartPureChartRef.value) {
    buildColdStartPureChart(coldStartPureChartRef.value, data.value.coldstart_pure)
  }
  if (data.value.interest && interestChartRef.value) {
    buildInterestChart(interestChartRef.value, data.value.interest)
  }
  if (data.value.behavior && behaviorChartRef.value) {
    buildBehaviorChart(behaviorChartRef.value, data.value.behavior)
  }
  if (data.value.stages && stageChartRef.value) {
    buildStageChart(stageChartRef.value, data.value.stages)
  }
}

function handleResize() {
  charts.forEach((chart) => chart.resize())
}

async function loadReports() {
  loading.value = true
  try {
    const response = await getEvaluationReports(selectedDataset.value)
    data.value = response
    const availableTabs = [
      data.value.ablation && 'ablation',
      (data.value.stratified || data.value.coldstart_pure || data.value.interest || data.value.behavior) && 'coldstart',
      data.value.stages && 'stages',
    ].filter(Boolean)
    activeTab.value = availableTabs[0] || 'ablation'
    await renderCharts()
  } finally {
    loading.value = false
  }
}

watch(selectedDataset, () => {
  loadReports()
})

window.addEventListener('resize', handleResize)
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})

loadReports()
</script>

<template>
  <div class="evaluation-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">实验评估</h1>
        <p class="page-subtitle">按数据集分别查看消融、分层和冷启动评估结果。</p>
      </div>
      <div class="toolbar">
        <span class="toolbar-label">数据集</span>
        <el-segmented v-model="selectedDataset" :options="DATASET_OPTIONS" />
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" :size="28"><Loading /></el-icon>
      <span>加载评估数据…</span>
    </div>

    <div v-else-if="empty" class="empty-state">
      <p>当前数据集暂无评估数据。</p>
      <el-text type="info" tag="code">
        cd backend && MYSQL_URI="mysql+pymysql://root@localhost:3306/knowledge_community" EVAL_REPORT_DIR="reports/evaluation_epinions" uv run python -m scripts.evaluate
      </el-text>
      <br />
      <el-text type="info" tag="code">
        cd backend && MYSQL_URI="mysql+pymysql://root@localhost:3306/knowledge_community_old" EVAL_REPORT_DIR="reports/evaluation_old_dataset" uv run python -m scripts.evaluate
      </el-text>
    </div>

    <div v-else class="report-shell">
      <div class="report-meta">
        <span>当前目录：{{ data.report_dir || '-' }}</span>
      </div>

      <el-tabs v-model="activeTab" class="eval-tabs">
        <el-tab-pane label="消融实验" name="ablation" v-if="data.ablation">
          <div ref="ablationChartRef" class="chart-box"></div>
          <el-table :data="data.ablation" stripe class="eval-table" size="small">
            <el-table-column prop="config" label="配置" width="180" />
            <el-table-column prop="k" label="K" width="60" />
            <el-table-column prop="precision" label="P@K" width="110">
              <template #default="{ row }">{{ fmt(row.precision) }}</template>
            </el-table-column>
            <el-table-column prop="recall" label="R@K" width="110">
              <template #default="{ row }">{{ fmt(row.recall) }}</template>
            </el-table-column>
            <el-table-column prop="ndcg" label="NDCG@K" width="120">
              <template #default="{ row }">{{ fmt(row.ndcg) }}</template>
            </el-table-column>
            <el-table-column prop="hitrate" label="HR@K" width="110">
              <template #default="{ row }">{{ fmt(row.hitrate) }}</template>
            </el-table-column>
            <el-table-column prop="coverage" label="Coverage" width="110">
              <template #default="{ row }">{{ fmt(row.coverage) }}</template>
            </el-table-column>
            <el-table-column prop="entropy" label="Entropy" width="110">
              <template #default="{ row }">{{ fmt(row.entropy) }}</template>
            </el-table-column>
            <el-table-column prop="ils" label="ILS" width="100">
              <template #default="{ row }">{{ fmt(row.ils) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane
          label="冷启动 / 分层"
          name="coldstart"
          v-if="data.stratified || data.coldstart_pure || data.interest || data.behavior"
        >
          <template v-if="data.stratified">
            <h3 class="section-title">主评估分层结果</h3>
            <div ref="stratifiedChartRef" class="chart-box"></div>
            <el-table :data="data.stratified" stripe class="eval-table" size="small">
              <el-table-column prop="config" label="配置" width="170" />
              <el-table-column prop="k" label="K" width="60" />
              <el-table-column prop="stage" label="阶段" width="100" />
              <el-table-column prop="n_users" label="用户数" width="100" />
              <el-table-column prop="precision" label="P@K" width="110">
                <template #default="{ row }">{{ fmt(row.precision) }}</template>
              </el-table-column>
              <el-table-column prop="ndcg" label="NDCG@K" width="120">
                <template #default="{ row }">{{ fmt(row.ndcg) }}</template>
              </el-table-column>
              <el-table-column prop="hitrate" label="HR@K" width="110">
                <template #default="{ row }">{{ fmt(row.hitrate) }}</template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="data.coldstart_pure">
            <h3 class="section-title">纯冷启动用户评估</h3>
            <div ref="coldStartPureChartRef" class="chart-box"></div>
            <el-table :data="data.coldstart_pure" stripe class="eval-table" size="small">
              <el-table-column prop="config" label="配置" width="170" />
              <el-table-column prop="k" label="K" width="60" />
              <el-table-column prop="precision" label="P@K" width="110">
                <template #default="{ row }">{{ fmt(row.precision) }}</template>
              </el-table-column>
              <el-table-column prop="recall" label="R@K" width="110">
                <template #default="{ row }">{{ fmt(row.recall) }}</template>
              </el-table-column>
              <el-table-column prop="ndcg" label="NDCG@K" width="120">
                <template #default="{ row }">{{ fmt(row.ndcg) }}</template>
              </el-table-column>
              <el-table-column prop="hitrate" label="HR@K" width="110">
                <template #default="{ row }">{{ fmt(row.hitrate) }}</template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="data.interest">
            <h3 class="section-title">兴趣对齐指标</h3>
            <div ref="interestChartRef" class="chart-box"></div>
            <el-table :data="data.interest" stripe class="eval-table" size="small">
              <el-table-column prop="config" label="配置" width="140" />
              <el-table-column prop="k" label="K" width="60" />
              <el-table-column prop="precision" label="P@K">
                <template #default="{ row }">{{ fmt(row.precision) }}</template>
              </el-table-column>
              <el-table-column prop="recall" label="R@K">
                <template #default="{ row }">{{ fmt(row.recall) }}</template>
              </el-table-column>
              <el-table-column prop="hit_rate" label="HR@K">
                <template #default="{ row }">{{ fmt(row.hit_rate) }}</template>
              </el-table-column>
              <el-table-column prop="interest_tag_recall" label="TagRecall@K">
                <template #default="{ row }">{{ fmt(row.interest_tag_recall) }}</template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="data.behavior">
            <h3 class="section-title">行为影响指标</h3>
            <div ref="behaviorChartRef" class="chart-box"></div>
            <el-table :data="data.behavior" stripe class="eval-table" size="small">
              <el-table-column prop="config" label="配置" width="140" />
              <el-table-column prop="k" label="K" width="60" />
              <el-table-column prop="behavior_ndcg" label="BehaviorNDCG@K">
                <template #default="{ row }">{{ fmt(row.behavior_ndcg) }}</template>
              </el-table-column>
              <el-table-column prop="behavior_align" label="BehaviorAlign@K">
                <template #default="{ row }">{{ fmt(row.behavior_align) }}</template>
              </el-table-column>
              <el-table-column prop="behavior_tag_recall" label="BTagRecall@K">
                <template #default="{ row }">{{ fmt(row.behavior_tag_recall) }}</template>
              </el-table-column>
              <el-table-column prop="behavior_domain_recall" label="BDomRecall@K">
                <template #default="{ row }">{{ fmt(row.behavior_domain_recall) }}</template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>

        <el-tab-pane label="阶段权重" name="stages" v-if="data.stages">
          <div ref="stageChartRef" class="chart-box"></div>
          <el-table :data="data.stages" stripe class="eval-table" size="small">
            <el-table-column prop="stage" label="阶段" width="100" />
            <el-table-column prop="users" label="用户数" width="80" />
            <el-table-column prop="avg_behavior_count" label="平均行为数" width="110">
              <template #default="{ row }">{{ fmt(row.avg_behavior_count) }}</template>
            </el-table-column>
            <el-table-column prop="cf" label="CF">
              <template #default="{ row }">{{ fmt(row.cf) }}</template>
            </el-table-column>
            <el-table-column prop="swing" label="Swing">
              <template #default="{ row }">{{ fmt(row.swing) }}</template>
            </el-table-column>
            <el-table-column prop="graph" label="Graph">
              <template #default="{ row }">{{ fmt(row.graph) }}</template>
            </el-table-column>
            <el-table-column prop="semantic" label="Semantic">
              <template #default="{ row }">{{ fmt(row.semantic) }}</template>
            </el-table-column>
            <el-table-column prop="knowledge" label="Knowledge">
              <template #default="{ row }">{{ fmt(row.knowledge) }}</template>
            </el-table-column>
            <el-table-column prop="hot" label="Hot">
              <template #default="{ row }">{{ fmt(row.hot) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.evaluation-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-end;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.page-title {
  font-size: clamp(2rem, 3vw, 3rem);
  font-weight: 800;
  letter-spacing: -0.05em;
  margin: 0;
}

.page-subtitle {
  margin: 8px 0 0;
  color: var(--kr-text-muted, #7b7f87);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-label {
  font-size: 13px;
  color: var(--kr-text-muted, #7b7f87);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--kr-text-muted, #999);
}

.report-shell {
  margin-top: 8px;
}

.report-meta {
  margin-bottom: 12px;
  color: var(--kr-text-muted, #7b7f87);
  font-size: 13px;
}

.eval-tabs {
  margin-top: 8px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 24px 0 8px;
}

.chart-box {
  width: 100%;
  height: 400px;
  margin-bottom: 24px;
}

.eval-table {
  margin-bottom: 32px;
}

@media (max-width: 768px) {
  .evaluation-page {
    padding: 24px 16px 48px;
  }

  .toolbar {
    width: 100%;
    align-items: flex-start;
    flex-direction: column;
  }

  .chart-box {
    height: 320px;
  }
}
</style>
