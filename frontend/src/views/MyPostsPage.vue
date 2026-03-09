<template>
  <div class="my-posts-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">我的发帖</h2>
        <p class="page-subtitle">集中查看、编辑和删除自己发布的内容</p>
      </div>
      <el-button type="primary" @click="$router.push('/create-post')">去发帖</el-button>
    </div>

    <div v-loading="loading">
      <div v-for="post in posts" :key="post.id" class="post-item">
        <PostCard :post="post" />
        <div class="post-actions">
          <el-button size="small" @click="goToEditPost(post.id)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDeletePost(post.id)">删除</el-button>
        </div>
      </div>
      <el-empty v-if="!loading && posts.length === 0" description="你还没有发过帖子" />
    </div>

    <div v-if="total > pageSize" class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetchPosts"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { getUserPosts } from '../api/user'
import { deletePost } from '../api/post'
import PostCard from '../components/post/PostCard.vue'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const posts = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)

async function fetchPosts() {
  loading.value = true
  try {
    const data = await getUserPosts(authStore.userId, page.value, pageSize)
    posts.value = data.posts || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function goToEditPost(postId) {
  router.push(`/posts/${postId}/edit`)
}

async function handleDeletePost(postId) {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确认删除这篇帖子吗？', '删除帖子', {
      type: 'warning',
    })
    await deletePost(postId)
    ElMessage.success('帖子已删除')
    if (posts.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await fetchPosts()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      // 错误已由拦截器处理
    }
  }
}

onMounted(fetchPosts)
</script>

<style scoped>
.my-posts-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.page-subtitle {
  font-size: 13px;
  color: #909399;
}

.post-item {
  margin-bottom: 12px;
}

.post-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin: -2px 0 12px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
