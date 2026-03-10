<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

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
      tags: [...(post.tags || [])],
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
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存修改</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.edit-post-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 20px;
}

.tag-input-area {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
</style>
