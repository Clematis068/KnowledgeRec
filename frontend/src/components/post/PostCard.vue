<template>
  <el-card shadow="hover" class="post-card" @click="$router.push(`/posts/${post.id}`)">
    <div class="post-header">
      <span class="title">{{ post.title }}</span>
      <el-tag v-if="post.domain_id" size="small">领域 {{ post.domain_id }}</el-tag>
    </div>
    <p class="summary">{{ post.summary || '暂无摘要' }}</p>
    <div class="post-meta">
      <span><el-icon><View /></el-icon> {{ post.view_count || 0 }}</span>
      <span><el-icon><Star /></el-icon> {{ post.like_count || 0 }}</span>
      <span v-if="post.tags && post.tags.length">
        <el-tag v-for="tag in post.tags.slice(0, 3)" :key="tag" size="small" type="info" class="tag">
          {{ tag }}
        </el-tag>
      </span>
    </div>
  </el-card>
</template>

<script setup>
defineProps({ post: { type: Object, required: true } })
</script>

<style scoped>
.post-card {
  margin-bottom: 12px;
  cursor: pointer;
}

.post-card:hover .title {
  color: #409eff;
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.summary {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.post-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #909399;
}

.post-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tag {
  margin-right: 4px;
}
</style>
