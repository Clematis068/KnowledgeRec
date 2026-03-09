<template>
  <div class="search-page">
    <h2 class="page-title">搜索 "{{ query }}" 的结果</h2>
    <p class="result-count" v-if="!loading">共 {{ total }} 条结果</p>

    <div v-loading="loading">
      <PostCard v-for="p in posts" :key="p.id" :post="p" />
      <el-empty v-if="!loading && posts.length === 0" description="未找到相关帖子" />
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
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { searchPosts } from '../api/post'
import PostCard from '../components/post/PostCard.vue'

const route = useRoute()
const query = ref('')
const posts = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)

async function fetchResults() {
  if (!query.value) return
  loading.value = true
  try {
    const data = await searchPosts(query.value, page.value, pageSize)
    posts.value = data.posts
    total.value = data.total
  } finally {
    loading.value = false
  }
}

watch(
  () => route.query.q,
  (newQ) => {
    query.value = newQ || ''
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
</style>
