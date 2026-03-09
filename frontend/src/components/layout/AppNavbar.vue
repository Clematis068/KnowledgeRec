<template>
  <div class="navbar">
    <div class="navbar-brand">
      <el-icon :size="22"><Connection /></el-icon>
      <span class="title">KnowledgeRec</span>
      <span class="subtitle">知识社区推荐系统</span>
    </div>

    <div class="navbar-search">
      <el-input
        v-model="searchQuery"
        placeholder="搜索知识帖子..."
        :prefix-icon="Search"
        clearable
        size="default"
        style="width: 300px"
        @keyup.enter="handleSearch"
      />
    </div>

    <div class="navbar-right">
      <template v-if="authStore.isLoggedIn">
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="28" :icon="UserFilled" />
            <span class="username">{{ authStore.username }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="recommend">
                <el-icon><Star /></el-icon>我的推荐
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
        <el-button text @click="$router.push('/login')">登录</el-button>
        <el-button type="primary" size="small" @click="$router.push('/register')">注册</el-button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { UserFilled, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const searchQuery = ref('')

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/search', query: { q: searchQuery.value.trim() } })
  }
}

function handleCommand(cmd) {
  if (cmd === 'recommend') {
    router.push('/recommend')
  } else if (cmd === 'profile') {
    router.push(`/users/${authStore.userId}`)
  } else if (cmd === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.navbar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #409eff;
}

.title {
  font-size: 18px;
  font-weight: 700;
}

.subtitle {
  font-size: 13px;
  color: #909399;
  margin-left: 4px;
}

.navbar-search {
  flex: 1;
  display: flex;
  justify-content: center;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #606266;
}

.username {
  font-size: 14px;
}
</style>
