<template>
  <div v-loading="loading" class="post-detail-page">
    <div class="backbar">
      <el-page-header @back="$router.back()" :title="'返回'" />
    </div>

    <template v-if="post">
      <article class="article-shell">
        <header class="article-header">
          <span class="article-kicker">{{ post.domain_name || 'Knowledge' }}</span>
          <h1 class="article-title">{{ post.title }}</h1>
          <p v-if="post.summary" class="article-deck">{{ post.summary }}</p>

          <div class="article-meta">
            <router-link :to="`/users/${post.author_id}`" class="author-link">
              {{ post.author_name || '匿名' }}
            </router-link>
            <span class="meta-item"><el-icon><View /></el-icon>{{ post.view_count || 0 }} 浏览</span>
            <span class="meta-item"><el-icon><Star /></el-icon>{{ post.like_count || 0 }} 点赞</span>
            <span class="meta-item">约 {{ readingMinutes }} 分钟阅读</span>
            <span class="meta-item">{{ post.created_at }}</span>
          </div>

          <div v-if="post.tags && post.tags.length" class="article-tags">
            <el-tag v-for="tag in post.tags" :key="tag" size="small" effect="plain" class="tag-chip">
              {{ tag }}
            </el-tag>
          </div>

          <div v-if="authStore.isLoggedIn" class="manage-bar">
            <template v-if="isOwnPost">
              <el-button size="small" @click="goToEdit">编辑帖子</el-button>
              <el-button size="small" type="danger" @click="handleDeletePost">删除帖子</el-button>
            </template>
            <template v-else>
              <el-button
                size="small"
                :type="blockedAuthor ? 'danger' : 'default'"
                @click="toggleBlockAuthor"
              >
                {{ blockedAuthor ? '取消屏蔽作者' : '屏蔽作者' }}
              </el-button>
              <el-button
                size="small"
                :type="blockedDomain ? 'warning' : 'default'"
                @click="toggleBlockDomain"
              >
                {{ blockedDomain ? '取消屏蔽领域' : '屏蔽领域' }}
              </el-button>
            </template>
          </div>
        </header>

        <div v-if="authStore.isLoggedIn && !isOwnPost" class="reader-actions">
          <el-button
            :type="liked ? 'danger' : 'default'"
            :icon="liked ? StarFilled : Star"
            @click="toggleLike"
          >
            {{ liked ? '已点赞' : '点赞' }}
          </el-button>
          <el-button
            :type="favorited ? 'warning' : 'default'"
            :icon="favorited ? CollectionTag : Collection"
            @click="toggleFavorite"
          >
            {{ favorited ? '已收藏' : '收藏' }}
          </el-button>
          <el-button
            :type="disliked ? 'danger' : 'default'"
            :icon="CircleClose"
            @click="toggleDislike"
          >
            {{ disliked ? '取消不感兴趣' : '不感兴趣' }}
          </el-button>
        </div>

        <div class="article-layout">
          <aside class="article-sidebar">
            <div class="sidebar-block">
              <span class="sidebar-kicker">Article note</span>
              <p class="sidebar-text">采用更窄的正文宽度、更大的标题和更克制的分隔，让阅读更像长文页面。</p>
            </div>
            <div class="sidebar-block">
              <span class="sidebar-kicker">Snapshot</span>
              <ul class="sidebar-list">
                <li class="sidebar-item">领域：{{ post.domain_name || '未分类' }}</li>
                <li class="sidebar-item">阅读时长：约 {{ readingMinutes }} 分钟</li>
                <li class="sidebar-item">互动：{{ post.like_count || 0 }} 赞 / {{ post.view_count || 0 }} 浏览</li>
              </ul>
            </div>
          </aside>

          <section class="article-content">
            <div class="content-block">
              <span class="content-kicker">正文</span>
              <div class="content-body">
                <p v-for="(paragraph, index) in contentParagraphs" :key="`${index}-${paragraph.slice(0, 16)}`" class="content-paragraph">
                  {{ paragraph }}
                </p>
                <p v-if="!contentParagraphs.length" class="content-paragraph">暂无正文内容。</p>
              </div>
            </div>
          </section>
        </div>
      </article>

      <section class="comments-shell">
        <div class="comments-header">
          <span class="comments-kicker">Discussion</span>
          <h2 class="comments-title">评论区</h2>
        </div>
        <CommentSection :post-id="route.params.id" />
      </section>
    </template>

    <el-empty v-else-if="!loading" description="帖子不存在" />
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { View, Star, StarFilled, Collection, CollectionTag, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index'
import { ElMessageBox } from 'element-plus/es/components/message-box/index'
import {
  blockPostAuthor,
  blockPostDomain,
  deletePost,
  getPostDetail,
  recordBehavior,
  unblockPostAuthor,
  unblockPostDomain,
  unlikePost,
  unfavoritePost,
  undislikePost,
  getPostUserStatus,
} from '../api/post'
import { useAuthStore } from '../stores/auth'
import CommentSection from '../components/post/CommentSection.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const post = ref(null)
const loading = ref(false)
const liked = ref(false)
const favorited = ref(false)
const disliked = ref(false)
const blockedAuthor = ref(false)
const blockedDomain = ref(false)
const isOwnPost = computed(() => post.value?.author_id === authStore.userId)
const readingMinutes = computed(() => {
  const contentLength = (post.value?.content || '').replace(/\s+/g, '').length
  return Math.max(1, Math.round(contentLength / 320))
})
const contentParagraphs = computed(() => {
  const content = post.value?.content || ''
  return content
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
})

onMounted(async () => {
  loading.value = true
  try {
    post.value = await getPostDetail(route.params.id)

    if (authStore.isLoggedIn) {
      recordBehavior(route.params.id, 'browse').catch(() => {})

      const status = await getPostUserStatus(route.params.id)
      liked.value = status.liked
      favorited.value = status.favorited
      disliked.value = status.disliked
      blockedAuthor.value = status.blocked_author
      blockedDomain.value = status.blocked_domain
    }
  } finally {
    loading.value = false
  }
})

async function toggleLike() {
  try {
    if (liked.value) {
      await unlikePost(route.params.id)
      liked.value = false
      post.value.like_count = Math.max((post.value.like_count || 0) - 1, 0)
      ElMessage.success('已取消点赞')
    } else {
      await recordBehavior(route.params.id, 'like')
      liked.value = true
      disliked.value = false
      post.value.like_count = (post.value.like_count || 0) + 1
      ElMessage.success('点赞成功')
    }
  } catch {
    // 错误已被 axios 拦截器处理
  }
}

async function toggleFavorite() {
  try {
    if (favorited.value) {
      await unfavoritePost(route.params.id)
      favorited.value = false
      ElMessage.success('已取消收藏')
    } else {
      await recordBehavior(route.params.id, 'favorite')
      favorited.value = true
      disliked.value = false
      ElMessage.success('收藏成功')
    }
  } catch {
    // 错误已被 axios 拦截器处理
  }
}

async function toggleDislike() {
  try {
    if (disliked.value) {
      await undislikePost(route.params.id)
      disliked.value = false
      ElMessage.success('已取消不感兴趣')
    } else {
      await recordBehavior(route.params.id, 'dislike')
      disliked.value = true
      if (liked.value) {
        liked.value = false
        post.value.like_count = Math.max((post.value.like_count || 0) - 1, 0)
      }
      favorited.value = false
      ElMessage.success('已减少此类内容推荐')
    }
  } catch {
    // 错误已被 axios 拦截器处理
  }
}

function goToEdit() {
  router.push(`/posts/${route.params.id}/edit`)
}

async function handleDeletePost() {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确认删除这篇帖子吗？', '删除帖子', {
      type: 'warning',
    })
    await deletePost(route.params.id)
    ElMessage.success('帖子已删除')
    router.replace(`/users/${authStore.userId}`)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      // 错误已被拦截器处理
    }
  }
}

