<template>
  <div v-loading="loading" class="post-detail-page">
    <el-page-header @back="$router.back()" :title="'返回'" style="margin-bottom: 20px" />

    <template v-if="post">
      <el-card>
        <template #header>
          <div class="detail-header">
            <h2>{{ post.title }}</h2>
            <div class="meta">
              <el-tag size="small">{{ post.domain_name }}</el-tag>
              <router-link :to="`/users/${post.author_id}`" class="author-link">
                {{ post.author_name || '匿名' }}
              </router-link>
              <span><el-icon><View /></el-icon> {{ post.view_count }}</span>
              <span><el-icon><Star /></el-icon> {{ post.like_count }}</span>
              <span>{{ post.created_at }}</span>
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
          </div>
        </template>

        <div v-if="post.tags && post.tags.length" class="tags-area">
          <el-tag v-for="tag in post.tags" :key="tag" size="small" type="info" class="tag">
            {{ tag }}
          </el-tag>
        </div>

        <div v-if="authStore.isLoggedIn && !isOwnPost" class="action-bar">
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

        <div v-if="post.summary" class="summary-section">
          <h4>摘要</h4>
          <p>{{ post.summary }}</p>
        </div>

        <div class="content-section">
          <h4>正文</h4>
          <div class="content-body">{{ post.content }}</div>
        </div>
      </el-card>

      <el-card style="margin-top: 16px">
        <template #header>
              <span style="font-weight: 600">评论区</span>
            </template>
        <CommentSection :post-id="route.params.id" />
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="帖子不存在" />
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { View, Star, StarFilled, Collection, CollectionTag, CircleClose } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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

onMounted(async () => {
  loading.value = true
  try {
    post.value = await getPostDetail(route.params.id)

    if (authStore.isLoggedIn) {
      // 记录浏览行为 (fire-and-forget)
      recordBehavior(route.params.id, 'browse').catch(() => {})

      // 获取点赞/收藏状态
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
  max-width: 900px;
  margin: 0 auto;
}

.detail-header h2 {
  font-size: 20px;
  margin-bottom: 10px;
}

.manage-bar {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: #909399;
}

.meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.author-link {
  color: #909399;
  text-decoration: none;
}

.author-link:hover {
  color: #409eff;
}

.tags-area {
  margin-bottom: 16px;
}

.tag {
  margin-right: 6px;
}

.action-bar {
  margin-bottom: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.summary-section {
  margin-bottom: 20px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
}

.summary-section h4 {
  font-size: 14px;
  margin-bottom: 6px;
  color: #606266;
}

.summary-section p {
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
}

.content-section h4 {
  font-size: 14px;
  margin-bottom: 8px;
  color: #606266;
}

.content-body {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  color: #303133;
}
</style>
