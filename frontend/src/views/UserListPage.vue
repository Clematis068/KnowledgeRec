<template>
  <div class="user-list-page">
    <div class="page-header">
      <h2>用户列表</h2>
    </div>

    <div v-loading="loading">
      <el-row :gutter="16">
        <el-col v-for="u in users" :key="u.id" :xs="24" :sm="12" :md="8" :lg="6">
          <UserCard :user="u" style="margin-bottom: 16px" />
        </el-col>
      </el-row>
      <el-empty v-if="!loading && users.length === 0" description="暂无用户" />
    </div>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetchUsers"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getUserList } from '../api/user'
import UserCard from '../components/user/UserCard.vue'

const users = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)

async function fetchUsers() {
  loading.value = true
  try {
    const data = await getUserList(page.value, pageSize)
    users.value = data.users
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.user-list-page {
  max-width: 1140px;
  margin: 0 auto;
}

.page-header {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}

.page-header h2 {
  font-size: clamp(2rem, 3vw, 3rem);
  line-height: 0.96;
  letter-spacing: -0.05em;
}

.pagination {
  margin-top: 22px;
  display: flex;
  justify-content: center;
}
</style>
