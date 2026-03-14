<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  authorName: { type: String, default: '这位作者' },
  authorAvatarSrc: { type: String, default: '' },
  submitting: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible', 'confirm'])

const authorInitial = computed(() => props.authorName.charAt(0)?.toUpperCase() || '?')

function closeDialog() {
  if (props.submitting) return
  emit('update:visible', false)
}

function confirmAction() {
  if (props.submitting) return
  emit('confirm')
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    width="440px"
    class="unfollow-author-dialog"
    :lock-scroll="false"
    :close-on-click-modal="!submitting"
    :close-on-press-escape="!submitting"
    :show-close="!submitting"
    @update:model-value="emit('update:visible', $event)"
    @close="closeDialog"
  >
    <div class="dialog-shell">
      <div class="dialog-label">关注设置</div>

      <div class="dialog-hero">
        <el-avatar :size="64" :src="authorAvatarSrc" class="dialog-avatar">
          {{ authorInitial }}
        </el-avatar>

        <div class="dialog-copy">
          <div class="dialog-title-row">
            <h3 class="dialog-title">取消关注 {{ authorName }}？</h3>
            <span class="status-pill">已关注</span>
          </div>
          <p class="dialog-description">
            取消后，这位作者的新帖子将不再优先出现在你的“关注”动态中，但你之后仍然可以重新关注。
          </p>
        </div>
      </div>

      <div class="impact-panel">
        <div class="impact-item">
          <span class="impact-dot" />
          <span class="impact-text">关注流里不再优先展示 Ta 的更新</span>
        </div>
        <div class="impact-item">
          <span class="impact-dot" />
          <span class="impact-text">你之前的点赞、收藏和评论不会受影响</span>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog">继续关注</el-button>
        <el-button type="danger" :loading="submitting" @click="confirmAction">取消关注</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
:deep(.unfollow-author-dialog) {
  margin: 16px auto !important;
}

:deep(.unfollow-author-dialog .el-dialog__header) {
  display: none;
}

:deep(.unfollow-author-dialog .el-dialog__body) {
  padding: 24px 24px 18px;
}

:deep(.unfollow-author-dialog .el-dialog__footer) {
  padding: 0 24px 24px;
}

.dialog-shell {
  display: grid;
  gap: 18px;
}

.dialog-label {
  display: inline-flex;
  width: fit-content;
  min-height: 28px;
  align-items: center;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.1);
  color: var(--kr-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.dialog-hero {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.dialog-avatar {
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(180deg, var(--kr-primary), var(--kr-primary-strong));
}

.dialog-copy {
  min-width: 0;
  display: grid;
  gap: 10px;
}

.dialog-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.dialog-title {
  margin: 0;
  font-size: 1.5rem;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.status-pill {
  display: inline-flex;
  min-height: 28px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid var(--kr-border);
  border-radius: 999px;
  color: var(--kr-text-soft);
  background: var(--kr-secondary-soft);
  font-size: 12px;
  font-weight: 700;
}

.dialog-description {
  margin: 0;
  color: var(--kr-text-soft);
  line-height: 1.75;
}

.impact-panel {
  display: grid;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--kr-border);
  border-radius: 20px;
  background: rgba(248, 245, 240, 0.72);
}

.impact-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.impact-dot {
  width: 8px;
  height: 8px;
  margin-top: 8px;
  border-radius: 999px;
  background: var(--kr-primary);
  flex-shrink: 0;
}

.impact-text {
  color: var(--kr-text);
  line-height: 1.65;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 560px) {
  :deep(.unfollow-author-dialog .el-dialog__body) {
    padding: 20px 20px 16px;
  }

  :deep(.unfollow-author-dialog .el-dialog__footer) {
    padding: 0 20px 20px;
  }

  .dialog-hero {
    flex-direction: column;
  }

  .dialog-footer {
    flex-direction: column-reverse;
  }
}
</style>