async function toggleBlockAuthor() {
  try {
    if (blockedAuthor.value) {
      await unblockPostAuthor(route.params.id)
      blockedAuthor.value = false
      ElMessage.success('已取消屏蔽作者')
    } else {
      await blockPostAuthor(route.params.id)
      blockedAuthor.value = true
      ElMessage.success('已屏蔽该作者')
      router.replace('/recommend')
    }
  } catch {
    // 错误已被 axios 拦截器处理
  }
}

async function toggleBlockDomain() {
  try {
    if (blockedDomain.value) {
      await unblockPostDomain(route.params.id)
      blockedDomain.value = false
      ElMessage.success('已取消屏蔽领域')
    } else {
      await blockPostDomain(route.params.id)
      blockedDomain.value = true
      ElMessage.success('已屏蔽该领域')
      router.replace('/recommend')
    }
  } catch {
    // 错误已被 axios 拦截器处理
  }
}
</script>

<style scoped>
.post-detail-page {
  max-width: 1120px;
  margin: 0 auto;
  display: grid;
  gap: 24px;
}

.backbar {
  padding-bottom: 12px;
  border-bottom: 1px solid var(--kr-border);
}

.article-shell {
  display: grid;
  gap: 28px;
}

.article-header {
  max-width: 780px;
  padding-bottom: 26px;
  border-bottom: 1px solid var(--kr-border);
}

