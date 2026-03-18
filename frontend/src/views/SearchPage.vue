<template>
  <div class="search-page">
    <h2 class="page-title">搜索 "{{ query }}" 的结果</h2>

    <div v-loading="loading">
      <!-- 综合搜索：用户 + 帖子 -->
      <template v-if="searchType === 'all'">
        <!-- 用户区 -->
        <section v-if="users.length" class="search-section">
          <h3 class="section-label">用户（{{ userTotal }} 人）</h3>
          <div class="user-grid">
            <div
              v-for="u in users"
              :key="u.id"
              class="user-card"
              @click="$router.push(`/users/${u.id}`)"
            >
              <el-avatar :size="48" class="user-avatar">
                {{ u.username?.charAt(0)?.toUpperCase() }}
              </el-avatar>
              <span class="user-name">{{ u.username }}</span>
              <span class="user-bio">{{ u.bio || '暂无简介' }}</span>
            </div>
          </div>
        </section>

        <!-- 帖子区 -->
        <section class="search-section">
          <h3 class="section-label">帖子（{{ postTotal }} 篇）</h3>
          <PostCard v-for="p in posts" :key="p.id" :post="p" />
          <el-empty v-if="!loading && posts.length === 0 && users.length === 0" description="未找到相关结果" />
        </section>

        <div v-if="postTotal > pageSize" class="pagination">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="postTotal"
            layout="prev, pager, next, total"
            @current-change="fetchResults"
          />
        </div>
      </template>

      <!-- 仅搜用户 -->
      <template v-else-if="searchType === 'author'">
        <div class="user-grid">
          <div v-for="u in users" :key="u.id" class="user-card" @click="$router.push(`/users/${u.id}`)">
            <el-avatar :size="48" class="user-avatar">
              {{ u.username?.charAt(0)?.toUpperCase() }}
            </el-avatar>
            <span class="user-name">{{ u.username }}</span>
            <span class="user-bio">{{ u.bio || '暂无简介' }}</span>
          </div>
        </div>
        <el-empty v-if="!loading && users.length === 0" description="未找到相关用户" />
        <div v-if="total > pageSize" class="pagination">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next, total"
            @current-change="fetchResults"
          />
        </div>
      </template>

      <!-- 仅搜帖子 -->
      <template v-else>
        <PostCard v-for="p in posts" :key="p.id" :post="p" />
        <el-empty v-if="!loading && posts.length === 0" description="未找到相关帖子" />
        <div v-if="total > pageSize" class="pagination">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next, total"
            @current-change="fetchResults"
          />
        </div>
      </template>
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
const searchType = ref('all')
const posts = ref([])
const users = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const postTotal = ref(0)
const userTotal = ref(0)
const loading = ref(false)

async function fetchResults() {
  if (!query.value) return
  loading.value = true
  try {
    const data = await searchPosts(query.value, page.value, pageSize, searchType.value)
    if (searchType.value === 'all') {
      posts.value = data.posts || []
      users.value = data.users || []
      postTotal.value = data.post_total || 0
      userTotal.value = data.user_total || 0
    } else if (searchType.value === 'author') {
      users.value = data.users || []
      posts.value = []
      total.value = data.total
    } else {
      posts.value = data.posts || []
      users.value = []
      total.value = data.total
    }
  } finally {
    loading.value = false
  }
}

watch(
  () => [route.query.q, route.query.type],
  ([newQ, newType]) => {
    query.value = newQ || ''
    searchType.value = newType || 'all'
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
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay-soft);
  font-size: clamp(2rem, 3vw, 3rem);
  font-weight: 800;
  line-height: 0.98;
  letter-spacing: -0.05em;
}

.search-section {
  display: grid;
  gap: 12px;
}

.section-label {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--kr-text-muted);
  padding: 8px 12px;
  margin: 0;
}

.user-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.user-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
  padding: 20px 14px 16px;
  border-radius: 20px;
  cursor: pointer;
  border: 1px solid var(--kr-border);
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay-soft);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.user-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--kr-shadow-clay-soft), 0 4px 12px rgba(0, 0, 0, 0.06);
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.user-avatar {
  background: linear-gradient(135deg, var(--kr-secondary), var(--kr-primary));
  color: #fff;
  font-size: 18px;
  flex-shrink: 0;
}

.user-name {
  font-size: 0.95rem;
  font-weight: 800;
  color: var(--kr-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.user-bio {
  font-size: 12px;
  color: var(--kr-text-soft);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
