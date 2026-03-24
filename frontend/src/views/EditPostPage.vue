<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'

import { getPostDetail, updatePost } from '../api/post'
import { useDomains } from '../composables/useDomains'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { domains, fetchDomains } = useDomains()

const formRef = ref()
const loading = ref(false)
const submitting = ref(false)

const form = ref({
  title: '',
  domain_id: null,
  content: '',
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  domain_id: [{ required: true, message: '请选择领域', trigger: 'change' }],
  content: [{ required: true, message: '请输入正文', trigger: 'blur' }],
}

async function fetchPost() {
  loading.value = true
  try {
    const post = await getPostDetail(route.params.id)
    if (post.author_id !== authStore.userId) {
      ElMessage.error('只能编辑自己的帖子')
      router.replace(`/posts/${route.params.id}`)
      return
    }

    form.value = {
      title: post.title || '',
      domain_id: post.domain_id || null,
      content: post.content || '',
    }
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await updatePost(route.params.id, form.value)
    ElMessage.success('帖子已更新')
    router.replace(`/posts/${route.params.id}`)
  } catch {
    // 错误已由拦截器处理
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchDomains()
  fetchPost()
})
</script>

<template>
  <div v-loading="loading" class="edit-post-page">
    <el-page-header @back="$router.back()" :title="'返回'" style="margin-bottom: 20px" />
    <h2 class="page-title">编辑帖子</h2>

    <el-form
      v-if="!loading"
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
    >
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入标题" maxlength="200" show-word-limit />
      </el-form-item>

      <el-form-item label="领域" prop="domain_id">
        <el-select v-model="form.domain_id" placeholder="请选择领域" style="width: 100%">
          <el-option v-for="domain in domains" :key="domain.id" :label="domain.name" :value="domain.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="正文" prop="content">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="12"
          placeholder="请输入帖子正文"
          maxlength="10000"
          show-word-limit
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存修改</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.edit-post-page {
  max-width: 980px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.page-title {
  font-size: clamp(2rem, 3vw, 3rem);
  font-weight: 800;
  letter-spacing: -0.05em;
  margin-bottom: 4px;
}

.edit-post-page :deep(.el-form) {
  padding: 24px;
  border: 1px solid var(--kr-border);
  border-radius: 30px;
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay-soft);
}
</style>
