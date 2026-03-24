<template>
  <div class="evaluation-page">
    <h1 class="page-title">实验评估</h1>

    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" :size="28"><Loading /></el-icon>
      <span>加载评估数据…</span>
    </div>

    <div v-else-if="empty" class="empty-state">
      <p>暂无评估数据。请先运行评估脚本生成报告：</p>
      <el-text type="info" tag="code">cd backend && uv run python -m scripts.evaluate</el-text>
      <br />
      <el-text type="info" tag="code">cd backend && uv run python -m scripts.evaluate_cold_start</el-text>
    </div>

    <el-tabs v-else v-model="activeTab" class="eval-tabs">
      <!-- Tab 1: 消融实验 -->
      <el-tab-pane label="消融实验" name="ablation" v-if="data.ablation">
        <div ref="ablationChartRef" class="chart-box"></div>
        <el-table :data="data.ablation" stripe class="eval-table" size="small">
          <el-table-column prop="config" label="配置" width="160" />
          <el-table-column prop="k" label="K" width="60" />
          <el-table-column prop="precision" label="P@K" width="120">
            <template #default="{ row }">{{ fmt(row.precision) }}</template>
          </el-table-column>
          <el-table-column prop="recall" label="R@K" width="120">
            <template #default="{ row }">{{ fmt(row.recall) }}</template>
          </el-table-column>
          <el-table-column prop="ndcg" label="NDCG@K" width="120">
            <template #default="{ row }">{{ fmt(row.ndcg) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 2: 冷启动 / 成长评估 -->
      <el-tab-pane label="冷启动 / 成长" name="coldstart" v-if="data.interest || data.behavior">
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

      <!-- Tab 3: 用户阶段权重分析 -->
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
          <el-table-column prop="hot" label="Hot">
            <template #default="{ row }">{{ fmt(row.hot) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

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

const loading = ref(true)
const data = ref({})
const activeTab = ref('ablation')

const ablationChartRef = ref(null)
const interestChartRef = ref(null)
const behaviorChartRef = ref(null)
const stageChartRef = ref(null)

const charts = []

const empty = computed(() =>
  !loading.value && !data.value.ablation && !data.value.interest && !data.value.behavior && !data.value.stages,
)

function fmt(v) {
  if (v == null) return '-'
  return typeof v === 'number' ? v.toFixed(4) : v
}

// ─── 图表配置 ───

const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#fc8452']

