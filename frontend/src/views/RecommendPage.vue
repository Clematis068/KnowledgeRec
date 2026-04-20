<template>
  <div class="recommend-page">
    <div class="recommend-shell">
      <section class="feed-column">
        <header class="feed-toolbar">
          <div class="tabs-wrap">
            <el-tabs v-model="activeFeed" class="feed-tabs" @tab-change="handleTabChange">
              <el-tab-pane label="推荐" name="recommend" />
              <el-tab-pane label="关注" name="following" />
              <el-tab-pane label="最新" name="latest" />
            </el-tabs>
          </div>

          <div class="toolbar-actions">
            <span class="toolbar-pill">{{ activeFeedLabel }}</span>
            <span class="toolbar-pill">{{ activeFeedCount }} 条</span>
            <el-button class="toolbar-button toolbar-button--primary" type="primary" :icon="Refresh" :loading="currentLoading" @click="refreshCurrentFeed">
              刷新
            </el-button>
            <el-button
              v-if="isRecommendFeed"
              class="toolbar-button toolbar-button--text"
              text
              :icon="View"
              @click="openDebugPanel"
            >
              调试
            </el-button>
          </div>
        </header>

        <div v-if="currentLoading && isRecommendFeed" class="result-area">
          <RecCardSkeleton :count="4" />
        </div>
        <div v-else-if="currentLoading" class="loading-area">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <p class="loading-text">{{ loadingText }}</p>
        </div>

        <template v-else-if="isRecommendFeed">
          <div v-if="recommendations.length" class="result-area">
            <RecCard
              v-for="item in recommendations"
              :key="item.post_id"
              :item="item"
              :allow-feedback="isOwnSelection"
              @dislike="handleDislike"
              @show-reason="openReason"
            />

            <div v-if="hasMore" ref="loadMoreTrigger" class="load-more-trigger" aria-hidden="true"></div>

            <RecCardSkeleton v-if="loadingMore" :count="2" />
            <div v-else-if="!hasMore" class="feed-status">没有更多推荐了</div>
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

      <RecommendRightRail class="right-column" />
    </div>

    <RecReasonDialog
      v-model="reasonDialogVisible"
      :user-id="selectedUserId || authStore.userId"
      :post-id="reasonPostId"
      :rec-item="reasonItem"
    />
    <RecommendDebugPanel v-model:visible="showDebugPanel" :debug="recommendDebug" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Loading, Refresh, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index'
import { getFollowingPosts, getPostList, recordBehavior } from '../api/post'
import PostCard from '../components/post/PostCard.vue'
import RecCard from '../components/recommend/RecCard.vue'
import RecCardSkeleton from '../components/recommend/RecCardSkeleton.vue'
import RecommendDebugPanel from '../components/recommend/RecommendDebugPanel.vue'
import RecommendRightRail from '../components/recommend/RecommendRightRail.vue'
import RecReasonDialog from '../components/recommend/RecReasonDialog.vue'
import { useInfiniteRecommend } from '../composables/useInfiniteRecommend'
import { useAuthStore } from '../stores/auth'

const RECOMMEND_BATCH_SIZE = 20

const authStore = useAuthStore()

const activeFeed = ref('recommend')
const loading = ref(false)
const loadingText = ref('正在加载内容...')
const showDebugPanel = ref(false)
const selectedUserId = ref(null)
const loadMoreTrigger = ref(null)
const skipNextAutoLoad = ref(false)

const followingPosts = ref([])
const latestPosts = ref([])

const reasonDialogVisible = ref(false)
const reasonPostId = ref(null)
const reasonItem = ref(null)

const {
  recommendations,
  recommendDebug,
  loading: recommendLoading,
  loadingMore,
  hasMore,
  isOwnSelection,
  refreshRecommendations,
  advanceRecommendations,
  loadMoreRecommendations,
  removeRecommendation,
  loadDebugSnapshot,
} = useInfiniteRecommend({
  authStore,
  selectedUserId,
  batchSize: RECOMMEND_BATCH_SIZE,
  debug: false,
  enableLlm: false,
})

const isRecommendFeed = computed(() => activeFeed.value === 'recommend')
const feedPosts = computed(() => (
  activeFeed.value === 'following' ? followingPosts.value : latestPosts.value
))
const currentLoading = computed(() => (
  isRecommendFeed.value ? recommendLoading.value : loading.value
))
const activeFeedCount = computed(() => {
  if (activeFeed.value === 'recommend') return recommendations.value.length
  if (activeFeed.value === 'following') return followingPosts.value.length
  return latestPosts.value.length
})

const activeFeedLabel = computed(() => {
  if (activeFeed.value === 'recommend') return `推荐 · ${RECOMMEND_BATCH_SIZE}/批`
  if (activeFeed.value === 'following') return '关注更新'
  return '最新内容'
})

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

