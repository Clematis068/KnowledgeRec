<template>
  <div v-loading="loading" class="post-detail-page">
    <div class="backbar">
      <el-page-header @back="$router.back()" :title="'返回'" />
    </div>

    <template v-if="post">
      <article class="article-shell">
        <header class="article-header">
          <PostAuthorHero
            :post="post"
            :reading-minutes="readingMinutes"
            :formatted-created-at="formattedCreatedAt"
            :show-follow-button="showFollowButton"
            :is-following="isFollowingAuthor"
            :follow-loading="followLoading"
            @toggle-follow="toggleFollowAuthor"
          />

          <div class="article-meta">
            <span class="meta-item"><el-icon><View /></el-icon>{{ post.view_count || 0 }} 浏览</span>
            <span class="meta-item"><el-icon><Star /></el-icon>{{ post.like_count || 0 }} 点赞</span>
          </div>

          <div v-if="post.tags && post.tags.length" class="article-tags">
            <el-tag v-for="tag in post.tags" :key="tag" size="small" effect="plain" class="tag-chip">
              {{ tag }}
            </el-tag>
          </div>

          <div v-if="post.image_url" class="article-feature-image">
            <img :src="post.image_url" :alt="post.title">
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
              <span class="sidebar-kicker">内容概览</span>
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
              <div class="content-body markdown-body" v-html="renderedContent"></div>
              <p v-if="!renderedContent" class="content-paragraph">暂无正文内容。</p>
            </div>
          </section>
        </div>
      </article>

      <section class="comments-shell">
        <div class="comments-header">
          <span class="comments-kicker">讨论</span>
          <h2 class="comments-title">评论区</h2>
        </div>
        <CommentSection :post-id="route.params.id" />
      </section>
    </template>

    <el-empty v-else-if="!loading" description="帖子不存在" />

    <UnfollowAuthorDialog
      v-model:visible="unfollowDialogVisible"
      :author-name="authorName"
      :author-avatar-src="authorAvatarSrc"
      :submitting="followLoading"
      @confirm="confirmUnfollowAuthor"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { View, Star, StarFilled, Collection, CollectionTag, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus/es/components/message/index'
import { ElMessageBox } from 'element-plus/es/components/message-box/index'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import java from 'highlight.js/lib/languages/java'
import cpp from 'highlight.js/lib/languages/cpp'
import sql from 'highlight.js/lib/languages/sql'
import bash from 'highlight.js/lib/languages/bash'
import json_ from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import 'highlight.js/styles/github.css'
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
import { followUser, getFollowStatus, unfollowUser } from '../api/user'
import { useAuthStore } from '../stores/auth'
import CommentSection from '../components/post/CommentSection.vue'
import PostAuthorHero from '../components/post/PostAuthorHero.vue'
import UnfollowAuthorDialog from '../components/post/UnfollowAuthorDialog.vue'

// 注册 highlight.js 语言
hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('java', java)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('c', cpp)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json_)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('go', go)

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
const isFollowingAuthor = ref(false)
const followLoading = ref(false)
const unfollowDialogVisible = ref(false)
const isOwnPost = computed(() => post.value?.author_id === authStore.userId)
const showFollowButton = computed(() => authStore.isLoggedIn && !isOwnPost.value && !!post.value?.author_id)
const authorName = computed(() => post.value?.author_name || '匿名作者')
const authorAvatarSrc = computed(() => post.value?.author_avatar_url || '')
const readingMinutes = computed(() => {
  const contentLength = (post.value?.content || '').replace(/\s+/g, '').length
  return Math.max(1, Math.round(contentLength / 320))
})
const formattedCreatedAt = computed(() => {
  if (!post.value?.created_at) return '最近'
  const date = new Date(post.value.created_at)
  if (Number.isNaN(date.getTime())) return post.value.created_at
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date)
})
// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: true,
})

// 自定义渲染器
const renderer = new marked.Renderer()

