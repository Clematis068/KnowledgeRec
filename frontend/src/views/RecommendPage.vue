<template>
  <div class="recommend-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon :size="20"><Star /></el-icon>
        <span class="header-title">社区首页</span>
        <el-tag size="small" type="info">
          {{ isOwnSelection ? '我的视角' : `演示用户 #${selectedUserId || '-'}` }}
        </el-tag>
      </div>
      <div class="header-right">
        <el-button
          text
          :icon="View"
          :disabled="activeFeed !== 'recommend'"
          @click="showDebugPanel = true"
        >
          Debug
        </el-button>
        <el-button text :icon="Operation" @click="showSettings = !showSettings">
          调参
        </el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="fetchCurrentFeed">
          刷新
        </el-button>
      </div>
    </div>

    <el-card v-show="showSettings" class="settings-panel">
      <el-form :inline="true" size="small">
        <el-form-item label="演示用户">
          <UserSelector v-model="selectedUserId" />
        </el-form-item>
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

    <el-tabs v-model="activeFeed" class="feed-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="推荐" name="recommend" />
      <el-tab-pane label="关注" name="following" />
      <el-tab-pane label="最新" name="latest" />
    </el-tabs>

    <div v-if="loading" class="loading-area">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>{{ loadingText }}</p>
    </div>

    <template v-else-if="activeFeed === 'recommend'">
      <div v-if="recommendations.length" class="result-area">
        <RecCard
          v-for="item in recommendations"
          :key="item.post_id"
          :item="item"
          :allow-feedback="isOwnSelection"
          @dislike="handleDislike"
          @show-reason="openReason"
        />
      </div>
      <el-empty v-else description="暂无推荐结果，试试调整参数或切换演示用户" />
    </template>

    <template v-else>
      <div v-if="feedPosts.length" class="result-area">
        <PostCard v-for="post in feedPosts" :key="post.id" :post="post" />
      </div>
      <el-empty
        v-else
        :description="activeFeed === 'following' ? '你还没有关注内容，先去逛逛用户页吧' : '暂无最新帖子'"
      />
    </template>

    <RecReasonDialog
      v-model="reasonDialogVisible"
      :user-id="selectedUserId || authStore.userId"
      :post-id="reasonPostId"
    />
    <RecommendDebugPanel v-model:visible="showDebugPanel" :debug="recommendDebug" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Refresh, Operation, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getRecommendations, getMyRecommendations } from '../api/recommendation'
import { getFollowingPosts, getPostList, recordBehavior } from '../api/post'
import { useAuthStore } from '../stores/auth'
import WeightSlider from '../components/recommend/WeightSlider.vue'
import UserSelector from '../components/recommend/UserSelector.vue'
import RecCard from '../components/recommend/RecCard.vue'
import RecReasonDialog from '../components/recommend/RecReasonDialog.vue'
import RecommendDebugPanel from '../components/recommend/RecommendDebugPanel.vue'
import PostCard from '../components/post/PostCard.vue'

const authStore = useAuthStore()

const activeFeed = ref('recommend')
const topN = ref(20)
const weights = ref({ cf: 0.35, graph: 0.35, semantic: 0.30 })
const loading = ref(false)
const loadingText = ref('正在加载内容...')
const showSettings = ref(false)
const showDebugPanel = ref(false)
const enableLlm = ref(false)
const selectedUserId = ref(null)

const recommendations = ref([])
const recommendDebug = ref(null)
const followingPosts = ref([])
const latestPosts = ref([])

const reasonDialogVisible = ref(false)
const reasonPostId = ref(null)

const isOwnSelection = computed(() => selectedUserId.value === authStore.userId)
const feedPosts = computed(() => (
  activeFeed.value === 'following' ? followingPosts.value : latestPosts.value
))

function onWeightsChange(value) {
  weights.value = value
}

async function fetchRecommendations() {
  if (!selectedUserId.value) return

  loadingText.value = isOwnSelection.value
    ? '正在为你计算个性化推荐...'
    : `正在生成用户 #${selectedUserId.value} 的推荐结果...`
  loading.value = true

  try {
    const data = isOwnSelection.value
      ? await getMyRecommendations({
        topN: topN.value,
        enableLlm: enableLlm.value,
        weights: weights.value,
        debug: true,
      })
      : await getRecommendations(selectedUserId.value, {
        topN: topN.value,
        enableLlm: enableLlm.value,
        weights: weights.value,
        debug: true,
      })

    recommendations.value = data.recommendations || []
    recommendDebug.value = data.debug || null
  } catch {
    recommendations.value = []
    recommendDebug.value = null
  } finally {
    loading.value = false
  }
}

async function fetchFollowingFeed() {
  loadingText.value = '正在加载关注内容...'
  loading.value = true

  try {
    const data = await getFollowingPosts(1, 20)
    followingPosts.value = data.posts || []
  } catch {
    followingPosts.value = []
  } finally {
    loading.value = false
  }
}

async function fetchLatestFeed() {
  loadingText.value = '正在加载最新帖子...'
  loading.value = true

  try {
    const data = await getPostList(1, 20)
    latestPosts.value = data.posts || []
  } catch {
    latestPosts.value = []
  } finally {
    loading.value = false
  }
}

function fetchCurrentFeed() {
  if (activeFeed.value === 'recommend') {
    return fetchRecommendations()
  }
  if (activeFeed.value === 'following') {
    return fetchFollowingFeed()
  }
  return fetchLatestFeed()
}

function handleTabChange() {
  fetchCurrentFeed()
}

function openReason(postId) {
  reasonPostId.value = postId
  reasonDialogVisible.value = true
}

async function handleDislike(postId) {
  try {
    await recordBehavior(postId, 'dislike')
    recommendations.value = recommendations.value.filter((item) => item.post_id !== postId)
    ElMessage.success('已减少这类内容推荐')
  } catch {
    // 错误已由拦截器处理
  }
}

watch(selectedUserId, (userId, previousUserId) => {
  if (!userId || previousUserId == null || userId === previousUserId || activeFeed.value !== 'recommend') return
  fetchRecommendations()
})

onMounted(() => {
  selectedUserId.value = authStore.userId
  fetchCurrentFeed()
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

.feed-tabs {
  margin-bottom: 12px;
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

.result-area {
  min-height: 180px;
}
</style>
