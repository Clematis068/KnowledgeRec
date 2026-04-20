<template>
  <div class="navbar">
    <div class="brand-block" @click="router.push('/recommend')">
      <div class="brand-mark">
        <el-icon :size="18"><Connection /></el-icon>
      </div>
      <div class="brand-copy">
        <span class="brand-eyebrow">Knowledge Graph Community</span>
        <span class="brand-title">知识推荐</span>
      </div>
    </div>

    <div class="navbar-search">
      <div class="search-shell">
        <button type="button" class="search-type-chip" @click="toggleSearchType">
          {{ searchTypeLabel }}
        </button>
        <el-autocomplete
          ref="searchInputRef"
          v-model="searchQuery"
          :fetch-suggestions="fetchSearchSuggestions"
          :prefix-icon="Search"
          :placeholder="searchPlaceholder"
          popper-class="search-suggestion-popper"
          clearable
          :trigger-on-focus="searchType === 'post'"
          value-key="value"
          size="large"
          class="search-input"
          @keyup.enter="handleSearch"
          @select="handleSuggestionSelect"
        >
          <template #default="{ item }">
            <div :class="['search-suggestion', { 'is-first-hot': item.isFirstHot, 'is-action': item.kind === 'clear-history' }]">
              <span v-if="item.isFirstHistory" class="suggestion-divider">搜索历史</span>
              <span v-if="item.isFirstHot" class="suggestion-divider">热门内容</span>
              <template v-if="item.kind === 'clear-history'">
                <span class="suggestion-action">{{ item.value }}</span>
              </template>
              <template v-else>
                <span class="suggestion-title">{{ item.value }}</span>
                <span class="suggestion-meta">
                  <span :class="['suggestion-source', item.kind]">
                    {{ item.kind === 'history' ? '搜索历史' : '热搜' }}
                  </span>
                  <template v-if="item.kind === 'hot'">
                    <span>#{{ item.rank }}</span>
                    <span>{{ item.authorName || '匿名作者' }}</span>
                    <span>{{ item.likeCount || 0 }} 赞</span>
                  </template>
                </span>
              </template>
            </div>
          </template>
        </el-autocomplete>
      </div>
    </div>

    <div class="navbar-right">
      <template v-if="authStore.isLoggedIn">
        <el-button text class="nav-action" @click="router.push('/recommend')">首页</el-button>
        <el-button text class="nav-action" @click="handleWrite">
          <el-icon><EditPen /></el-icon>
          写作
        </el-button>
        <button type="button" class="icon-button notification-btn" @click="router.push('/notifications')" aria-label="通知">
          <el-icon><Bell /></el-icon>
          <span v-if="notificationStore.totalCount > 0" class="notification-badge">
            {{ notificationStore.totalCount > 99 ? '99+' : notificationStore.totalCount }}
          </span>
        </button>

        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="34" :icon="UserFilled" class="user-avatar" />
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="recommend">我的推荐</el-dropdown-item>
              <el-dropdown-item command="my-posts">我的发帖</el-dropdown-item>
              <el-dropdown-item command="profile">个人资料</el-dropdown-item>
              <el-dropdown-item command="evaluation">实验评估</el-dropdown-item>
              <el-dropdown-item v-if="authStore.user?.role === 'admin'" command="admin">管理后台</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <el-button text class="nav-action" @click="router.push('/login')">登录</el-button>
        <el-button type="primary" @click="router.push('/register')">开始使用</el-button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, Bell, Connection, EditPen, Search, UserFilled } from '@element-plus/icons-vue'
import { getHotPosts } from '../../api/post'
import { useAuthStore } from '../../stores/auth'
import { useNotificationStore } from '../../stores/notification'

const HOT_SUGGESTION_LIMIT = 5
const SEARCH_HISTORY_LIMIT = 5
const SEARCH_HISTORY_STORAGE_KEY = 'app:search-history'

const router = useRouter()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()
const searchInputRef = ref()
const searchQuery = ref('')
const searchType = ref('post')
const hotSuggestions = ref([])
const hotSuggestionsLoaded = ref(false)
const searchHistory = ref(loadSearchHistory())

const searchTypeLabel = computed(() => (searchType.value === 'author' ? '作者' : '帖子'))
const searchPlaceholder = computed(() => (
  searchType.value === 'author' ? '搜索作者' : '搜索帖子或话题'
))

function toggleSearchType() {
  searchType.value = searchType.value === 'post' ? 'author' : 'post'
  searchQuery.value = ''
  focusSearch()
}

async function ensureHotSuggestionsLoaded() {
  if (hotSuggestionsLoaded.value) return

  const data = await getHotPosts(HOT_SUGGESTION_LIMIT)
  hotSuggestions.value = (data.posts || []).map((post, index) => ({
    value: post.title,
    postId: post.id,
    rank: index + 1,
    likeCount: post.like_count,
    authorName: post.author_name,
    kind: 'hot',
  }))
  hotSuggestionsLoaded.value = true
}

