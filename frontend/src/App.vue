<script setup>
import { ref } from 'vue'
import axios from 'axios'

const question = ref('')
const reply = ref('')
const loading = ref(false)

async function askQwen() {
  if (!question.value.trim()) return
  loading.value = true
  reply.value = ''
  try {
    const res = await axios.post('/api/llm/chat', {
      message: question.value,
    })
    reply.value = res.data.reply
  } catch (err) {
    reply.value = '请求失败：' + (err.response?.data?.error || err.message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="container">
    <h1>知识社区推荐系统</h1>
    <p class="subtitle">千问 API 连通性测试</p>

    <div class="input-area">
      <textarea
        v-model="question"
        placeholder="输入你的问题..."
        rows="3"
        @keydown.ctrl.enter="askQwen"
      />
      <button @click="askQwen" :disabled="loading">
        {{ loading ? '思考中...' : '发送' }}
      </button>
    </div>

    <div v-if="reply" class="reply-area">
      <h3>千问回复：</h3>
      <div class="reply-content">{{ reply }}</div>
    </div>
  </div>
</template>

<style scoped>
.container {
  max-width: 700px;
  margin: 40px auto;
  padding: 0 20px;
  font-family: system-ui, sans-serif;
}

h1 {
  margin-bottom: 4px;
}

.subtitle {
  color: #888;
  margin-bottom: 24px;
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

textarea {
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 15px;
  resize: vertical;
}

button {
  align-self: flex-end;
  padding: 10px 28px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  cursor: pointer;
}

button:hover {
  background: #337ecc;
}

button:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.reply-area {
  margin-top: 24px;
  padding: 16px;
  background: #f9f9f9;
  border-radius: 8px;
  border: 1px solid #eee;
}

.reply-content {
  white-space: pre-wrap;
  line-height: 1.6;
}
</style>
