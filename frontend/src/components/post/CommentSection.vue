<template>
  <div class="comment-section">
    <div v-if="authStore.isLoggedIn" class="comment-input">
      <el-input
        v-model="commentText"
        type="textarea"
        :rows="3"
        placeholder="写下你的评论..."
        maxlength="500"
        show-word-limit
      />
      <el-button
        type="primary"
        :disabled="!commentText.trim()"
        :loading="submitting"
        style="margin-top: 8px"
        @click="handleSubmit"
      >
        发表评论
      </el-button>
    </div>
    <div v-else class="login-tip">
      <router-link to="/login">登录</router-link>后即可评论
    </div>

    <div v-loading="loading" class="comment-list">
      <div v-for="c in comments" :key="c.id" class="comment-item">
        <el-avatar :size="32" class="comment-avatar">
          {{ c.username?.charAt(0)?.toUpperCase() }}
        </el-avatar>
        <div class="comment-body">
          <div class="comment-meta">
            <router-link :to="`/users/${c.user_id}`" class="comment-user">
              {{ c.username }}
            </router-link>
            <span class="comment-time">{{ c.created_at }}</span>
          </div>
          <div class="comment-text">{{ c.comment_text }}</div>
        </div>
      </div>
      <el-empty v-if="!loading && comments.length === 0" description="暂无评论" />
    </div>

    <div v-if="total > pageSize" class="comment-pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchComments"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getComments, postComment } from '../../api/post'
import { useAuthStore } from '../../stores/auth'

const props = defineProps({
  postId: { type: [Number, String], required: true },
})

const authStore = useAuthStore()
const comments = ref([])
const commentText = ref('')
const loading = ref(false)
const submitting = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)

async function fetchComments() {
  loading.value = true
  try {
    const data = await getComments(props.postId, page.value, pageSize)
    comments.value = data.comments
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!commentText.value.trim()) return
  submitting.value = true
  try {
    await postComment(props.postId, commentText.value.trim())
    commentText.value = ''
    page.value = 1
    await fetchComments()
    ElMessage.success('评论成功')
  } finally {
    submitting.value = false
  }
}

onMounted(fetchComments)
</script>

<style scoped>
.comment-input {
  margin-bottom: 20px;
}

.login-tip {
  margin-bottom: 20px;
  color: #909399;
  font-size: 14px;
}

.login-tip a {
  color: #409eff;
}

.comment-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-avatar {
  background: #409eff;
  color: #fff;
  font-size: 14px;
  flex-shrink: 0;
}

.comment-body {
  flex: 1;
  min-width: 0;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.comment-user {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  text-decoration: none;
}

.comment-user:hover {
  color: #409eff;
}

.comment-time {
  font-size: 12px;
  color: #c0c4cc;
}

.comment-text {
  font-size: 14px;
  line-height: 1.6;
  color: #606266;
  word-break: break-word;
}

.comment-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
