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
  max-width: 980px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.page-title {
  padding: 22px 24px 8px;
  border: 1px solid var(--kr-border);
  border-radius: 30px 30px 18px 18px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(241, 232, 255, 0.92));
  box-shadow: var(--kr-shadow-clay-soft);
  font-size: clamp(2rem, 3vw, 3rem);
  font-weight: 800;
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.result-count {
  margin-top: -18px;
  margin-left: 24px;
  width: fit-content;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--kr-secondary-soft);
  color: var(--kr-secondary);
  font-size: 12px;
  font-weight: 800;
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
  padding: 18px;
  border-radius: 24px;
  margin-bottom: 12px;
  cursor: pointer;
  border: 1px solid var(--kr-border);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(240, 232, 255, 0.9));
  box-shadow: var(--kr-shadow-clay-soft);
  transition: transform 0.2s ease;
}

.user-item:hover {
  transform: translateY(-3px);
}

.user-avatar {
  background: linear-gradient(135deg, var(--kr-secondary), var(--kr-primary));
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
  font-size: 1rem;
  font-weight: 800;
  color: var(--kr-text);
}

.user-bio {
  font-size: 13px;
  color: var(--kr-text-soft);
  line-height: 1.6;
}
</style>