function loadSearchHistory() {
  try {
    const rawValue = localStorage.getItem(SEARCH_HISTORY_STORAGE_KEY)
    const parsedValue = JSON.parse(rawValue || '[]')
    if (!Array.isArray(parsedValue)) return []
    return parsedValue
      .filter((item) => item && typeof item.value === 'string' && typeof item.searchType === 'string')
      .slice(0, SEARCH_HISTORY_LIMIT * 2)
      .map((item) => ({
        value: item.value.trim(),
        searchType: item.searchType,
        kind: 'history',
      }))
      .filter((item) => item.value)
  } catch {
    return []
  }
}

function saveSearchHistory(keyword, type) {
  const normalizedKeyword = String(keyword || '').trim()
  if (!normalizedKeyword) return

  const nextHistory = [
    {
      value: normalizedKeyword,
      searchType: type,
      kind: 'history',
    },
    ...searchHistory.value.filter((item) => !(item.value === normalizedKeyword && item.searchType === type)),
  ]

  const typeCounter = {}
  searchHistory.value = nextHistory.filter((item) => {
    const currentCount = typeCounter[item.searchType] || 0
    if (currentCount >= SEARCH_HISTORY_LIMIT) {
      return false
    }
    typeCounter[item.searchType] = currentCount + 1
    return true
  })

  localStorage.setItem(
    SEARCH_HISTORY_STORAGE_KEY,
    JSON.stringify(searchHistory.value.map(({ value, searchType }) => ({ value, searchType }))),
  )
}

function buildHistorySuggestions(keyword) {
  const currentType = searchType.value
  const lowerKeyword = keyword.toLowerCase()
  return searchHistory.value
    .filter((item) => item.searchType === currentType)
    .filter((item) => !keyword || item.value.toLowerCase().includes(lowerKeyword))
    .slice(0, SEARCH_HISTORY_LIMIT)
}

function clearSearchHistory(type) {
  searchHistory.value = searchHistory.value.filter((item) => item.searchType !== type)
  localStorage.setItem(
    SEARCH_HISTORY_STORAGE_KEY,
    JSON.stringify(searchHistory.value.map(({ value, searchType }) => ({ value, searchType }))),
  )
}

function buildHotSuggestions(keyword) {
  const lowerKeyword = keyword.toLowerCase()
  return hotSuggestions.value
    .filter((item) => !keyword || item.value.toLowerCase().includes(lowerKeyword))
    .slice(0, HOT_SUGGESTION_LIMIT)
}

async function fetchSearchSuggestions(queryString, callback) {
  const rawKeyword = String(queryString || '').trim()
  if (searchType.value !== 'post') {
    const historySuggestions = buildHistorySuggestions(rawKeyword).map((item, index) => ({
      ...item,
      isFirstHistory: index === 0,
    }))
    if (historySuggestions.length > 0 && !rawKeyword) {
      historySuggestions.push({
        kind: 'clear-history',
        value: '清空搜索历史',
        searchType: searchType.value,
      })
    }
    callback(historySuggestions)
    return
  }

  try {
    await ensureHotSuggestionsLoaded()
    const keyword = rawKeyword.toLowerCase()
    const historySuggestions = buildHistorySuggestions(keyword).map((item, index) => ({
      ...item,
      isFirstHistory: index === 0,
    }))
    const hotSuggestionsForView = buildHotSuggestions(keyword).map((item, index) => ({
      ...item,
      isFirstHot: historySuggestions.length > 0 && index === 0,
    }))

    if (historySuggestions.length > 0 && !rawKeyword) {
      historySuggestions.push({
        kind: 'clear-history',
        value: '清空搜索历史',
        searchType: searchType.value,
      })
    }

    callback([
      ...historySuggestions,
      ...hotSuggestionsForView,
    ])
  } catch {
    callback(buildHistorySuggestions(rawKeyword))
  }
}

function handleSearch() {
  const keyword = searchQuery.value.trim()
  if (!keyword) return
  saveSearchHistory(keyword, searchType.value)
  router.push({ path: '/search', query: { q: keyword, type: searchType.value } })
}

function handleSuggestionSelect(item) {
  if (item.kind === 'clear-history') {
    clearSearchHistory(item.searchType || searchType.value)
    searchQuery.value = ''
    return
  }

  searchQuery.value = item.value
  if (item.kind === 'history') {
    saveSearchHistory(item.value, item.searchType)
    router.push({ path: '/search', query: { q: item.value, type: item.searchType } })
    return
  }

  saveSearchHistory(item.value, 'post')
  router.push(`/posts/${item.postId}`)
}

function focusSearch() {
  searchInputRef.value?.focus?.()
}

function handleFocusSearch() {
  focusSearch()
}

function handleWrite() {
  router.push(authStore.isLoggedIn ? '/create-post' : '/login')
}

