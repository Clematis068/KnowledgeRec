<template>
  <div class="navbar">
    <div class="brand-block" @click="router.push('/')">
      <div class="brand-mark">
        <el-icon :size="20"><Connection /></el-icon>
      </div>
      <div class="brand-copy">
        <span class="brand-title">KnowledgeRec</span>
        <span class="brand-subtitle">知识社区</span>
      </div>
    </div>

    <div class="navbar-search">
      <div class="search-shell">
        <el-select v-model="searchType" size="large" class="search-type">
          <el-option label="搜帖子" value="post" />
          <el-option label="搜作者" value="author" />
        </el-select>
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
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="34" :icon="UserFilled" class="user-avatar" />
            <span class="username">{{ authStore.username }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="recommend">
                <el-icon><Star /></el-icon>我的推荐
              </el-dropdown-item>
              <el-dropdown-item command="my-posts">
                <el-icon><Document /></el-icon>我的发帖
              </el-dropdown-item>
              <el-dropdown-item command="profile">
                <el-icon><User /></el-icon>个人资料
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <el-button text @click="router.push('/login')">登录</el-button>
        <el-button type="primary" @click="router.push('/register')">注册</el-button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, UserFilled } from '@element-plus/icons-vue'
import { getHotPosts } from '../../api/post'
import { useAuthStore } from '../../stores/auth'

const HOT_SUGGESTION_LIMIT = 5
const SEARCH_HISTORY_LIMIT = 5
const SEARCH_HISTORY_STORAGE_KEY = 'app:search-history'

const router = useRouter()
const authStore = useAuthStore()
const searchInputRef = ref()
const searchQuery = ref('')
const searchType = ref('post')
const hotSuggestions = ref([])
const hotSuggestionsLoaded = ref(false)
const searchHistory = ref(loadSearchHistory())

const searchPlaceholder = computed(() => (
  searchType.value === 'author' ? '搜索作者' : '搜索帖子或话题'
))

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

function handleCommand(cmd) {
  if (cmd === 'recommend') {
    router.push('/recommend')
  } else if (cmd === 'my-posts') {
    router.push('/my-posts')
  } else if (cmd === 'profile') {
    router.push(`/users/${authStore.userId}`)
  } else if (cmd === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

onMounted(() => {
  window.addEventListener('app:focus-search', handleFocusSearch)
})

onBeforeUnmount(() => {
  window.removeEventListener('app:focus-search', handleFocusSearch)
})
</script>

<style scoped>
.navbar {
  display: grid;
  grid-template-columns: auto minmax(320px, 1fr) auto;
  gap: 18px;
  align-items: center;
  min-height: 74px;
  padding: 14px 20px;
  border: 1px solid rgba(124, 58, 237, 0.14);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 18px 44px rgba(76, 29, 149, 0.08);
  backdrop-filter: blur(18px);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  cursor: pointer;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(135deg, var(--kr-primary), #9f67ff);
  box-shadow: 0 10px 24px rgba(124, 58, 237, 0.28);
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-title {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.brand-subtitle {
  font-size: 13px;
  color: var(--kr-text-soft);
}

.navbar-search {
  min-width: 0;
  display: flex;
  justify-content: center;
}

.search-shell {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr);
  gap: 8px;
  padding: 6px;
  width: min(100%, 460px);
  border: 1px solid rgba(124, 58, 237, 0.1);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.76);
}

.search-type :deep(.el-select__wrapper),
.search-input :deep(.el-input__wrapper) {
  min-height: 40px;
  background: #fff;
  font-size: 13px;
}

.search-type :deep(.el-select__selected-item),
.search-input :deep(.el-input__inner),
.search-input :deep(.el-input__prefix-inner) {
  font-size: 13px;
}

.search-suggestion {
  display: grid;
  gap: 4px;
  padding: 3px 0;
}

.search-suggestion.is-action {
  gap: 0;
}

.search-suggestion.is-first-hot {
  margin-top: 6px;
  padding-top: 10px;
  border-top: 1px solid rgba(124, 58, 237, 0.12);
}

.suggestion-divider {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--kr-text-muted);
}

.suggestion-title {
  color: var(--kr-text);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.suggestion-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 11px;
  color: var(--kr-text-muted);
}

.suggestion-source {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 10px;
  font-weight: 600;
  color: var(--kr-primary-strong);
  background: rgba(124, 58, 237, 0.08);
}

.suggestion-source.history {
  color: #2563eb;
  background: rgba(37, 99, 235, 0.1);
}

.suggestion-action {
  color: #ef4444;
  font-size: 12px;
  font-weight: 600;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px 8px 8px;
  border-radius: 999px;
  color: var(--kr-text);
  background: rgba(124, 58, 237, 0.06);
}

.user-avatar {
  background: linear-gradient(135deg, var(--kr-primary), #9f67ff);
}

.username {
  max-width: 112px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

@media (max-width: 1100px) {
  .navbar {
    grid-template-columns: 1fr;
  }

  .navbar-right {
    justify-content: space-between;
  }
}

@media (max-width: 680px) {
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
