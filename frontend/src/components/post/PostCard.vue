<template>
  <el-card shadow="never" class="post-card" @click="goToDetail">
    <div class="post-top">
      <span class="post-kicker">Knowledge Post</span>
      <el-tag v-if="post.domain_name" size="small" effect="plain" class="domain-tag">
        {{ post.domain_name }}
      </el-tag>
    </div>

    <h3 class="title">{{ post.title }}</h3>
    <p class="summary">{{ post.summary || '这篇内容还没有摘要，可以点进去查看完整帖子。' }}</p>

    <div v-if="post.tags && post.tags.length" class="tag-row">
      <span v-for="tag in post.tags.slice(0, 4)" :key="tag" class="topic-pill"># {{ tag }}</span>
    </div>

    <div class="post-footer">
      <div class="meta-group">
        <span class="meta-item"><el-icon><View /></el-icon>{{ post.view_count || 0 }}</span>
        <span class="meta-item"><el-icon><Star /></el-icon>{{ post.like_count || 0 }}</span>
      </div>
      <span class="detail-link">阅读全文</span>
    </div>
  </el-card>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  post: { type: Object, required: true },
})

const router = useRouter()

function goToDetail() {
  router.push(`/posts/${props.post.id}`)
}
</script>

<style scoped>
.post-card {
  margin-bottom: 14px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.post-card:hover {
  transform: translateY(-3px);
  border-color: rgba(124, 58, 237, 0.2);
  box-shadow: 0 22px 48px rgba(76, 29, 149, 0.12);
}

.post-top,
.post-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.post-kicker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-primary);
}

.domain-tag {
  border-color: rgba(124, 58, 237, 0.16);
  color: var(--kr-primary-strong);
  background: rgba(124, 58, 237, 0.08);
}

.title {
  margin: 14px 0 10px;
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: -0.03em;
}

.summary {
  margin-bottom: 16px;
  color: var(--kr-text-soft);
  line-height: 1.8;
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}

.topic-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--kr-primary-strong);
  background: rgba(124, 58, 237, 0.08);
}

.meta-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--kr-text-muted);
  font-size: 13px;
}

.detail-link {
  font-weight: 700;
  color: var(--kr-primary-strong);
}
</style>
