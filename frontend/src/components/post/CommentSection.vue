<template>
  <div class="comment-section">
    <div v-if="authStore.isLoggedIn" class="comment-input">
      <div v-if="replyTo" class="reply-hint">
        回复 @{{ replyTo.username }}
        <el-button text size="small" @click="cancelReply">取消</el-button>
      </div>
      <el-input
        ref="commentInputRef"
        v-model="commentText"
        type="textarea"
        :rows="3"
        :placeholder="replyTo ? `回复 @${replyTo.username}...` : '写下你的评论...'"
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
        {{ replyTo ? '回复' : '发表评论' }}
      </el-button>
    </div>
    <div v-else class="login-tip">
      <router-link to="/login">登录</router-link>后即可评论
    </div>

    <div v-loading="loading" class="comment-list">
      <template v-for="c in commentTree" :key="c.id">
        <div class="comment-item">
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
            <el-button
              v-if="authStore.isLoggedIn"
              text size="small" class="reply-btn"
              @click="handleReply(c)"
            >回复</el-button>
            <el-button
              v-if="authStore.userId === c.user_id"
              text size="small" class="delete-btn"
              @click="handleDeleteComment(c)"
            >删除</el-button>
          </div>
        </div>

        <!-- 子评论 -->
        <div v-if="c.children?.length" class="reply-thread">
          <div v-for="r in c.children" :key="r.id" class="comment-item reply-item">
            <el-avatar :size="28" class="comment-avatar comment-avatar--sm">
              {{ r.username?.charAt(0)?.toUpperCase() }}
            </el-avatar>
            <div class="comment-body">
              <div class="comment-meta">
                <router-link :to="`/users/${r.user_id}`" class="comment-user">
                  {{ r.username }}
                </router-link>
                <span v-if="r.reply_to_username" class="reply-tag">回复 @{{ r.reply_to_username }}</span>
                <span class="comment-time">{{ r.created_at }}</span>
              </div>
              <div class="comment-text">{{ r.comment_text }}</div>
              <el-button
                v-if="authStore.isLoggedIn"
                text size="small" class="reply-btn"
                @click="handleReply(r)"
              >回复</el-button>
              <el-button
                v-if="authStore.userId === r.user_id"
                text size="small" class="delete-btn"
                @click="handleDeleteComment(r)"
              >删除</el-button>
            </div>
          </div>
        </div>
      </template>
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
import { ref, computed, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index'
import { ElMessageBox } from 'element-plus/es/components/message-box/index'
import { deleteComment, getComments, postComment } from '../../api/post'
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
const replyTo = ref(null)
const commentInputRef = ref(null)

// 将扁平评论列表转为两级树：顶级评论 + 子评论（所有回复平铺到根评论下）
const commentTree = computed(() => {
  const map = {}
  const roots = []

  // 第一遍：建索引
  for (const c of comments.value) {
    map[c.id] = { ...c, children: [] }
  }

  // 第二遍：挂载子评论（找到最顶级的祖先）
  for (const c of comments.value) {
    const node = map[c.id]
    if (!c.parent_id || !map[c.parent_id]) {
      roots.push(node)
    } else {
      // 找到根祖先
      let ancestor = map[c.parent_id]
      while (ancestor && ancestor.parent_id && map[ancestor.parent_id]) {
        ancestor = map[ancestor.parent_id]
      }
      ancestor.children.push(node)
    }
  }

  return roots
})

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

function handleReply(comment) {
  replyTo.value = comment
  nextTick(() => {
    commentInputRef.value?.focus()
  })
}

function cancelReply() {
  replyTo.value = null
}

async function handleSubmit() {
  if (!commentText.value.trim()) return
  submitting.value = true
  try {
    const parentId = replyTo.value ? replyTo.value.id : null
    await postComment(props.postId, commentText.value.trim(), parentId)
    commentText.value = ''
    replyTo.value = null
    page.value = 1
    await fetchComments()
    ElMessage.success('评论成功')
  } finally {
    submitting.value = false
  }
}

async function handleDeleteComment(comment) {
  try {
    await ElMessageBox.confirm('确认删除这条评论吗？', '删除评论', {
      type: 'warning',
    })
    await deleteComment(props.postId, comment.id)
    await fetchComments()
    ElMessage.success('评论已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      // 错误已由拦截器处理
    }
  }
}

onMounted(fetchComments)
</script>

<style scoped>
.comment-section {
  display: grid;
  gap: 18px;
}

.comment-input {
  margin-bottom: 4px;
  padding: 18px;
  border-radius: 24px;
  background: var(--kr-surface-alt);
  box-shadow: var(--kr-shadow-clay-soft);
}

.reply-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--kr-secondary);
}

.login-tip {
  margin-bottom: 4px;
  color: var(--kr-text-soft);
  font-size: 14px;
}

.login-tip a {
  color: var(--kr-secondary);
  font-weight: 700;
}

.comment-list {
  display: grid;
  gap: 10px;
}

.comment-item {
  display: flex;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 24px;
  border: 1px solid var(--kr-border);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--kr-shadow-clay-soft);
}

/* 子评论缩进区域 */
.reply-thread {
  margin-left: 44px;
  padding-left: 16px;
  border-left: 2px solid var(--kr-border);
  display: grid;
  gap: 8px;
}

.reply-item {
  padding: 12px 14px;
  border-radius: 18px;
  box-shadow: none;
  background: var(--kr-surface-alt, #fafafa);
}

.comment-avatar {
  background: linear-gradient(135deg, var(--kr-secondary), var(--kr-primary));
  color: #fff;
  font-size: 14px;
  flex-shrink: 0;
}

.comment-avatar--sm {
  font-size: 12px;
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
  flex-wrap: wrap;
}

.comment-user {
  font-size: 14px;
  font-weight: 800;
  color: var(--kr-text);
  text-decoration: none;
}

.comment-user:hover {
  color: var(--kr-primary);
}

.comment-time {
  font-size: 12px;
  color: var(--kr-text-muted);
}

.comment-text {
  font-size: 14px;
  line-height: 1.75;
  color: var(--kr-text-soft);
  word-break: break-word;
}

.reply-tag {
  color: var(--kr-secondary);
  font-size: 13px;
  font-weight: 700;
}

.reply-btn {
  margin-top: 6px;
  color: var(--kr-text-muted);
  padding: 0;
}

.reply-btn:hover {
  color: var(--kr-primary);
}

.delete-btn {
  margin-top: 6px;
  color: var(--kr-danger);
  padding: 0;
}

.delete-btn:hover {
  color: var(--kr-danger);
}

.comment-pagination {
  margin-top: 8px;
  display: flex;
  justify-content: center;
}
</style>
