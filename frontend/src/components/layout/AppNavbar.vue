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
        <el-input
          ref="searchInputRef"
          v-model="searchQuery"
          :prefix-icon="Search"
          :placeholder="searchPlaceholder"
          clearable
          size="large"
          class="search-input"
          @keyup.enter="handleSearch"
        />
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
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const searchInputRef = ref()
const searchQuery = ref('')
const searchType = ref('post')

const searchPlaceholder = computed(() => (
  searchType.value === 'author' ? '搜索作者' : '搜索帖子或话题'
))

function handleSearch() {
  const keyword = searchQuery.value.trim()
  if (!keyword) return
  router.push({ path: '/search', query: { q: keyword, type: searchType.value } })
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
}

.search-shell {
  display: grid;
  grid-template-columns: 122px minmax(0, 1fr);
  gap: 10px;
  padding: 8px;
  border: 1px solid rgba(124, 58, 237, 0.1);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.76);
}

.search-type :deep(.el-select__wrapper),
.search-input :deep(.el-input__wrapper) {
  min-height: 46px;
  background: #fff;
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
