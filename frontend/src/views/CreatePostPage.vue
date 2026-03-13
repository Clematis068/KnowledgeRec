<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'

import { createPost } from '../api/post'
import { useDomains } from '../composables/useDomains'

const router = useRouter()
const { domains, fetchDomains } = useDomains()

const formRef = ref()
const submitting = ref(false)
const createdPostId = ref(null)
const tagInputVisible = ref(false)
const tagInputValue = ref('')
const tagInputRef = ref()

const form = ref({
  title: '',
  domain_id: null,
  tags: [],
  content: '',
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  domain_id: [{ required: true, message: '请选择领域', trigger: 'change' }],
  content: [{ required: true, message: '请输入正文', trigger: 'blur' }],
}

function showTagInput() {
  tagInputVisible.value = true
  nextTick(() => tagInputRef.value?.focus())
}

function confirmTag() {
  const value = tagInputValue.value.trim()
  if (value && !form.value.tags.includes(value)) {
    form.value.tags.push(value)
  }
  tagInputVisible.value = false
  tagInputValue.value = ''
}

function removeTag(tag) {
  form.value.tags = form.value.tags.filter((item) => item !== tag)
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
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入帖子标题" maxlength="200" show-word-limit />
      </el-form-item>

      <el-form-item label="领域" prop="domain_id">
        <el-select v-model="form.domain_id" placeholder="请选择领域" style="width: 100%">
          <el-option v-for="domain in domains" :key="domain.id" :label="domain.name" :value="domain.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="标签">
        <div class="tag-input-area">
          <el-tag
            v-for="tag in form.tags"
            :key="tag"
            closable
            style="margin-right: 6px; margin-bottom: 6px"
            @close="removeTag(tag)"
          >
            {{ tag }}
          </el-tag>
          <el-input
            v-if="tagInputVisible"
            ref="tagInputRef"
            v-model="tagInputValue"
            size="small"
            style="width: 120px"
            placeholder="输入标签"
            @keyup.enter="confirmTag"
            @blur="confirmTag"
          />
          <el-button v-else size="small" @click="showTagInput">+ 添加标签</el-button>
        </div>
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
  border-radius: 30px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(241, 232, 255, 0.92));
  box-shadow: var(--kr-shadow-clay-soft);
}

.tag-input-area {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
</style>
