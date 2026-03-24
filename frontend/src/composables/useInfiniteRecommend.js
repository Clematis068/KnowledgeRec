import { computed, ref, unref } from 'vue'

import { getRecommendations, getMyRecommendations } from '../api/recommendation'

export function useInfiniteRecommend({
  authStore,
  selectedUserId,
  batchSize = 20,
  debug = false,
  enableLlm = false,
} = {}) {
  const recommendations = ref([])
  const recommendDebug = ref(null)
  const loading = ref(false)
  const loadingMore = ref(false)
  const hasMore = ref(true)

  const isOwnSelection = computed(() => unref(selectedUserId) === authStore.userId)
  const loadedPostIds = computed(() => recommendations.value.map((item) => item.post_id))

  function dedupeItems(items, existingIds = new Set()) {
    const seenIds = new Set(existingIds)

    return (items || []).filter((item) => {
      const postId = item?.post_id
      if (!postId || seenIds.has(postId)) return false
      seenIds.add(postId)
      return true
    })
  }

  async function requestBatch(excludePostIds = [], overrides = {}) {
    const userId = unref(selectedUserId)
    if (!userId) {
      return { recommendations: [], debug: null }
    }

    const requestOptions = {
      topN: batchSize,
      debug,
      enableLlm,
      excludePostIds,
      ...overrides,
    }

    if (isOwnSelection.value) {
      return getMyRecommendations(requestOptions)
    }

    return getRecommendations(userId, requestOptions)
  }

  async function refreshRecommendations() {
    const userId = unref(selectedUserId)
    if (!userId) return

    loading.value = true
    hasMore.value = true

    try {
      const data = await requestBatch([])
      const nextItems = dedupeItems(data.recommendations)
      recommendations.value = nextItems
      recommendDebug.value = data.debug || null
      hasMore.value = nextItems.length >= batchSize
    } catch {
      recommendations.value = []
      recommendDebug.value = null
      hasMore.value = false
    } finally {
      loading.value = false
    }
  }

  async function advanceRecommendations() {
    const userId = unref(selectedUserId)
    if (!userId) return

    const excludePostIds = loadedPostIds.value
    if (!excludePostIds.length) {
      return refreshRecommendations()
    }

    loading.value = true

    try {
      const data = await requestBatch(excludePostIds)
      const nextItems = dedupeItems(data.recommendations)

      if (nextItems.length) {
        recommendations.value = nextItems
      }

      hasMore.value = nextItems.length >= batchSize
    } catch {
      hasMore.value = false
    } finally {
      loading.value = false
    }
  }

  async function loadMoreRecommendations() {
    const userId = unref(selectedUserId)
    if (!userId || loading.value || loadingMore.value || !hasMore.value) return

    loadingMore.value = true

    try {
      const existingIds = new Set(loadedPostIds.value)
      const data = await requestBatch(loadedPostIds.value)
      const nextItems = dedupeItems(data.recommendations, existingIds)

      recommendations.value = [...recommendations.value, ...nextItems]
      if (data.debug) {
        recommendDebug.value = data.debug
      }

      hasMore.value = nextItems.length > 0 && nextItems.length >= batchSize
    } catch {
      hasMore.value = false
    } finally {
      loadingMore.value = false
    }
  }

  function removeRecommendation(postId) {
    recommendations.value = recommendations.value.filter((item) => item.post_id !== postId)
  }

  async function loadDebugSnapshot() {
    const userId = unref(selectedUserId)
    if (!userId) return null

    const data = await requestBatch([], { debug: true })
    recommendDebug.value = data.debug || null
    return recommendDebug.value
  }

  return {
    recommendations,
    recommendDebug,
    loading,
    loadingMore,
    hasMore,
    isOwnSelection,
    loadedPostIds,
    refreshRecommendations,
    advanceRecommendations,
    loadMoreRecommendations,
    removeRecommendation,
    loadDebugSnapshot,
  }
}
