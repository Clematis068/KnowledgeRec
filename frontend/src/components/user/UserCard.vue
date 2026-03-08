<template>
  <el-card shadow="hover" class="user-card" @click="$router.push(`/users/${user.id}`)">
    <div class="user-info">
      <el-avatar :size="48" class="avatar">
        {{ user.username?.charAt(0)?.toUpperCase() }}
      </el-avatar>
      <div class="info">
        <div class="name">{{ user.username }}</div>
        <div class="bio">{{ user.bio || '这个用户很懒，什么都没写' }}</div>
      </div>
    </div>
    <div v-if="user.interest_profile" class="interest">
      <el-tag size="small" type="success">{{ user.interest_profile }}</el-tag>
    </div>
  </el-card>
</template>

<script setup>
defineProps({ user: { type: Object, required: true } })
</script>

<style scoped>
.user-card {
  cursor: pointer;
}

.user-card:hover .name {
  color: #409eff;
}

.user-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.avatar {
  background: #409eff;
  color: #fff;
  flex-shrink: 0;
}

.name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.bio {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.interest {
  margin-top: 10px;
}
</style>
