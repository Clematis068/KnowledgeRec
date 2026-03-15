<script setup>
import { computed } from 'vue'

const props = defineProps({
  post: { type: Object, required: true },
  readingMinutes: { type: Number, default: 1 },
  formattedCreatedAt: { type: String, default: '最近' },
  showFollowButton: { type: Boolean, default: false },
  isFollowing: { type: Boolean, default: false },
  followLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['toggleFollow'])

const domainLabel = computed(() => props.post?.domain_name || '知识内容')
const titleText = computed(() => props.post?.title || '未命名帖子')
const deckText = computed(() => props.post?.summary || '')
const authorName = computed(() => props.post?.author_name || '匿名作者')
const authorInitial = computed(() => authorName.value.charAt(0)?.toUpperCase() || '?')
const authorProfileRoute = computed(() => `/users/${props.post?.author_id}`)
const authorAvatarSrc = computed(() => props.post?.author_avatar_url || undefined)
const followLabel = computed(() => (props.isFollowing ? '已关注' : '关注'))
const followHint = computed(() => (
  props.isFollowing
    ? '已加入关注列表，新帖子会优先出现在关注动态。'
    : '关注后可在关注动态中更快看到 Ta 的新帖子。'
))

function handleToggleFollow() {
  emit('toggleFollow')
}
</script>

<template>
  <div class="author-hero">
    <span class="article-kicker">{{ domainLabel }}</span>

    <h1 class="article-title">
      <span class="title-highlight">{{ titleText }}</span>
    </h1>

    <p v-if="deckText" class="article-deck">{{ deckText }}</p>

    <div class="author-panel">
      <div class="author-row">
        <router-link :to="authorProfileRoute" class="author-avatar-link" :aria-label="`查看 ${authorName} 的个人资料`">
          <el-avatar :size="54" :src="authorAvatarSrc" class="author-avatar">
            {{ authorInitial }}
          </el-avatar>
        </router-link>

        <div class="author-main">
          <div class="author-line">
            <span class="author-label">作者</span>
            <router-link :to="authorProfileRoute" class="author-name-link">
              {{ authorName }}
            </router-link>
          </div>

          <p class="author-hint">{{ followHint }}</p>

          <div class="author-meta">
            <span class="meta-item">{{ readingMinutes }} 分钟阅读</span>
            <span class="meta-dot">·</span>
            <span class="meta-item">{{ formattedCreatedAt }}</span>
          </div>
        </div>
      </div>

      <div v-if="showFollowButton" class="follow-action">
          <el-button
            class="follow-button"
            :class="{ 'is-following': isFollowing }"
            :loading="followLoading"
            @click="handleToggleFollow"
          >
            {{ followLabel }}
          </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.author-hero {
  display: grid;
  gap: 22px;
}

.article-kicker {
  display: inline-flex;
  width: fit-content;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-text-muted);
}

.article-title {
  max-width: 1120px;
  font-family: 'Inter', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: clamp(2.6rem, 5.2vw, 4.8rem);
  font-weight: 800;
  line-height: 1.02;
  letter-spacing: -0.06em;
}

.title-highlight {
  padding: 0;
  background: transparent;
}

.article-deck {
  max-width: 980px;
  color: var(--kr-text-soft);
  font-size: clamp(1.18rem, 2vw, 1.55rem);
  line-height: 1.55;
}

.author-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border: 1px solid var(--kr-border);
  border-radius: 28px;
  background: var(--kr-surface);
}

.author-row {
  display: flex;
  flex: 1;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
}

.author-avatar-link {
  display: inline-flex;
  border-radius: 999px;
}

.author-avatar {
  color: #fff;
  background: linear-gradient(180deg, var(--kr-primary), var(--kr-primary-strong));
  font-size: 0.92rem;
}

.author-main {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.author-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.author-label {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.1);
  color: var(--kr-primary);
  font-size: 12px;
  font-weight: 700;
}

.author-name-link {
  color: var(--kr-text);
  font-size: clamp(1.05rem, 1.35vw, 1.2rem);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.02em;
}

.author-hint {
  margin: 0;
  color: var(--kr-text-soft);
  line-height: 1.7;
}

.author-name-link:hover,
.author-avatar-link:hover {
  color: var(--kr-primary);
}

.follow-action {
  align-self: center;
  flex-shrink: 0;
}

.follow-button {
  min-height: 38px;
  padding-inline: 16px;
  border-color: var(--kr-text);
  color: var(--kr-text);
  background: #fff !important;
  font-weight: 600;
}

.follow-button.is-following {
  border-color: var(--kr-border-strong);
  color: var(--kr-text-soft);
  background: var(--kr-secondary-soft) !important;
}

.author-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--kr-text-muted);
  font-size: 0.9rem;
}

.meta-item,
.meta-dot {
  line-height: 1;
}

@media (max-width: 720px) {
  .article-title {
    font-size: clamp(2.2rem, 10vw, 3.5rem);
  }

  .article-deck {
    font-size: 1.08rem;
  }

  .author-panel {
    flex-direction: column;
    align-items: stretch;
    padding: 16px;
  }

  .author-row,
  .author-line {
    align-items: flex-start;
  }

  .follow-action,
  .follow-button {
    width: 100%;
  }

  .author-meta {
    width: 100%;
  }
}
</style>
