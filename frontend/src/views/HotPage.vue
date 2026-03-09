<template>
  <div class="hot-page">
    <div class="page-header">
      <h2><el-icon><TrendCharts /></el-icon> 热门帖子</h2>
    </div>

    <div v-loading="loading">
      <div v-for="(p, index) in posts" :key="p.id" class="hot-item">
        <span :class="['rank', rankClass(index)]">{{ index + 1 }}</span>
        <div class="hot-card-wrapper">
          <PostCard :post="p" />
        </div>
      </div>
      <el-empty v-if="!loading && posts.length === 0" description="暂无热门帖子" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getHotPosts } from '../api/post'
import PostCard from '../components/post/PostCard.vue'

const posts = ref([])
const loading = ref(false)

function rankClass(index) {
  if (index === 0) return 'rank-gold'
  if (index === 1) return 'rank-silver'
  if (index === 2) return 'rank-bronze'
  return ''
}

onMounted(async () => {
  loading.value = true
  try {
    const data = await getHotPosts(50)
    posts.value = data.posts
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.hot-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 16px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.hot-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.rank {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #909399;
  background: #f5f7fa;
  flex-shrink: 0;
  margin-top: 14px;
}

.rank-gold {
  background: #fdf6ec;
  color: #e6a23c;
}

.rank-silver {
  background: #f4f4f5;
  color: #909399;
}

.rank-bronze {
  background: #fef0f0;
  color: #f56c6c;
}

.hot-card-wrapper {
  flex: 1;
  min-width: 0;
}
</style>
