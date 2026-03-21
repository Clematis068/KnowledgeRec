<template>
  <div class="skeleton-list">
    <div v-for="i in count" :key="i" class="skeleton-card">
      <div class="skeleton-main">
        <div class="skeleton-eyebrow">
          <el-skeleton-item variant="text" style="width: 60px; height: 14px" />
          <el-skeleton-item variant="text" style="width: 80px; height: 14px" />
        </div>
        <el-skeleton-item variant="h1" style="width: 70%; height: 28px; margin: 10px 0 12px" />
        <div class="skeleton-summary">
          <el-skeleton-item variant="text" style="width: 100%; height: 14px" />
          <el-skeleton-item variant="text" style="width: 85%; height: 14px" />
        </div>
        <div class="skeleton-tags">
          <el-skeleton-item variant="button" style="width: 56px; height: 30px; border-radius: 999px" />
          <el-skeleton-item variant="button" style="width: 72px; height: 30px; border-radius: 999px" />
          <el-skeleton-item variant="button" style="width: 48px; height: 30px; border-radius: 999px" />
        </div>
        <div class="skeleton-meta">
          <el-skeleton-item variant="text" style="width: 64px; height: 13px" />
          <el-skeleton-item variant="text" style="width: 48px; height: 13px" />
          <el-skeleton-item variant="text" style="width: 48px; height: 13px" />
          <el-skeleton-item variant="text" style="width: 56px; height: 13px" />
        </div>
      </div>
      <div class="skeleton-thumb">
        <el-skeleton-item variant="image" style="width: 100%; height: 100%" />
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  count: {
    type: Number,
    default: 4,
  },
})
</script>

<style scoped>
.skeleton-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 208px;
  gap: 24px;
  padding: 26px 0;
  border-bottom: 1px solid var(--kr-border, #eee);
}

.skeleton-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.skeleton-eyebrow {
  display: flex;
  gap: 10px;
}

.skeleton-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 44rem;
}

.skeleton-tags {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.skeleton-meta {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.skeleton-thumb {
  width: 208px;
  height: 148px;
  border-radius: 10px;
  overflow: hidden;
  background: #f3f2ee;
}

@media (max-width: 720px) {
  .skeleton-card {
    grid-template-columns: 1fr;
  }

  .skeleton-thumb {
    width: 100%;
    height: 164px;
  }
}
</style>
