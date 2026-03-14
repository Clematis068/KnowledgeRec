<template>
  <aside class="right-rail">
    <section class="rail-section">
      <h2 class="rail-title">精选内容</h2>
      <div class="pick-list">
        <article
          v-for="post in hotPicks"
          :key="post.id"
          class="pick-item"
          @click="goToPost(post.id)"
        >
          <div class="pick-topline">
            <span class="pick-source">{{ post.domain_name || '知识推荐' }}</span>
            <span class="pick-author">作者：{{ post.author_name || '匿名作者' }}</span>
          </div>
          <h3 class="pick-title">{{ post.title }}</h3>
          <div class="pick-meta">
            <span>{{ formatDate(post.created_at) }}</span>
            <span>{{ post.like_count || 0 }} 赞</span>
          </div>
        </article>
      </div>
    </section>

    <section class="rail-section">
      <h2 class="rail-title">推荐主题</h2>
      <div class="topic-grid">
        <button
          v-for="topic in topicList"
          :key="topic.id"
          type="button"
          class="topic-chip"
          @click="goToTopic(topic.name)"
        >
          {{ topic.name }}
        </button>
      </div>
    </section>

    <section class="rail-section">
      <h2 class="rail-title">继续探索</h2>
      <div class="mini-links">
        <button type="button" class="mini-link" @click="router.push('/hot')">查看热门趋势</button>
        <button type="button" class="mini-link" @click="router.push('/search')">搜索更多主题</button>
      </div>
    </section>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getDomains } from '../../api/auth'
import { getHotPosts } from '../../api/post'

const router = useRouter()
const hotPosts = ref([])
const domains = ref([])

const hotPicks = computed(() => hotPosts.value.slice(0, 3))
const topicList = computed(() => domains.value.slice(0, 8))

async function loadRailData() {
  try {
    const [hotData, domainData] = await Promise.all([
      getHotPosts(6),
      getDomains(),
    ])
    hotPosts.value = hotData.posts || []
    domains.value = domainData.domains || []
  } catch {
    hotPosts.value = []
    domains.value = []
  }
}

function formatDate(value) {
  if (!value) return '最近'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '最近'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

function goToPost(postId) {
  router.push(`/posts/${postId}`)
}

function goToTopic(topic) {
  router.push({ path: '/search', query: { q: topic, type: 'post' } })
}

onMounted(() => {
  loadRailData()
})
</script>

<style scoped>
.right-rail {
  position: sticky;
  top: 96px;
  display: grid;
  gap: 30px;
}

.rail-section {
  padding-top: 4px;
}

.rail-title {
  margin-bottom: 18px;
  font-size: 1.85rem;
  line-height: 1;
  letter-spacing: -0.04em;
}

.pick-list {
  display: grid;
  gap: 18px;
}

.pick-item {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--kr-border);
  cursor: pointer;
}

.pick-topline,
.pick-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--kr-text-muted);
  font-size: 12px;
}

.pick-title {
  margin: 8px 0 10px;
  font-size: 1.35rem;
  line-height: 1.25;
  letter-spacing: -0.02em;
}

.topic-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.topic-chip {
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--kr-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.8);
  color: var(--kr-text);
  font-weight: 700;
}

.mini-links {
  display: grid;
  gap: 12px;
}

.mini-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--kr-text);
  font-weight: 700;
  text-align: left;
}

@media (max-width: 1180px) {
  .right-rail {
    position: static;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 24px;
  }
}
</style>
