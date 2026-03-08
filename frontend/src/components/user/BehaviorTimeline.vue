<template>
  <el-timeline>
    <el-timeline-item
      v-for="b in behaviors"
      :key="b.id"
      :timestamp="b.created_at"
      :type="typeMap[b.behavior_type] || 'info'"
      placement="top"
    >
      <span class="behavior-label">{{ labelMap[b.behavior_type] || b.behavior_type }}</span>
      <router-link :to="`/posts/${b.post_id}`" class="post-link">
        帖子 #{{ b.post_id }}
      </router-link>
      <span v-if="b.duration" class="duration">{{ b.duration }}s</span>
    </el-timeline-item>
    <el-empty v-if="behaviors.length === 0" description="暂无行为记录" />
  </el-timeline>
</template>

<script setup>
defineProps({ behaviors: { type: Array, default: () => [] } })

const typeMap = {
  view: 'primary',
  like: 'success',
  comment: 'warning',
  share: 'danger',
}

const labelMap = {
  view: '浏览',
  like: '点赞',
  comment: '评论',
  share: '分享',
}
</script>

<style scoped>
.behavior-label {
  font-weight: 600;
  margin-right: 8px;
}

.post-link {
  color: #409eff;
}

.post-link:hover {
  text-decoration: underline;
}

.duration {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
}
</style>
