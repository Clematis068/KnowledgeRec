<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  saving: {
    type: Boolean,
    default: false,
  },
  profile: {
    type: Object,
    required: true,
  },
  tagGroups: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:visible', 'save'])

const localForm = reactive({
  bio: '',
  gender: '',
  email: '',
  tag_ids: [],
})

const selectedTags = computed(() => {
  const selected = []
  const selectedIds = new Set(localForm.tag_ids)
  for (const group of props.tagGroups) {
    for (const tag of group.tags || []) {
      if (selectedIds.has(tag.id)) {
        selected.push(tag)
      }
    }
  }
  return selected
})

function removeTag(tagId) {
  localForm.tag_ids = localForm.tag_ids.filter((id) => id !== tagId)
}

function getGroupSelected(group) {
  const ids = new Set((group.tags || []).map((tag) => tag.id))
  return localForm.tag_ids.filter((id) => ids.has(id))
}

function setGroupSelected(group, nextIds) {
  const ids = new Set((group.tags || []).map((tag) => tag.id))
  const others = localForm.tag_ids.filter((id) => !ids.has(id))
  localForm.tag_ids = [...others, ...nextIds]
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    localForm.bio = props.profile.bio || ''
    localForm.gender = props.profile.gender || ''
    localForm.email = props.profile.email || ''
    localForm.tag_ids = [...(props.profile.tag_ids || [])]
  },
  { immediate: true },
)

function closeDialog() {
  emit('update:visible', false)
}

function saveProfile() {
  emit('save', {
    bio: localForm.bio.trim(),
    gender: localForm.gender,
    email: localForm.email.trim(),
    tag_ids: [...localForm.tag_ids],
  })
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="编辑资料"
    width="780px"
    class="profile-edit-dialog"
    draggable
    overflow
    :lock-scroll="false"
    @update:model-value="emit('update:visible', $event)"
    @close="closeDialog"
  >
    <div class="dialog-layout">
      <section class="panel overview-panel">
        <div class="panel-head">
          <h3>资料概览</h3>
          <p>简介和兴趣标签会直接更新；邮箱变更需要额外验证码确认。</p>
        </div>

        <div class="field-block">
          <label class="field-label" for="profile-bio">简介</label>
          <el-input
            id="profile-bio"
            v-model="localForm.bio"
            type="textarea"
            :rows="4"
            maxlength="200"
            show-word-limit
            placeholder="介绍一下你的研究方向、关注主题或社区身份。"
          />
        </div>

        <div class="field-grid">
          <div class="field-block">
            <label class="field-label" for="profile-gender">性别</label>
            <el-select id="profile-gender" v-model="localForm.gender" class="full-width">
              <el-option label="男" value="male" />
              <el-option label="女" value="female" />
              <el-option label="其他" value="other" />
            </el-select>
          </div>

          <div class="field-block">
            <label class="field-label" for="profile-email">邮箱</label>
            <el-input id="profile-email" v-model="localForm.email" placeholder="name@example.com" />
          </div>
        </div>

        <div class="selected-panel">
          <div class="selected-head">
            <span class="field-label">已选兴趣</span>
            <span class="selected-count">{{ localForm.tag_ids.length }} 个</span>
          </div>
          <div v-if="selectedTags.length" class="selected-tags">
            <el-tag
              v-for="tag in selectedTags"
              :key="tag.id"
              closable
              size="small"
              effect="plain"
              @close="removeTag(tag.id)"
            >
              {{ tag.name }}
            </el-tag>
          </div>
          <p v-else class="selected-empty">还没有选择兴趣标签。</p>
        </div>
      </section>

      <section class="panel tag-panel">
        <div class="panel-head">
          <h3>兴趣标签</h3>
          <p>从每个领域的下拉列表中挑选标签，推荐结果会更贴近你的主题偏好。</p>
        </div>

        <div v-if="tagGroups.length" class="group-list">
          <section v-for="group in tagGroups" :key="group.domain.id" class="group-card">
            <header class="group-head">
              <div class="group-title">
                <span class="domain-badge">领域</span>
                <strong>{{ group.domain.name }}</strong>
                <span class="group-count">{{ (group.tags || []).length }} 个标签</span>
              </div>
              <p>{{ group.domain.description || '选择这个领域里你更常看的主题。' }}</p>
            </header>
            <div class="group-tags">
              <el-select
                :model-value="getGroupSelected(group)"
                multiple
                collapse-tags
                collapse-tags-tooltip
                filterable
                clearable
                placeholder="选择该领域下感兴趣的标签"
                class="full-width tag-select"
                @update:model-value="setGroupSelected(group, $event)"
              >
                <el-option
                  v-for="tag in group.tags"
                  :key="tag.id"
                  :label="tag.name"
                  :value="tag.id"
                />
              </el-select>
            </div>
          </section>
        </div>
        <el-empty v-else description="暂无兴趣标签数据" :image-size="72" />
      </section>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
:deep(.profile-edit-dialog) {
  margin: 16px auto !important;
  max-height: calc(100vh - 32px);
  display: flex;
  flex-direction: column;
}

:deep(.profile-edit-dialog .el-dialog__body) {
  overflow: auto;
}

.dialog-layout {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.panel {
  padding: 24px 26px;
  border: 1px solid var(--kr-border);
  border-radius: 24px;
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay-soft);
}

.panel-head {
  margin-bottom: 20px;
}

.panel-head h3 {
  margin: 0 0 6px;
  font-size: 22px;
  line-height: 1.05;
  letter-spacing: -0.03em;
}

.panel-head p,
.group-head p,
.selected-empty {
  margin: 0;
  color: var(--kr-text-soft);
  line-height: 1.7;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.field-block + .field-block,
.selected-panel {
  margin-top: 20px;
}

.field-label {
  display: inline-flex;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 800;
  color: var(--kr-text);
}

.full-width {
  width: 100%;
}

.selected-panel {
  padding: 16px 18px;
  border-radius: 18px;
  background: transparent;
  border: 1px solid var(--kr-border);
}

.group-card {
  padding: 18px 20px 20px;
  border-radius: 18px;
  background: transparent;
  border: 1px solid var(--kr-border);
}

.group-card + .group-card {
  margin-top: 0;
}

.selected-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.selected-count {
  font-size: 12px;
  font-weight: 800;
  color: var(--kr-primary);
}

.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.group-list {
  display: grid;
  gap: 16px;
  max-height: min(56vh, 460px);
  overflow: auto;
  padding-right: 6px;
}

.group-head {
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--kr-border);
}

.group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.domain-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--kr-primary, #ff7e3d);
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
}

.group-title strong {
  font-size: 17px;
  letter-spacing: -0.01em;
}

.group-count {
  margin-left: auto;
  font-size: 12px;
  font-weight: 700;
  color: var(--kr-text-soft);
}

.group-tags {
  padding-top: 4px;
}

.tag-select :deep(.el-select__wrapper) {
  border-radius: 14px;
  background: #fff;
  min-height: 40px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
