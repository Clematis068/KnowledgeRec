<template>
  <div class="search-page">
    <h2 class="page-title">搜索 "{{ query }}" 的结果</h2>
    <p class="result-count" v-if="!loading">共 {{ total }} 条结果</p>

    <div v-loading="loading">
      <!-- 帖子结果 -->
      <template v-if="searchType !== 'author'">
        <PostCard v-for="p in posts" :key="p.id" :post="p" />
        <el-empty v-if="!loading && posts.length === 0" description="未找到相关帖子" />
      </template>

      <!-- 用户结果 -->
      <template v-else>
        <div v-for="u in users" :key="u.id" class="user-item" @click="$router.push(`/users/${u.id}`)">
          <el-avatar :size="40" class="user-avatar">
            {{ u.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <div class="user-info">
            <span class="user-name">{{ u.username }}</span>
            <span class="user-bio">{{ u.bio || '暂无简介' }}</span>
          </div>
        </div>
        <el-empty v-if="!loading && users.length === 0" description="未找到相关用户" />
      </template>
    </div>

    <div v-if="total > pageSize" class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetchResults"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { searchPosts } from '../api/post'
import PostCard from '../components/post/PostCard.vue'

const route = useRoute()
const query = ref('')
const searchType = ref('post')
const posts = ref([])
const users = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)

async function fetchResults() {
  if (!query.value) return
  loading.value = true
  try {
    const data = await searchPosts(query.value, page.value, pageSize, searchType.value)
    if (searchType.value === 'author') {
      users.value = data.users || []
      posts.value = []
    } else {
      posts.value = data.posts || []
      users.value = []
    }
    total.value = data.total
  } finally {
    loading.value = false
  }
}

watch(
  () => [route.query.q, route.query.type],
  ([newQ, newType]) => {
    query.value = newQ || ''
    searchType.value = newType || 'post'
    page.value = 1
    fetchResults()
  },
  { immediate: true }
)
</script>

<style scoped>
.search-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.result-count {
  font-size: 13px;
  color: #909399;
  margin-bottom: 16px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 10px;
  cursor: pointer;
  border: 1px solid #ebeef5;
  transition: box-shadow 0.2s;
}

.user-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-size: 16px;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.user-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.user-bio {
  font-size: 13px;
  color: #909399;
}
</style>