function handleCommand(cmd) {
  if (cmd === 'recommend') {
    router.push('/recommend')
  } else if (cmd === 'my-posts') {
    router.push('/my-posts')
  } else if (cmd === 'profile') {
    router.push(`/users/${authStore.userId}`)
  } else if (cmd === 'evaluation') {
    router.push('/evaluation')
  } else if (cmd === 'admin') {
    router.push('/admin')
  } else if (cmd === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

onMounted(() => {
  window.addEventListener('app:focus-search', handleFocusSearch)
  if (authStore.isLoggedIn) {
    notificationStore.startListening(authStore.token)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('app:focus-search', handleFocusSearch)
  notificationStore.stopListening()
})

watch(() => authStore.isLoggedIn, (loggedIn) => {
  if (loggedIn) {
    notificationStore.startListening(authStore.token)
  } else {
    notificationStore.stopListening()
  }
})
</script>

<style scoped>
.navbar {
  display: grid;
  grid-template-columns: auto minmax(280px, 520px) auto;
  gap: 24px;
  align-items: center;
  min-height: 64px;
  max-width: var(--cds-layout-max-width);
  margin: 0 auto;
  padding: 8px 32px;
}

.brand-block {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  color: #ffffff;
  background: var(--cds-background-inverse);
}

.brand-copy {
  display: grid;
  gap: 2px;
}

.brand-eyebrow {
  color: var(--cds-text-muted);
  font-family: 'IBM Plex Mono', 'SFMono-Regular', Menlo, monospace;
  font-size: 11px;
  letter-spacing: 0.32px;
}

.brand-title {
  color: var(--cds-text-primary);
  font-size: 18px;
  line-height: 1.1;
  font-weight: 400;
}

.navbar-search {
  min-width: 0;
  display: flex;
  justify-content: flex-start;
}

.search-shell {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  width: min(100%, 520px);
}

.search-type-chip {
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--cds-border-subtle);
  background: transparent;
  color: var(--cds-text-secondary);
  font-size: 13px;
  font-weight: 600;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.search-type-chip:hover {
  border-color: var(--cds-border-strong);
  background: var(--cds-layer-hover);
}

.search-input :deep(.el-input__wrapper) {
  min-height: 40px;
  background: var(--cds-layer-01) !important;
  outline: none !important;
  box-shadow: inset 0 -1px 0 var(--cds-border-subtle) !important;
}

.search-input :deep(.el-input__wrapper:hover) {
  outline: none !important;
  box-shadow: inset 0 -2px 0 var(--cds-text-primary) !important;
}

.search-input :deep(.el-input__wrapper.is-focus),
.search-input :deep(.el-input__wrapper:focus),
.search-input :deep(.el-input__wrapper:focus-visible),
.search-input :deep(.el-input__wrapper:focus-within) {
  outline: none !important;
  border: none !important;
  box-shadow: inset 0 -2px 0 var(--cds-link-primary) !important;
}

.search-suggestion {
  display: grid;
  gap: 5px;
  padding: 4px 2px;
}

.search-suggestion.is-action {
  gap: 0;
}

.search-suggestion.is-first-hot {
  margin-top: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--cds-border-subtle);
}

.suggestion-divider {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.32px;
  text-transform: uppercase;
  color: var(--cds-text-muted);
}

.suggestion-title {
  color: var(--cds-text-primary);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.suggestion-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 11px;
  color: var(--cds-text-muted);
}

.suggestion-source {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 400;
  color: var(--cds-link-primary);
  background: var(--cds-blue-10);
}

.suggestion-source.history {
  color: var(--cds-text-secondary);
  background: var(--cds-layer-01);
}

.suggestion-action {
  color: var(--cds-support-error);
  font-size: 12px;
  font-weight: 600;
}

.navbar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.nav-action {
  --el-button-text-color: var(--cds-text-primary);
  --el-button-hover-text-color: var(--cds-text-primary);
  --el-button-active-text-color: var(--cds-text-primary);
  --el-button-bg-color: transparent;
  --el-button-hover-bg-color: var(--cds-layer-hover);
  --el-button-active-bg-color: var(--cds-layer-hover);
  --el-button-border-color: transparent;
  --el-button-hover-border-color: transparent;
  --el-button-active-border-color: transparent;
  color: var(--cds-text-primary);
  font-weight: 400;
}

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--cds-border-subtle);
  background: transparent;
  color: var(--cds-text-primary);
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.icon-button:hover {
  border-color: var(--cds-border-strong);
  background: var(--cds-layer-hover);
}

.notification-btn {
  position: relative;
}

.notification-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--cds-support-error);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}

.user-info {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 0;
  color: var(--cds-text-primary);
  transition: background-color 0.2s ease;
  cursor: pointer;
}

.user-info:hover {
  background: var(--cds-layer-hover);
}

.user-avatar {
  color: #ffffff;
  background: var(--cds-background-inverse);
}

.username {
  max-width: 112px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 400;
}

@media (max-width: 1180px) {
  .navbar {
    grid-template-columns: 1fr;
    padding-inline: 24px;
  }

  .navbar-search {
    order: 3;
  }

  .navbar-right {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

@media (max-width: 680px) {
  .navbar {
    padding-inline: 16px;
  }

  .search-shell {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.search-suggestion-popper .el-scrollbar__wrap {
  max-height: none !important;
  overflow: visible !important;
}

.search-suggestion-popper .el-scrollbar__bar {
  display: none !important;
}
</style>
