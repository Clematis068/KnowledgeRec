<script setup>
import { Plus } from '@element-plus/icons-vue'
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'

import { createPost } from '../api/post'
import { useDomains } from '../composables/useDomains'

const router = useRouter()
const { domains, fetchDomains } = useDomains()

const formRef = ref()
const submitting = ref(false)
const createdPostId = ref(null)
const uploadHeaders = { Authorization: `Bearer ${localStorage.getItem('token')}` }

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

function handleUploadSuccess(res) {
  form.value.image_url = res.url
  ElMessage.success('封面上传成功')
}

function beforeUpload(file) {
  const isJpgOrPng =
    file.type === 'image/jpeg' ||
    file.type === 'image/png' ||
    /\.(jpe?g|png)$/i.test(file.name || '')
  if (!isJpgOrPng) {
    ElMessage.error('封面图片仅支持 JPG / PNG 格式')
    return false
  }
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isLt5M) {
    ElMessage.error('图片大小不能超过 5MB')
  }
  return isLt5M
}

watch(
  createdPostId,
  (id) => {
    if (id) {
      router.replace(`/posts/${id}`)
    }
  },
  { flush: 'post' },
)

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const res = await createPost(form.value)
    ElMessage.success('发布成功')
    createdPostId.value = res.id
  } catch {
    submitting.value = false
  }
}

onMounted(fetchDomains)
</script>

<template>
  <div class="create-post-page">
    <el-page-header @back="$router.back()" :title="'返回'" style="margin-bottom: 20px" />
    <h2 class="page-title">发布帖子</h2>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
    >
      <el-form-item label="封面图片">
        <el-upload
          class="cover-uploader"
          action="/api/upload/image"
          accept="image/jpeg,image/png"
          :show-file-list="false"
          :on-success="handleUploadSuccess"
          :before-upload="beforeUpload"
          name="file"
          :headers="uploadHeaders"
        >
          <img v-if="form.image_url" :src="form.image_url" class="cover-preview" />
          <el-icon v-else class="cover-uploader-icon"><Plus /></el-icon>
        </el-upload>
        <div class="upload-tip">建议尺寸 800x450，支持 jpg/png，小于 5MB</div>
      </el-form-item>

      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入帖子标题" maxlength="200" show-word-limit />
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
        <el-button type="primary" :loading="submitting" @click="handleSubmit">发布</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.create-post-page {
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

.create-post-page :deep(.el-form) {
  padding: 24px;
  border: 1px solid var(--kr-border);
  border-radius: 0; /* Follow Carbon Design */
  background: var(--kr-surface);
}

.cover-uploader :deep(.el-upload) {
  border: 1px dashed var(--cds-border-subtle);
  background: var(--cds-layer-01);
  width: 240px;
  height: 135px;
  cursor: pointer;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s;
}

.cover-uploader :deep(.el-upload):hover {
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
