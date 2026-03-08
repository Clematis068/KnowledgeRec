<template>
  <div class="recommend-page">
    <!-- 顶部栏：标题 + 调参折叠面板 + 刷新按钮 -->
    <div class="page-header">
      <div class="header-left">
        <el-icon :size="20"><Star /></el-icon>
        <span class="header-title">为你推荐</span>
        <el-tag size="small" type="info">{{ authStore.username }}</el-tag>
      </div>
      <div class="header-right">
        <el-button text :icon="Operation" @click="showSettings = !showSettings">
          调参
        </el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="fetchRecommendations">
          换一批
        </el-button>
      </div>
    </div>

    <!-- 可折叠的调参面板 -->
    <el-card v-show="showSettings" class="settings-panel">
      <el-form :inline="true" size="small">
        <el-form-item label="融合权重">
          <WeightSlider @update:weights="onWeightsChange" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="topN" :min="5" :max="50" :step="5" />
        </el-form-item>
        <el-form-item label="LLM重排">
          <el-switch v-model="enableLlm" active-text="开" inactive-text="关" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-area">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>正在为你计算个性化推荐...</p>
    </div>

    <!-- 推荐结果列表 -->
    <div v-else-if="recommendations.length" class="result-area">
      <RecCard
        v-for="item in recommendations"
        :key="item.post_id"
        :item="item"
        @show-reason="openReason"
      />
    </div>

    <el-empty v-else description="暂无推荐结果，试试调整参数" />

    <RecReasonDialog
      v-model="reasonDialogVisible"
      :user-id="authStore.userId"
      :post-id="reasonPostId"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh, Operation } from '@element-plus/icons-vue'
import { getMyRecommendations } from '../api/recommendation'
import { useAuthStore } from '../stores/auth'
import WeightSlider from '../components/recommend/WeightSlider.vue'
import RecCard from '../components/recommend/RecCard.vue'
import RecReasonDialog from '../components/recommend/RecReasonDialog.vue'

const authStore = useAuthStore()

const topN = ref(20)
const weights = ref({ cf: 0.35, graph: 0.35, semantic: 0.30 })
const loading = ref(false)
const recommendations = ref([])
const showSettings = ref(false)
const enableLlm = ref(false)

const reasonDialogVisible = ref(false)
const reasonPostId = ref(null)

function onWeightsChange(w) {
  weights.value = w
}

async function fetchRecommendations() {
  loading.value = true
  try {
    const data = await getMyRecommendations({
      topN: topN.value,
      enableLlm: enableLlm.value,
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

// 进入页面自动加载推荐
onMounted(() => {
  fetchRecommendations()
})
</script>

<style scoped>
.recommend-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 12px 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #303133;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.settings-panel {
  margin-bottom: 16px;
}

.loading-area {
  text-align: center;
  padding: 80px 0;
  color: #909399;
}

.loading-area p {
  margin-top: 12px;
  font-size: 14px;
}
</style>
