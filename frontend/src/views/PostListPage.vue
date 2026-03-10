<script setup>
import { onMounted, ref } from 'vue'

import PostCard from '../components/post/PostCard.vue'
import { getPostList } from '../api/post'
import { useDomains } from '../composables/useDomains'

const { domains, fetchDomains } = useDomains()

const activeDomain = ref('all')
const posts = ref([])
const page = ref(1)
const total = ref(0)
const loading = ref(false)
const pageSize = 20

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

onMounted(() => {
  fetchDomains()
  fetchPosts()
})
</script>

<template>
  <div class="post-list-page">
    <div class="page-header">
      <h2>帖子列表</h2>
    </div>

    <el-tabs v-model="activeDomain" @tab-change="onDomainChange">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane
        v-for="domain in domains"
        :key="domain.id"
        :label="domain.name"
        :name="String(domain.id)"
      />
    </el-tabs>

    <div v-loading="loading">
      <PostCard v-for="post in posts" :key="post.id" :post="post" />
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