function refreshCurrentFeed() {
  if (isRecommendFeed.value) {
    loadingText.value = recommendations.value.length ? '正在切换下一批推荐...' : '正在为你加载推荐...'
    if (recommendations.value.length) {
      skipNextAutoLoad.value = true
      return advanceRecommendations()
    }
    return refreshRecommendations()
  }
  if (activeFeed.value === 'following') {
    return fetchFollowingFeed()
  }
  return fetchLatestFeed()
}

function handleTabChange() {
  if (isRecommendFeed.value) {
    if (!recommendations.value.length) {
      loadingText.value = '正在为你加载推荐...'
      refreshRecommendations()
    } else {
      setupLoadMoreObserver()
    }
    return
  }

  if (activeFeed.value === 'following') {
    fetchFollowingFeed()
    return
  }

  fetchLatestFeed()
}

function openReason(item) {
  // 兼容传 postId（向后兼容）或整个 item
  if (typeof item === 'number') {
    reasonPostId.value = item
    reasonItem.value = null
  } else {
    reasonPostId.value = item.post_id
    reasonItem.value = item
  }
  reasonDialogVisible.value = true
}

async function openDebugPanel() {
  showDebugPanel.value = true
  if (recommendDebug.value) return

  try {
    await loadDebugSnapshot()
  } catch {
    // 错误已由拦截器处理
  }
}

async function handleDislike(postId) {
  try {
    await recordBehavior(postId, 'dislike')
    removeRecommendation(postId)
    ElMessage.success('已减少这类内容推荐')

    if (isRecommendFeed.value && recommendations.value.length < RECOMMEND_BATCH_SIZE && hasMore.value) {
      loadMoreRecommendations()
    }
  } catch {
    // 错误已由拦截器处理
  }
}

let loadMoreObserver = null

function destroyLoadMoreObserver() {
  if (loadMoreObserver) {
    loadMoreObserver.disconnect()
    loadMoreObserver = null
  }
}

function setupLoadMoreObserver() {
  destroyLoadMoreObserver()

  if (!loadMoreTrigger.value || !isRecommendFeed.value || !hasMore.value) return

  loadMoreObserver = new IntersectionObserver(
    (entries) => {
      const entry = entries[0]
      if (entry?.isIntersecting) {
        if (skipNextAutoLoad.value) {
          skipNextAutoLoad.value = false
          return
        }
        loadMoreRecommendations()
      }
    },
    {
      root: null,
      rootMargin: '280px 0px',
      threshold: 0,
    },
  )

  loadMoreObserver.observe(loadMoreTrigger.value)
}

watch(selectedUserId, (userId, previousUserId) => {
  if (!userId || userId === previousUserId || !isRecommendFeed.value) return
  loadingText.value = '正在为你加载推荐...'
  refreshRecommendations()
})

watch([loadMoreTrigger, isRecommendFeed, hasMore], () => {
  setupLoadMoreObserver()
})

onMounted(() => {
  selectedUserId.value = authStore.userId
  loadingText.value = '正在为你加载推荐...'
  refreshCurrentFeed()
})

onBeforeUnmount(() => {
  destroyLoadMoreObserver()
})
</script>

<style scoped>
.recommend-page {
  min-width: 0;
  display: grid;
  gap: 24px;
}

.recommend-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 336px;
  gap: 32px;
  align-items: start;
}

.feed-column,
.right-column {
  min-width: 0;
}

.feed-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 0 16px;
  border-bottom: 1px solid var(--cds-border-subtle);
}

.tabs-wrap {
  min-width: 0;
}

.feed-tabs {
  margin-bottom: -1px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-pill {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  background: var(--cds-layer-01);
  color: var(--cds-text-secondary);
  font-size: 13px;
  font-weight: 400;
}

.recommend-page :deep(.el-tabs__item) {
  color: var(--cds-text-secondary);
  background: transparent !important;
}

.recommend-page :deep(.el-tabs__item:hover),
.recommend-page :deep(.el-tabs__item.is-active) {
  color: var(--cds-text-primary) !important;
  background: transparent !important;
}

.recommend-page :deep(.el-tabs__active-bar) {
  background: var(--cds-link-primary) !important;
}

.toolbar-button.el-button--primary {
  min-width: 112px;
}

.loading-area {
  display: grid;
  place-items: center;
  min-height: 320px;
  background: var(--cds-layer-01);
  color: var(--cds-text-muted);
}

.loading-text,
.feed-status {
  color: var(--cds-text-secondary);
  line-height: 1.6;
}

.result-area {
  min-height: 220px;
}

.load-more-trigger {
  width: 100%;
  height: 1px;
}

.feed-status {
  padding: 16px;
  text-align: center;
  background: var(--cds-layer-01);
}

@media (max-width: 1180px) {
  .recommend-shell {
    grid-template-columns: 1fr;
    gap: 28px;
  }
}

@media (max-width: 720px) {
  .feed-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar-actions {
    justify-content: flex-start;
  }
}
</style>
