<script setup>
import { computed, ref, watch } from 'vue'

const BATCH_SIZE = 12

const props = defineProps({
  groups: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  selectedTagIds: {
    type: Array,
    default: () => [],
  },
  minSelection: {
    type: Number,
    default: 3,
  },
})

const emit = defineEmits(['update:selectedTagIds'])

const activeDomainId = ref(null)
const batchIndex = ref(0)

const activeGroup = computed(() => {
  if (!props.groups.length) return null
  return props.groups.find((group) => group.domain.id === activeDomainId.value) || props.groups[0]
})

const visibleTags = computed(() => {
  const tags = activeGroup.value?.tags || []
  if (!tags.length) return []
  if (tags.length <= BATCH_SIZE) return tags

  const start = (batchIndex.value * BATCH_SIZE) % tags.length
  const end = start + BATCH_SIZE
  if (end <= tags.length) {
    return tags.slice(start, end)
  }
  return [...tags.slice(start), ...tags.slice(0, end - tags.length)]
})

const selectedCount = computed(() => props.selectedTagIds.length)

watch(
  () => props.groups,
  (groups) => {
    if (!groups.length) {
      activeDomainId.value = null
      batchIndex.value = 0
      return
    }
    const exists = groups.some((group) => group.domain.id === activeDomainId.value)
    if (!exists) {
      activeDomainId.value = groups[0].domain.id
      batchIndex.value = 0
    }
  },
  { immediate: true },
)

function updateSelectedTagIds(nextIds) {
  emit('update:selectedTagIds', nextIds)
}

function toggleTag(tagId) {
  const nextIds = props.selectedTagIds.includes(tagId)
    ? props.selectedTagIds.filter((id) => id !== tagId)
    : [...props.selectedTagIds, tagId]
  updateSelectedTagIds(nextIds)
}

function selectDomain(domainId) {
  activeDomainId.value = domainId
  batchIndex.value = 0
}

function rotateBatch() {
  if (!activeGroup.value?.tags?.length) return
  batchIndex.value += 1
}

function removeSelectedTag(tagId) {
  updateSelectedTagIds(props.selectedTagIds.filter((id) => id !== tagId))
}

function isSelected(tagId) {
  return props.selectedTagIds.includes(tagId)
}

function findTagName(tagId) {
  for (const group of props.groups) {
    const tag = group.tags.find((item) => item.id === tagId)
    if (tag) return tag.name
  }
  return `标签 ${tagId}`
}
</script>

<template>
  <div class="interest-step" v-loading="loading">
    <div class="step-head">
      <div>
        <h3>选几个你感兴趣的主题</h3>
        <p>至少选择 {{ minSelection }} 个，后面推荐会更准。</p>
      </div>
      <div class="selected-count">{{ selectedCount }} 已选择</div>
    </div>

    <div class="selected-panel">
      <div class="selected-title">已选兴趣</div>
      <div v-if="selectedCount" class="selected-tags">
        <el-tag
          v-for="tagId in selectedTagIds"
          :key="tagId"
          closable
          size="large"
          @close="removeSelectedTag(tagId)"
        >
          {{ findTagName(tagId) }}
        </el-tag>
      </div>
      <el-empty v-else description="还没有选择兴趣标签" :image-size="70" />
    </div>

    <div class="domain-toolbar" v-if="groups.length">
      <el-select
        :model-value="activeDomainId"
        placeholder="选择一个领域"
        class="domain-select"
        @update:model-value="selectDomain"
      >
        <el-option
          v-for="group in groups"
          :key="group.domain.id"
          :label="group.domain.name"
          :value="group.domain.id"
        />
      </el-select>
      <el-button @click="rotateBatch">换一批</el-button>
    </div>

    <div v-if="activeGroup" class="tag-panel">
      <div class="domain-meta">
        <div class="domain-title">{{ activeGroup.domain.name }}</div>
        <div class="domain-desc">{{ activeGroup.domain.description || '从这个领域挑几个你想看的主题。' }}</div>
      </div>

      <div class="tag-grid">
        <button
          v-for="tag in visibleTags"
          :key="tag.id"
          type="button"
          class="tag-chip"
          :class="{ selected: isSelected(tag.id) }"
          @click="toggleTag(tag.id)"
        >
          {{ tag.name }}
        </button>
      </div>
    </div>

    <el-empty v-else description="暂无兴趣标签数据" />
  </div>
</template>

<style scoped>
.interest-step {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.step-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.step-head h3 {
  margin: 0 0 6px;
  font-size: 24px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.step-head p {
  margin: 0;
  color: var(--kr-text-soft);
  line-height: 1.7;
}

.selected-count {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--kr-secondary-soft);
  color: var(--kr-secondary);
  font-weight: 800;
}

.selected-panel,
.tag-panel {
  border: 1px solid var(--kr-border);
  border-radius: 24px;
  padding: 18px;
  background: var(--kr-surface);
  box-shadow: var(--kr-shadow-clay-soft);
}

.selected-title {
  margin-bottom: 12px;
  color: var(--kr-text);
  font-weight: 800;
}

.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.domain-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.domain-select {
  max-width: 260px;
}

.domain-meta {
  margin-bottom: 16px;
}

.domain-title {
  font-size: 20px;
  font-weight: 800;
  color: var(--kr-text);
  letter-spacing: -0.03em;
}

.domain-desc {
  margin-top: 6px;
  color: var(--kr-text-soft);
  line-height: 1.6;
}

.tag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px;
}

.tag-chip {
  padding: 12px 14px;
  border: 3px solid #e6cdb9;
  border-radius: 16px;
  font-weight: 700;
  color: var(--kr-text);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--kr-shadow-clay-soft);
}

.tag-chip.selected {
  color: #fff;
  background: linear-gradient(135deg, var(--kr-primary), var(--kr-hot));
}

@media (max-width: 720px) {
  .step-head,
  .domain-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .domain-select {
    max-width: none;
  }
}
</style>