// 代码高亮
renderer.code = ({ text, lang }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  let highlighted
  try {
    highlighted = language !== 'plaintext'
      ? hljs.highlight(text, { language }).value
      : text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  } catch {
    highlighted = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
  const langLabel = lang ? `<span class="code-lang-label">${lang}</span>` : ''
  return `<div class="code-block-wrapper">${langLabel}<pre><code class="hljs language-${language}">${highlighted}</code></pre></div>`
}

// 图片：lazy loading + 自适应（过滤文件名标注）
renderer.image = ({ href, title, text }) => {
  const titleAttr = title ? ` title="${title}"` : ''
  const isFilename = text && /^[\w\-. ]*\.(jpg|jpeg|png|gif|webp|bmp|svg|ico)$/i.test(text.trim())
  const caption = text && !isFilename ? `<figcaption>${text}</figcaption>` : ''
  return `<figure class="article-figure"><img src="${href}" alt="${isFilename ? '' : (text || '')}"${titleAttr} loading="lazy" />${caption}</figure>`
}

marked.use({ renderer })

const renderedContent = computed(() => {
  let content = post.value?.content || ''
  if (!content) return ''
  // 清理残留的互动文本行（评论/点赞/收藏/关注相关）
  content = content.replace(/^.*(?:评论\s*\d*|点赞\s*\d*|收藏\s*\d*|喜欢\s*\d*|分享\s*\d*)\s*$/gm, '')
  // 清理独立的图片文件名行
  content = content.replace(/^[\w\-. ]*\.(?:jpg|jpeg|png|gif|webp|bmp|svg|ico)\s*$/gim, '')
  return marked.parse(content)
})

async function fetchPost() {
  loading.value = true
  try {
    const detail = await getPostDetail(route.params.id)
    post.value = detail

    if (authStore.isLoggedIn) {
      recordBehavior(route.params.id, 'browse').catch(() => {})

      const [status, followStatus] = await Promise.all([
        getPostUserStatus(route.params.id),
        detail.author_id && detail.author_id !== authStore.userId
          ? getFollowStatus(detail.author_id)
          : Promise.resolve(null),
      ])
      liked.value = status.liked
      favorited.value = status.favorited
      disliked.value = status.disliked
      blockedAuthor.value = status.blocked_author
      blockedDomain.value = status.blocked_domain
      isFollowingAuthor.value = followStatus?.is_following ?? false
    } else {
      isFollowingAuthor.value = false
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchPost()
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

async function toggleFollowAuthor() {
  const authorId = post.value?.author_id
  if (!authorId || !showFollowButton.value) return

  if (isFollowingAuthor.value) {
    unfollowDialogVisible.value = true
    return
  }

  followLoading.value = true
  try {
    await followUser(authorId)
    isFollowingAuthor.value = true
    ElMessage.success('关注成功')
  } catch {
    // 错误已被 axios 拦截器处理
  } finally {
    followLoading.value = false
  }
}

async function confirmUnfollowAuthor() {
  const authorId = post.value?.author_id
  if (!authorId || !showFollowButton.value) return

  followLoading.value = true
  try {
    await unfollowUser(authorId)
    isFollowingAuthor.value = false
    unfollowDialogVisible.value = false
    ElMessage.success('已取消关注')
  } catch {
    // 错误已被 axios 拦截器处理
  } finally {
    followLoading.value = false
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
  display: grid;
  gap: 16px;
  padding-bottom: 26px;
  border-bottom: 1px solid var(--kr-border);
}

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

.comments-title {
  letter-spacing: -0.05em;
}

.sidebar-text,
.sidebar-item {
  color: var(--kr-text-soft);
  line-height: 1.95;
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
  color: var(--kr-text-muted);
  font-size: 13px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.article-tags {
  margin-top: 4px;
}

.tag-chip {
  border-color: var(--kr-border);
  color: var(--kr-text-soft);
  background: transparent;
}

.article-feature-image {
  margin-top: 24px;
  width: 100%;
  max-height: 480px;
  overflow: hidden;
  background: var(--cds-layer-01);
}

.article-feature-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
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

/* ── Markdown 正文样式 ── */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 1.6em 0 0.6em;
  font-weight: 700;
  line-height: 1.35;
  color: var(--kr-text);
}

.markdown-body :deep(h1) { font-size: 1.65rem; }
.markdown-body :deep(h2) { font-size: 1.4rem; border-bottom: 1px solid var(--kr-border); padding-bottom: 0.3em; }
.markdown-body :deep(h3) { font-size: 1.2rem; }
.markdown-body :deep(h4) { font-size: 1.08rem; }

.markdown-body :deep(p) {
  margin-bottom: 1.25em;
  font-size: 1.02rem;
  line-height: 1.95;
  color: var(--kr-text-soft);
  word-break: break-word;
}

.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 4px 0;
  cursor: zoom-in;
}

.markdown-body :deep(.article-figure) {
  margin: 1.2em 0;
  text-align: center;
}

.markdown-body :deep(.article-figure figcaption) {
  margin-top: 8px;
  font-size: 0.88rem;
  color: var(--kr-text-muted);
  line-height: 1.5;
}

.markdown-body :deep(blockquote) {
  margin: 1.2em 0;
  padding: 0.8em 1.2em;
  border-left: 3px solid var(--kr-primary);
  background: rgba(0, 0, 0, 0.02);
  color: var(--kr-text-soft);
  border-radius: 0 6px 6px 0;
}

.markdown-body :deep(blockquote p:last-child) {
  margin-bottom: 0;
}

/* ── 代码块 ── */
.markdown-body :deep(.code-block-wrapper) {
  position: relative;
  margin: 1.2em 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--kr-border);
}

.markdown-body :deep(.code-lang-label) {
  position: absolute;
  top: 0;
  right: 0;
  padding: 2px 10px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--kr-text-muted);
  background: rgba(0, 0, 0, 0.04);
  border-radius: 0 8px 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.markdown-body :deep(pre) {
  margin: 0;
  padding: 16px 20px;
  background: #f6f8fa;
  overflow-x: auto;
  font-size: 0.88rem;
  line-height: 1.65;
}

.markdown-body :deep(code) {
  font-family: 'SF Mono', 'Fira Code', 'Consolas', 'Monaco', monospace;
  font-size: 0.88em;
}

.markdown-body :deep(:not(pre) > code) {
  padding: 0.15em 0.4em;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
  color: #d63384;
  font-size: 0.85em;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.8em 0;
  padding-left: 1.8em;
  color: var(--kr-text-soft);
  line-height: 1.9;
}

.markdown-body :deep(li) {
  margin-bottom: 0.3em;
}

.markdown-body :deep(li > ul),
.markdown-body :deep(li > ol) {
  margin: 0.2em 0;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: 1.2em 0;
  border-collapse: collapse;
  font-size: 0.95rem;
  overflow-x: auto;
  display: block;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 10px 14px;
  border: 1px solid var(--kr-border);
  text-align: left;
}

.markdown-body :deep(th) {
  background: rgba(0, 0, 0, 0.03);
  font-weight: 600;
  white-space: nowrap;
}

.markdown-body :deep(hr) {
  margin: 2em 0;
  border: none;
  border-top: 1px solid var(--kr-border);
}

.markdown-body :deep(a) {
  color: var(--kr-primary);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.15s;
}

.markdown-body :deep(a:hover) {
  border-bottom-color: var(--kr-primary);
}

.markdown-body :deep(strong) {
  font-weight: 700;
  color: var(--kr-text);
}

.markdown-body :deep(em) {
  font-style: italic;
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
