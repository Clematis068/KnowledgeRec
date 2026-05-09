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
      <h2 class="rail-title">更多</h2>
      <div class="mini-links">
        <button type="button" class="mini-link" @click="router.push('/hot')">查看热门趋势</button>
        <button type="button" class="mini-link" @click="router.push('/search')">搜索更多主题</button>
      </div>
    </section>

    <footer class="rail-footer">
      <p class="footer-text">
        KnowledgeRec v0.9.0 · 知识社区推荐系统 · 太原理工大学软件学院
        本科毕业设计 · 仅用于学术研究与课程演示，不提供真实信息发布服务 ·
        数据来源：自建模拟数据集（基于公开 Yelp 评估子集脱敏改造）·
        推荐结果由 6 路召回 + GBDT 精排生成，不代表任何机构观点 ·
        反馈邮箱：xjldbhiahia@gmail.com · 项目仓库：github.com/Clematis068/KnowledgeRec ·
        © 2026 Jiale Xu · 版权所有，转载请注明出处
      </p>
      <div class="footer-badges">
        <span class="footer-badge">学术用途</span>
        <span class="footer-badge">非商用</span>
      </div>
    </footer>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getDomains } from '../../api/auth'
import { getRandomPosts } from '../../api/post'

const router = useRouter()
const hotPosts = ref([])
const domains = ref([])

const hotPicks = computed(() => hotPosts.value.slice(0, 3))
const topicList = computed(() => domains.value.slice(0, 8))

async function loadRailData() {
  try {
    const [picksData, domainData] = await Promise.all([
      getRandomPosts(3),
      getDomains(),
    ])
    hotPosts.value = picksData.posts || []
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
  gap: 24px;
}

.rail-section {
  padding: 20px;
  background: var(--cds-layer-01);
  border-top: 3px solid var(--cds-link-primary);
}

.rail-title {
  margin-bottom: 18px;
  font-size: 1.35rem;
  line-height: 1.2;
  letter-spacing: 0;
}

.pick-list {
  display: grid;
  gap: 18px;
}

.pick-item {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--cds-border-subtle);
  cursor: pointer;
}

.pick-topline,
.pick-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--cds-text-muted);
  font-size: 12px;
}

.pick-title {
  margin: 8px 0 10px;
  font-size: 1.1rem;
  line-height: 1.4;
  letter-spacing: 0;
}

.topic-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.topic-chip {
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: var(--cds-background);
  color: var(--cds-link-primary);
  font-weight: 400;
}

.mini-links {
  display: grid;
  gap: 12px;
}

.mini-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--cds-link-primary);
  font-weight: 400;
  text-align: left;
}

.rail-footer {
  padding: 16px 4px 8px;
  border-top: 1px solid var(--cds-border-subtle);
}

.footer-text {
  margin: 0;
  color: var(--cds-text-muted);
  font-size: 12px;
  line-height: 1.7;
  word-break: break-all;
}

.footer-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.footer-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: var(--cds-background);
  border: 1px solid var(--cds-border-subtle);
  color: var(--cds-text-secondary);
  font-size: 11px;
  letter-spacing: 0.32px;
}

@media (max-width: 1180px) {
  .right-rail {
    position: static;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 24px;
  }
}
</style>
