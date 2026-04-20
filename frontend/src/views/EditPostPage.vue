<script setup>
import { Plus } from '@element-plus/icons-vue'
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
  image_url: '',
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
      image_url: post.image_url || '',
    }
  } finally {
    loading.value = false
  }
}

function handleUploadSuccess(res) {
  form.value.image_url = res.url
  ElMessage.success('封面上传成功')
}

function beforeUpload(file) {
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isLt5M) {
    ElMessage.error('图片大小不能超过 5MB')
  }
  return isLt5M
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
      <el-form-item label="封面图片">
        <el-upload
          class="cover-uploader"
          action="/api/upload/image"
          :show-file-list="false"
          :on-success="handleUploadSuccess"
          :before-upload="beforeUpload"
          name="file"
          :headers="{ Authorization: `Bearer ${localStorage.getItem('token')}` }"
        >
          <img v-if="form.image_url" :src="form.image_url" class="cover-preview" />
          <el-icon v-else class="cover-uploader-icon"><Plus /></el-icon>
        </el-upload>
        <div class="upload-tip">建议尺寸 800x450，支持 jpg/png，小于 5MB</div>
      </el-form-item>

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
  border-radius: 0;
  background: var(--kr-surface);
}

.cover-uploader {
  border: 1px dashed var(--cds-border-subtle);
  background: var(--cds-layer-01);
  width: 240px;
  height: 135px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s;
}

.cover-uploader:hover {
  border-color: var(--cds-link-primary);
}

.cover-uploader-icon {
  font-size: 28px;
  color: var(--cds-text-muted);
}

.cover-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.upload-tip {
  font-size: 12px;
  color: var(--cds-text-muted);
  margin-top: 8px;
}
</style>
