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
        <el-select v-model="form.domain_id" placeholder="请选择领域" style="width: 100%" @change="onDomainChange">
          <el-option v-for="d in domains" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="标签">
        <el-checkbox-group v-model="form.tag_ids">
          <el-checkbox
            v-for="tag in filteredTags"
            :key="tag.id"
            :label="tag.id"
          >
            {{ tag.name }}
          </el-checkbox>
        </el-checkbox-group>
        <div v-if="!form.domain_id" class="tag-hint">请先选择领域</div>
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

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createPost } from '../api/post'
import { getTags } from '../api/auth'

const router = useRouter()

const domains = [
  { id: 1, name: '计算机科学' },
  { id: 2, name: '数学' },
  { id: 3, name: '物理学' },
  { id: 4, name: '生物学' },
  { id: 5, name: '经济学' },
]

const allTags = ref([])
const formRef = ref()
const submitting = ref(false)

const form = ref({
  title: '',
  domain_id: null,
  tag_ids: [],
  content: '',
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  domain_id: [{ required: true, message: '请选择领域', trigger: 'change' }],
  content: [{ required: true, message: '请输入正文', trigger: 'blur' }],
}

const filteredTags = computed(() => {
  if (!form.value.domain_id) return []
  return allTags.value.filter(t => t.domain_id === form.value.domain_id)
})

function onDomainChange() {
  form.value.tag_ids = []
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const res = await createPost(form.value)
    ElMessage.success('发布成功')
    router.push(`/posts/${res.id}`)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const data = await getTags()
    allTags.value = data.tags || data
  } catch {
    // ignore
  }
})
</script>

<style scoped>
.create-post-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 20px;
}

.tag-hint {
  font-size: 12px;
  color: #909399;
}
</style>
