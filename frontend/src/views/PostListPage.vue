<template>
  <div class="post-list-page">
    <div class="page-header">
      <h2>帖子列表</h2>
    </div>

    <el-tabs v-model="activeDomain" @tab-change="onDomainChange">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane
        v-for="d in domains"
        :key="d.id"
        :label="d.name"
        :name="String(d.id)"
      />
    </el-tabs>

    <div v-loading="loading">
      <PostCard v-for="p in posts" :key="p.id" :post="p" />
      <el-empty v-if="!loading && posts.length === 0" description="暂无帖子" />
    </div>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetchPosts"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getPostList } from '../api/post'
import PostCard from '../components/post/PostCard.vue'

// 领域列表（与后端 seed 一致）
const domains = ref([
  { id: 1, name: '计算机科学' },
  { id: 2, name: '数学' },
  { id: 3, name: '物理学' },
  { id: 4, name: '生物学' },
  { id: 5, name: '经济学' },
])

const activeDomain = ref('all')
const posts = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)

async function fetchPosts() {
  loading.value = true
  try {
    const domainId = activeDomain.value === 'all' ? null : Number(activeDomain.value)
    const data = await getPostList(page.value, pageSize, domainId)
    posts.value = data.posts
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function onDomainChange() {
  page.value = 1
  fetchPosts()
}

onMounted(fetchPosts)
</script>

<style scoped>
.post-list-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 16px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
