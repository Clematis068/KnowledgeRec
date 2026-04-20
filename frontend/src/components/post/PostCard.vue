<template>
  <article class="post-card" @click="goToDetail">
    <div class="card-main">
      <div class="eyebrow-row">
        <span class="eyebrow">{{ post.domain_name || '知识内容' }}</span>
        <span class="eyebrow-sep">·</span>
        <span class="eyebrow">{{ post.author_name || '匿名作者' }}</span>
      </div>

      <h3 class="title">{{ post.title }}</h3>
      <p class="summary">{{ summaryText }}</p>

      <div v-if="previewTags.length" class="tag-row">
        <span v-for="tag in previewTags" :key="tag" class="topic-pill">{{ tag }}</span>
      </div>

      <div class="meta-row">
        <span class="meta-item">{{ formattedDate }}</span>
        <span class="meta-item">{{ post.view_count || 0 }} 浏览</span>
        <span class="meta-item">{{ post.like_count || 0 }} 赞</span>
      </div>
    </div>

    <div class="thumb-card" aria-hidden="true">
      <img class="thumb-image" :src="thumbnailSrc" :alt="post.title || '帖子封面'">
      <div class="thumb-overlay">
        <span class="thumb-domain">{{ thumbnailLabel }}</span>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { createPostThumbnail } from '../../utils/postThumbnail'

const props = defineProps({
  post: { type: Object, required: true },
})

const router = useRouter()

const summaryText = computed(() => (
  props.post.summary || '这篇内容还没有摘要，可以点进去查看完整帖子。'
))

const previewTags = computed(() => (props.post.tags || []).slice(0, 3))

const formattedDate = computed(() => {
  if (!props.post.created_at) return '最近'
  const date = new Date(props.post.created_at)
  if (Number.isNaN(date.getTime())) return '最近'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
  }).format(date)
})

const thumbnailLabel = computed(() => {
  const domainName = props.post.domain_name || '知识内容'
  return domainName.length > 14 ? `${domainName.slice(0, 14)}…` : domainName
})

const thumbnailSrc = computed(() => {
  if (props.post.image_url) {
    return props.post.image_url
  }
  return createPostThumbnail({
    title: props.post.title,
    domainName: props.post.domain_name,
    tags: props.post.tags || [],
    seed: props.post.id || 0,
  })
})

function goToDetail() {
  router.push(`/posts/${props.post.id}`)
}
</script>

<style scoped>
.post-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 224px;
  gap: 32px;
  padding: 24px 0;
  border-bottom: 1px solid var(--cds-border-subtle);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.post-card:hover {
  background: var(--cds-layer-01);
}

.card-main {
  min-width: 0;
}

.eyebrow-row,
.meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.eyebrow,
.meta-item {
  color: var(--cds-text-muted);
  font-size: 12px;
  letter-spacing: 0.16px;
}

.eyebrow-sep {
  color: var(--cds-text-muted);
}

.title {
  margin: 12px 0 10px;
  font-size: clamp(1.5rem, 2.5vw, 2.25rem);
  line-height: 1.2;
  letter-spacing: 0;
  font-weight: 300;
}

.summary {
  max-width: 44rem;
  color: var(--cds-text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.topic-pill {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--cds-blue-10);
  color: var(--cds-link-primary);
  font-size: 12px;
  font-weight: 400;
}

.meta-row {
  margin-top: 16px;
}

.thumb-card {
  position: relative;
  min-height: 148px;
  overflow: hidden;
  background: var(--cds-layer-01);
}

.thumb-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-overlay {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  align-items: center;
}

.thumb-domain {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--cds-text-secondary);
  font-size: 12px;
  font-weight: 400;
  backdrop-filter: blur(6px);
}

@media (max-width: 720px) {
  .post-card {
    grid-template-columns: 1fr;
  }

  .thumb-card {
    min-height: 164px;
  }
}
</style>
