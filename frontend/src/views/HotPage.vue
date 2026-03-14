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
  max-width: 980px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.page-header {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}

.page-header h2 {
  font-size: clamp(2rem, 3vw, 3rem);
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: -0.05em;
}

.hot-item {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.rank {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 20px;
  font-size: 1.05rem;
  font-weight: 900;
  color: var(--kr-text-soft);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(240, 232, 255, 0.92));
  box-shadow: var(--kr-shadow-clay-soft);
  flex-shrink: 0;
  margin-top: 12px;
}

.rank-gold {
  color: #9a5b00;
  background: linear-gradient(145deg, rgba(255, 244, 214, 0.98), rgba(255, 228, 132, 0.78));
}

.rank-silver {
  color: #5f6b85;
  background: linear-gradient(145deg, rgba(244, 247, 255, 0.98), rgba(219, 228, 245, 0.88));
}

.rank-bronze {
  color: #9f4c2f;
  background: linear-gradient(145deg, rgba(255, 235, 224, 0.98), rgba(247, 192, 162, 0.86));
}

.hot-card-wrapper {
  flex: 1;
  min-width: 0;
}

@media (max-width: 640px) {
  .hot-item {
    grid-template-columns: 1fr;
  }

  .rank {
    margin-top: 0;
  }
}
</style>
