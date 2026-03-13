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
  transition: transform 0.2s ease;
}

.user-card:hover {
  transform: translateY(-3px);
}

.user-card:hover .name {
  color: var(--kr-primary);
}

.user-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.avatar {
  background: linear-gradient(135deg, var(--kr-secondary), var(--kr-primary));
  color: #fff;
  flex-shrink: 0;
}

.name {
  font-size: 15px;
  font-weight: 800;
  color: var(--kr-text);
}

.bio {
  font-size: 12px;
  color: var(--kr-text-soft);
  margin-top: 4px;
  line-height: 1.6;
}

.interest {
  margin-top: 12px;
}
</style>
