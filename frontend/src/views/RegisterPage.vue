<template>
  <div class="register-page">
    <el-card class="register-card">
      <div class="brand">
        <el-icon :size="28" color="#409eff"><Connection /></el-icon>
        <h2>注册账号</h2>
        <p>加入 KnowledgeRec 知识社区</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" size="large">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少6位" />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" show-password placeholder="再次输入密码" />
        </el-form-item>

        <el-form-item label="性别" prop="gender">
          <el-radio-group v-model="form.gender">
            <el-radio value="male">男</el-radio>
            <el-radio value="female">女</el-radio>
            <el-radio value="other">其他</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-divider>选择你的兴趣标签</el-divider>

        <div v-loading="tagsLoading" class="tags-section">
          <div v-for="group in tagGroups" :key="group.domain.id" class="tag-group">
            <div class="group-label">{{ group.domain.name }}</div>
            <el-checkbox-group v-model="form.tag_ids">
              <el-checkbox
                v-for="tag in group.tags"
                :key="tag.id"
                :value="tag.id"
                :label="tag.name"
              />
            </el-checkbox-group>
          </div>
          <div v-if="!tagGroups.length && !tagsLoading" class="no-tags">暂无标签数据</div>
        </div>
        <div v-if="tagError" class="tag-hint">请至少选择 1 个兴趣标签</div>

        <el-form-item style="margin-top: 20px">
          <el-button type="primary" :loading="loading" style="width: 100%" @click="handleRegister">
            注 册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="footer-link">
        已有账号？<router-link to="/login">去登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { getTags } from '../api/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref()
const loading = ref(false)
const tagsLoading = ref(false)
const tagGroups = ref([])
const tagError = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  gender: 'male',
  tag_ids: [],
})

const validateConfirm = (_rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度 2-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

onMounted(async () => {
  tagsLoading.value = true
  try {
    const data = await getTags()
    tagGroups.value = data.groups || []
  } finally {
    tagsLoading.value = false
  }
})

async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  if (form.tag_ids.length === 0) {
    tagError.value = true
    return
  }
  tagError.value = false

  loading.value = true
  try {
    await authStore.register({
      username: form.username,
      password: form.password,
      gender: form.gender,
      tag_ids: form.tag_ids,
    })
    ElMessage.success('注册成功')
    router.push('/recommend')
  } catch {
    // 错误已被 axios 拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f4fd 0%, #f0f2f5 100%);
  padding: 40px 0;
}

.register-card {
  width: 600px;
}

.brand {
  text-align: center;
  margin-bottom: 20px;
}

.brand h2 {
  margin: 8px 0 4px;
  font-size: 22px;
  color: #303133;
}

.brand p {
  font-size: 13px;
  color: #909399;
}

.tags-section {
  min-height: 60px;
  margin-bottom: 8px;
}

.tag-group {
  margin-bottom: 12px;
}

.group-label {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 6px;
}

.no-tags {
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
}

.tag-hint {
  color: #f56c6c;
  font-size: 12px;
  margin: -4px 0 12px 80px;
}

.footer-link {
  text-align: center;
  font-size: 13px;
  color: #909399;
}

.footer-link a {
  color: #409eff;
  text-decoration: none;
}
</style>
