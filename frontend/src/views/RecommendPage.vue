<template>
  <div class="recommend-page">
    <el-card class="control-panel">
      <template #header>
        <div class="panel-title">
          <el-icon><Star /></el-icon>
          <span>智能推荐</span>
        </div>
      </template>

      <el-form label-width="80px">
        <el-form-item label="当前用户">
          <span class="current-user">{{ authStore.username }} (ID: {{ authStore.userId }})</span>
        </el-form-item>

        <el-form-item label="融合权重">
          <WeightSlider @update:weights="onWeightsChange" />
        </el-form-item>

        <el-form-item label="推荐数量">
          <el-input-number v-model="topN" :min="5" :max="50" :step="5" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="fetchRecommendations">
            <el-icon><Search /></el-icon>
            获取推荐
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-if="loading" class="loading-area">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>正在计算推荐（三路融合 + LLM），请稍候...</p>
    </div>

    <div v-else-if="recommendations.length" class="result-area">
      <div class="result-header">
        <span>为你推荐了 {{ recommendations.length }} 篇文章</span>
      </div>
      <RecCard
        v-for="item in recommendations"
        :key="item.post_id"
        :item="item"
        @show-reason="openReason"
      />
    </div>

    <el-empty v-else-if="searched" description="暂无推荐结果" />

    <RecReasonDialog
      v-model="reasonDialogVisible"
      :user-id="authStore.userId"
      :post-id="reasonPostId"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getMyRecommendations } from '../api/recommendation'
import { useAuthStore } from '../stores/auth'
import WeightSlider from '../components/recommend/WeightSlider.vue'
import RecCard from '../components/recommend/RecCard.vue'
import RecReasonDialog from '../components/recommend/RecReasonDialog.vue'

const authStore = useAuthStore()

const topN = ref(20)
const weights = ref({ cf: 0.35, graph: 0.35, semantic: 0.30 })
const loading = ref(false)
const searched = ref(false)
const recommendations = ref([])

const reasonDialogVisible = ref(false)
const reasonPostId = ref(null)

function onWeightsChange(w) {
  weights.value = w
}

async function fetchRecommendations() {
  loading.value = true
  searched.value = true
  try {
    const data = await getMyRecommendations({
      topN: topN.value,
      enableLlm: true,
      weights: weights.value,
    })
    recommendations.value = data.recommendations || []
  } catch {
    recommendations.value = []
  } finally {
    loading.value = false
  }
}

function openReason(postId) {
  reasonPostId.value = postId
  reasonDialogVisible.value = true
}
</script>

<style scoped>
.recommend-page {
  max-width: 900px;
  margin: 0 auto;
}

.control-panel {
  margin-bottom: 20px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
}

.current-user {
  font-size: 14px;
  color: #409eff;
  font-weight: 500;
}

.loading-area {
  text-align: center;
  padding: 60px 0;
  color: #909399;
}

.loading-area p {
  margin-top: 12px;
  font-size: 14px;
}

.result-header {
  margin-bottom: 16px;
  font-size: 14px;
  color: #606266;
}
</style>
