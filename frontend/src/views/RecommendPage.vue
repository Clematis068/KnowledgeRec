<template>
  <div class="recommend-page">
    <section class="hero-section">
      <div class="hero-copy">
        <span class="hero-kicker">Recommend</span>
        <h1>社区首页</h1>
        <p>{{ heroDescription }}</p>

        <div class="hero-stats">
          <article class="stat-card">
            <strong>{{ recommendations.length }}</strong>
            <span>推荐</span>
          </article>
          <article class="stat-card">
            <strong>{{ followingPosts.length }}</strong>
            <span>关注</span>
          </article>
          <article class="stat-card">
            <strong>{{ latestPosts.length }}</strong>
            <span>最新</span>
          </article>
        </div>
      </div>

      <div class="hero-side">
        <div class="hero-note">
          <span class="note-label">Mode</span>
          <h3>{{ currentFeedTitle }}</h3>
          <p>{{ currentFeedDescription }}</p>
        </div>
        <div class="hero-actions">
          <el-button type="primary" :icon="Refresh" :loading="loading" @click="fetchCurrentFeed">
            刷新
          </el-button>
          <el-button
            text
            :icon="View"
            :disabled="activeFeed !== 'recommend'"
            @click="showDebugPanel = true"
          >
            Debug 面板
          </el-button>
        </div>
      </div>
    </section>

    <div class="recommend-shell">
      <section class="feed-column">
        <div class="toolbar-card">
          <div>
            <span class="toolbar-kicker">Feed</span>
            <h2>内容流</h2>
          </div>
          <el-tag size="small" effect="plain" class="selection-tag">我的视角</el-tag>
        </div>

        <div class="tabs-card">
          <el-tabs v-model="activeFeed" class="feed-tabs" @tab-change="handleTabChange">
            <el-tab-pane label="推荐" name="recommend" />
            <el-tab-pane label="关注" name="following" />
            <el-tab-pane label="最新" name="latest" />
          </el-tabs>
        </div>

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
          <el-empty v-else description="暂无推荐结果" />
        </template>

        <template v-else>
          <div v-if="feedPosts.length" class="result-area">
            <PostCard v-for="post in feedPosts" :key="post.id" :post="post" />
          </div>
          <el-empty
            v-else
            :description="activeFeed === 'following' ? '暂无关注内容' : '暂无最新帖子'"
          />
        </template>
      </section>

      <aside class="insight-column">
        <el-card class="insight-card" shadow="never">
          <span class="insight-kicker">Status</span>
          <h3>{{ currentFeedTitle }}</h3>
          <p>{{ currentFeedDescription }}</p>
          <div class="insight-pills">
            <span class="insight-pill">我的推荐</span>
            <span class="insight-pill">Top {{ topN }}</span>
          </div>
        </el-card>
      </aside>
    </div>

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
import { Refresh, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getRecommendations, getMyRecommendations } from '../api/recommendation'
import { getFollowingPosts, getPostList, recordBehavior } from '../api/post'
import { useAuthStore } from '../stores/auth'
import RecCard from '../components/recommend/RecCard.vue'
import RecReasonDialog from '../components/recommend/RecReasonDialog.vue'
import RecommendDebugPanel from '../components/recommend/RecommendDebugPanel.vue'
import PostCard from '../components/post/PostCard.vue'

const authStore = useAuthStore()

const activeFeed = ref('recommend')
const topN = ref(20)
const loading = ref(false)
const loadingText = ref('正在加载内容...')
const showDebugPanel = ref(false)
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

const heroDescription = computed(() => (
  authStore.username ? `${authStore.username}，这里是你的内容入口。` : '这里是社区内容入口。'
))

const currentFeedTitle = computed(() => {
  if (activeFeed.value === 'recommend') return '推荐流'
  if (activeFeed.value === 'following') return '关注流'
  return '最新流'
})

const currentFeedDescription = computed(() => {
  if (activeFeed.value === 'recommend') return '优先看最相关内容。'
  if (activeFeed.value === 'following') {
    return '只看你关注的更新。'
  }
  return '快速扫最新内容。'
})

async function fetchRecommendations() {
  if (!selectedUserId.value) return

  loadingText.value = '正在为你计算推荐...'
  loading.value = true

  try {
    const data = isOwnSelection.value
      ? await getMyRecommendations({
        topN: topN.value,
        debug: true,
      })
      : await getRecommendations(selectedUserId.value, {
        topN: topN.value,
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
  display: grid;
  gap: 20px;
}

.hero-section,
.toolbar-card,
.tabs-card {
  border: 1px solid rgba(124, 58, 237, 0.12);
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 18px 44px rgba(76, 29, 149, 0.08);
  backdrop-filter: blur(18px);
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  gap: 18px;
  padding: 28px;
}

.hero-kicker,
.toolbar-kicker,
.insight-kicker,
.note-label {
  display: inline-flex;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-primary);
}

.hero-copy h1,
.toolbar-card h2,
.insight-card h3,
.hero-note h3 {
  line-height: 1;
  letter-spacing: -0.05em;
}

.hero-copy h1 {
  font-size: clamp(2.8rem, 5vw, 4.2rem);
}

.hero-copy p,
.hero-note p,
.insight-card p {
  color: var(--kr-text-soft);
  line-height: 1.7;
}

.hero-copy p {
  margin-top: 14px;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 22px;
}

.stat-card,
.hero-note,
.insight-card {
  padding: 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(124, 58, 237, 0.08);
}

.stat-card strong {
  display: block;
  margin-bottom: 8px;
  font-size: 32px;
  line-height: 1;
  letter-spacing: -0.05em;
}

.stat-card span {
  color: var(--kr-text-soft);
}

.hero-side {
  display: grid;
  gap: 14px;
}

.hero-actions {
  display: grid;
  gap: 10px;
}

.recommend-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  align-items: start;
}

.feed-column,
.insight-column {
  min-width: 0;
}

.toolbar-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  padding: 22px 24px;
  margin-bottom: 14px;
}

.selection-tag {
  border-color: rgba(124, 58, 237, 0.12);
  color: var(--kr-primary-strong);
  background: rgba(124, 58, 237, 0.08);
}

.tabs-card {
  padding: 0 18px;
  margin-bottom: 14px;
}

.feed-tabs {
  margin-bottom: -1px;
}

.loading-area {
  display: grid;
  place-items: center;
  min-height: 240px;
  color: var(--kr-text-muted);
}

.loading-area p {
  margin-top: 12px;
}

.result-area {
  min-height: 180px;
}

.insight-column {
  position: sticky;
  top: 96px;
}

.insight-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.insight-pill {
  display: inline-flex;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--kr-primary-strong);
  background: rgba(124, 58, 237, 0.08);
}

@media (max-width: 1180px) {
  .hero-section,
  .recommend-shell {
    grid-template-columns: 1fr;
  }

  .insight-column {
    position: static;
  }
}

@media (max-width: 720px) {
  .hero-section,
  .toolbar-card {
    padding: 20px;
  }

  .hero-stats {
    grid-template-columns: 1fr;
  }

  .toolbar-card {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
