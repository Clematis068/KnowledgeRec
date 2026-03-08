<template>
  <div v-loading="loading" class="user-detail-page">
    <el-page-header @back="$router.back()" :title="'返回'" style="margin-bottom: 20px" />

    <template v-if="user">
      <el-card class="profile-card">
        <div class="profile">
          <el-avatar :size="64" class="avatar">
            {{ user.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <div class="profile-info">
            <h2>{{ user.username }}</h2>
            <p class="email">{{ user.email }}</p>
            <p class="bio">{{ user.bio || '暂无简介' }}</p>
            <el-tag v-if="user.interest_profile" type="success" size="small">
              兴趣: {{ user.interest_profile }}
            </el-tag>
            <p class="time">注册时间: {{ user.created_at }}</p>
          </div>
        </div>
      </el-card>

      <el-card style="margin-top: 16px">
        <template #header>
          <span style="font-weight: 600">行为历史</span>
        </template>
        <BehaviorTimeline :behaviors="behaviors" />
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="用户不存在" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getUserDetail, getUserBehaviors } from '../api/user'
import BehaviorTimeline from '../components/user/BehaviorTimeline.vue'

const route = useRoute()
const user = ref(null)
const behaviors = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  const userId = route.params.id
  try {
    const [u, b] = await Promise.all([
      getUserDetail(userId),
      getUserBehaviors(userId),
    ])
    user.value = u
    behaviors.value = b.behaviors || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.user-detail-page {
  max-width: 900px;
  margin: 0 auto;
}

.profile {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.avatar {
  background: #409eff;
  color: #fff;
  font-size: 24px;
  flex-shrink: 0;
}

.profile-info h2 {
  font-size: 20px;
  margin-bottom: 4px;
}

.email {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.bio {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.time {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 8px;
}
</style>