function baseOption(title) {
  return {
    title: { text: title, left: 'center', textStyle: { fontSize: 15, fontWeight: 600 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 32 },
    grid: { top: 80, left: 60, right: 30, bottom: 40, containLabel: true },
  }
}

function buildAblationChart(el, rows) {
  const k10Rows = rows.filter((r) => r.k === 10)
  const configs = k10Rows.map((r) => r.config)
  const option = {
    ...baseOption('消融实验 — Precision / Recall / NDCG @10'),
    xAxis: { type: 'category', data: configs, axisLabel: { rotate: 35, fontSize: 11 } },
    yAxis: { type: 'value', name: '指标值' },
    series: [
      { name: 'P@10', type: 'bar', data: k10Rows.map((r) => r.precision), color: COLORS[0] },
      { name: 'R@10', type: 'bar', data: k10Rows.map((r) => r.recall), color: COLORS[1] },
      { name: 'NDCG@10', type: 'bar', data: k10Rows.map((r) => r.ndcg), color: COLORS[2] },
    ],
  }
  return initChart(el, option)
}

function buildInterestChart(el, rows) {
  const k10Rows = rows.filter((r) => r.k === 10)
  const configs = k10Rows.map((r) => r.config)
  const metrics = ['precision', 'recall', 'hit_rate', 'interest_tag_recall']
  const labels = ['P@10', 'R@10', 'HR@10', 'TagRecall@10']
  const option = {
    ...baseOption('兴趣对齐指标 @10'),
    xAxis: { type: 'category', data: configs },
    yAxis: { type: 'value', name: '指标值' },
    series: metrics.map((m, i) => ({
      name: labels[i],
      type: 'bar',
      data: k10Rows.map((r) => r[m]),
      color: COLORS[i],
    })),
  }
  return initChart(el, option)
}

function buildBehaviorChart(el, rows) {
  const k10Rows = rows.filter((r) => r.k === 10)
  const configs = k10Rows.map((r) => r.config)
  const metrics = ['behavior_ndcg', 'behavior_align', 'behavior_tag_recall', 'behavior_domain_recall']
  const labels = ['NDCG@10', 'Align@10', 'BTag@10', 'BDom@10']
  const option = {
    ...baseOption('行为影响指标 @10'),
    xAxis: { type: 'category', data: configs },
    yAxis: { type: 'value', name: '指标值' },
    series: metrics.map((m, i) => ({
      name: labels[i],
      type: 'bar',
      data: k10Rows.map((r) => r[m]),
      color: COLORS[i],
    })),
  }
  return initChart(el, option)
}

function buildStageChart(el, rows) {
  const stageOrder = ['cold', 'warm', 'active']
  const sorted = stageOrder.filter((s) => rows.find((r) => r.stage === s)).map((s) => rows.find((r) => r.stage === s))
  const stages = sorted.map((r) => `${r.stage} (${r.users}人)`)
  const channels = ['cf', 'swing', 'graph', 'semantic', 'knowledge', 'hot']
  const channelLabels = ['CF', 'Swing', 'Graph', 'Semantic', 'Knowledge', 'Hot']
  const option = {
    ...baseOption('用户阶段权重分布（堆叠）'),
    xAxis: { type: 'category', data: stages },
    yAxis: { type: 'value', name: '权重', max: 1 },
    series: channels.map((ch, i) => ({
      name: channelLabels[i],
      type: 'bar',
      stack: 'weight',
      data: sorted.map((r) => r[ch]),
      color: COLORS[i % COLORS.length],
    })),
  }
  return initChart(el, option)
}

function initChart(el, option) {
  const chart = echarts.init(el)
  chart.setOption(option)
  charts.push(chart)
  return chart
}

function handleResize() {
  charts.forEach((c) => c.resize())
}

// ─── 渲染逻辑 ───

async function renderCharts() {
  await nextTick()
  if (data.value.ablation && ablationChartRef.value) {
    buildAblationChart(ablationChartRef.value, data.value.ablation)
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

watch(activeTab, async () => {
  await nextTick()
  // 切换 tab 后重新渲染当前 tab 的图表
  if (activeTab.value === 'ablation' && data.value.ablation && ablationChartRef.value) {
    if (!ablationChartRef.value.__rendered) {
      buildAblationChart(ablationChartRef.value, data.value.ablation)
      ablationChartRef.value.__rendered = true
    } else {
      handleResize()
    }
  }
  if (activeTab.value === 'coldstart') {
    if (data.value.interest && interestChartRef.value && !interestChartRef.value.__rendered) {
      buildInterestChart(interestChartRef.value, data.value.interest)
      interestChartRef.value.__rendered = true
    }
    if (data.value.behavior && behaviorChartRef.value && !behaviorChartRef.value.__rendered) {
      buildBehaviorChart(behaviorChartRef.value, data.value.behavior)
      behaviorChartRef.value.__rendered = true
    }
    handleResize()
  }
  if (activeTab.value === 'stages' && data.value.stages && stageChartRef.value) {
    if (!stageChartRef.value.__rendered) {
      buildStageChart(stageChartRef.value, data.value.stages)
      stageChartRef.value.__rendered = true
    } else {
      handleResize()
    }
  }
})

// ─── 生命周期 ───

getEvaluationReports()
  .then((res) => {
    data.value = res
    loading.value = false
    nextTick(() => renderCharts())
  })
  .catch(() => {
    loading.value = false
  })

window.addEventListener('resize', handleResize)
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  charts.forEach((c) => c.dispose())
})
</script>

<style scoped>
.evaluation-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.page-title {
  font-size: clamp(2rem, 3vw, 3rem);
  font-weight: 800;
  letter-spacing: -0.05em;
  margin-bottom: 24px;
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
</style>
