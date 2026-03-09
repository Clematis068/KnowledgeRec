<template>
  <el-select
    v-model="selectedUserId"
    filterable
    placeholder="选择用户"
    :loading="loading"
    style="width: 300px"
  >
    <el-option
      v-for="u in users"
      :key="u.id"
      :label="`${u.username} (ID: ${u.id})`"
      :value="u.id"
    />
  </el-select>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getUserList } from '../../api/user'

const selectedUserId = defineModel({ type: Number, default: null })

const users = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const data = await getUserList(1, 200)
    users.value = data.users
  } finally {
    loading.value = false
  }
})
</script>