.article-kicker,
.sidebar-kicker,
.content-kicker,
.comments-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-text-muted);
}

.article-title,
.comments-title {
  letter-spacing: -0.05em;
}

.article-title {
  font-size: clamp(3rem, 6vw, 5.4rem);
  line-height: 0.92;
}

.article-deck,
.sidebar-text,
.sidebar-item,
.content-paragraph {
  color: var(--kr-text-soft);
  line-height: 1.95;
}

.article-deck {
  margin-top: 18px;
  font-size: 1.08rem;
}

.article-meta,
.manage-bar,
.reader-actions,
.article-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

.article-meta {
  margin-top: 20px;
  color: var(--kr-text-muted);
  font-size: 13px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.author-link {
  color: var(--kr-secondary);
  font-weight: 700;
}

.author-link:hover {
  color: var(--kr-primary);
}

.article-tags {
  margin-top: 18px;
}

.tag-chip {
  border-color: var(--kr-border);
  color: var(--kr-text-soft);
  background: transparent;
}

.manage-bar {
  margin-top: 18px;
}

.reader-actions {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--kr-border);
}

.article-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 44px;
  align-items: start;
}

.article-sidebar {
  position: sticky;
  top: 96px;
  display: grid;
  gap: 18px;
}

.sidebar-block,
.content-block,
.comments-shell {
  padding-top: 18px;
  border-top: 1px solid var(--kr-border);
}

.sidebar-list {
  list-style: none;
  display: grid;
  gap: 10px;
  margin-top: 10px;
}

.sidebar-item {
  position: relative;
  padding-left: 18px;
}

.sidebar-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.78em;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--kr-primary);
}

.article-content {
  max-width: 760px;
}

.content-body {
  margin-top: 12px;
}

.content-paragraph {
  margin-bottom: 1.4em;
  font-size: 1.02rem;
  white-space: pre-line;
}

.comments-header {
  margin-bottom: 18px;
}

.comments-title {
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: 0.98;
}

:deep(.el-page-header__content) {
  font-weight: 700;
}

@media (max-width: 980px) {
  .article-layout {
    grid-template-columns: 1fr;
    gap: 28px;
  }

  .article-sidebar {
    position: static;
  }
}

@media (max-width: 720px) {
  .article-title {
    font-size: clamp(2.4rem, 12vw, 4rem);
  }

  .article-meta,
  .manage-bar,
  .reader-actions {
    flex-direction: column;
    align-items: flex-start;
  }

  .reader-actions {
    align-items: stretch;
  }
}
</style>
