<template>
  <article class="rec-card">
    <div class="card-main">
      <div class="eyebrow-row">
        <span class="eyebrow">{{ item.domain_name || '推荐内容' }}</span>
        <span class="eyebrow-sep">·</span>
        <span class="eyebrow">{{ item.author_name || '知识推荐' }}</span>
      </div>

      <router-link :to="`/posts/${item.post_id}`" class="title">
        {{ item.title || `帖子 #${item.post_id}` }}
      </router-link>

      <p class="summary">{{ summaryText }}</p>

      <div v-if="previewTags.length" class="tag-row">
        <span v-for="tag in previewTags" :key="tag" class="topic-pill">{{ tag }}</span>
      </div>

      <div class="meta-row">
        <span class="meta-item">{{ formattedDate }}</span>
        <span class="meta-item">{{ item.view_count || 0 }} 浏览</span>
        <span class="meta-item">{{ item.like_count || 0 }} 赞</span>
        <span class="meta-item">推荐分 {{ displayScore }}</span>
      </div>

      <div class="action-row">
        <button type="button" class="action-link" @click="$emit('showReason', item.post_id)">
          推荐理由
        </button>
        <button
          v-if="allowFeedback"
          type="button"
          class="action-link action-link--danger"
          @click="$emit('dislike', item.post_id)"
        >
          不感兴趣
        </button>
      </div>
    </div>

    <router-link :to="`/posts/${item.post_id}`" class="thumb-card" aria-label="查看帖子">
      <img class="thumb-image" :src="thumbnailSrc" :alt="item.title || '帖子封面'">
      <div class="thumb-overlay">
        <span class="thumb-domain">{{ thumbnailLabel }}</span>
      </div>
    </router-link>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { createPostThumbnail } from '../../utils/postThumbnail'

const props = defineProps({
  item: { type: Object, required: true },
  allowFeedback: { type: Boolean, default: false },
})

defineEmits(['showReason', 'dislike'])

const summaryText = computed(() => (
  props.item.summary || '这篇内容与你当前的阅读兴趣和行为模式高度相关，适合继续展开阅读。'
))

const previewTags = computed(() => (props.item.tags || []).slice(0, 3))

const displayScore = computed(() => {
  const score = props.item.final_score ?? props.item.score
  return score == null ? '--' : score.toFixed(3)
})

const formattedDate = computed(() => {
  if (!props.item.created_at) return '最近'
  const date = new Date(props.item.created_at)
  if (Number.isNaN(date.getTime())) return '最近'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
  }).format(date)
})

const thumbnailLabel = computed(() => {
  const domainName = props.item.domain_name || '知识内容'
  return domainName.length > 14 ? `${domainName.slice(0, 14)}…` : domainName
})

const thumbnailSrc = computed(() => createPostThumbnail({
  title: props.item.title,
  domainName: props.item.domain_name,
  tags: props.item.tags || [],
  seed: props.item.post_id || 0,
}))
</script>

<style scoped>
.rec-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 208px;
  gap: 24px;
  padding: 26px 0;
  border-bottom: 1px solid var(--kr-border);
}

.card-main {
  min-width: 0;
}

.eyebrow-row,
.meta-row,
.action-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.eyebrow,
.meta-item {
  color: var(--kr-text-muted);
  font-size: 13px;
}

.eyebrow-sep {
  color: var(--kr-text-muted);
}

.title {
  display: inline-block;
  margin: 10px 0 12px;
  font-size: clamp(1.9rem, 3vw, 2.55rem);
  line-height: 1.06;
  letter-spacing: -0.04em;
}

.title:hover {
  color: var(--kr-text);
}

.summary {
  max-width: 44rem;
  color: var(--kr-text-soft);
  line-height: 1.82;
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
  background: rgba(255, 255, 255, 0.78);
  color: var(--kr-text);
  font-size: 12px;
  font-weight: 700;
}

.meta-row {
  margin-top: 16px;
}

.action-row {
  margin-top: 16px;
}

.action-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--kr-text);
  font-weight: 700;
}

.action-link--danger {
  color: var(--kr-text-muted);
}

.thumb-card {
  position: relative;
  display: block;
  min-height: 148px;
  overflow: hidden;
  border: 1px solid var(--kr-border);
  background: #f3f2ee;
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
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--kr-text-soft);
  font-size: 12px;
  font-weight: 700;
  backdrop-filter: blur(6px);
}

@media (max-width: 720px) {
  .rec-card {
    grid-template-columns: 1fr;
  }

  .thumb-card {
    min-height: 164px;
  }
}
</style>
