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
      <span v-if="b.comment_text" class="comment-preview">{{ b.comment_text }}</span>
      <span v-if="b.duration" class="duration">{{ b.duration }}s</span>
    </el-timeline-item>
    <el-empty v-if="behaviors.length === 0" description="暂无行为记录" />
  </el-timeline>
</template>

<script setup>
defineProps({ behaviors: { type: Array, default: () => [] } })

const typeMap = {
  browse: 'primary',
  like: 'success',
  favorite: 'warning',
  comment: 'warning',
  dislike: 'danger',
}

const labelMap = {
  browse: '浏览',
  like: '点赞',
  favorite: '收藏',
  comment: '评论',
  dislike: '不感兴趣',
}
</script>

<style scoped>
:deep(.el-timeline-item__node) {
  box-shadow: 0 0 0 4px rgba(255, 143, 122, 0.18);
}

:deep(.el-timeline-item__tail) {
  border-left: 2px solid rgba(126, 200, 227, 0.3);
}

.behavior-label {
  font-weight: 800;
  margin-right: 8px;
  color: var(--kr-text);
}

.post-link {
  color: var(--kr-secondary);
  font-weight: 700;
}

.post-link:hover {
  text-decoration: underline;
}

.duration {
  font-size: 12px;
  color: var(--kr-text-muted);
  margin-left: 8px;
}

.comment-preview {
  display: inline-block;
  margin-left: 8px;
  font-size: 13px;
  color: var(--kr-text-soft);
}
</style>
