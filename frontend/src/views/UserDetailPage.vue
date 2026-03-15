<template>
  <div v-loading="loading" class="user-detail-page">
    <el-page-header @back="$router.back()" :title="'返回'" style="margin-bottom: 20px" />

    <template v-if="user">
      <!-- 个人信息卡片 -->
      <el-card class="profile-card" shadow="never">
        <div class="profile">
          <el-avatar :size="64" class="avatar">
            {{ user.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <div class="profile-info">
            <div class="profile-top">
              <h2>{{ user.username }}</h2>
              <el-button
                v-if="!isOwnProfile && authStore.isLoggedIn"
                :type="isFollowing ? 'default' : 'primary'"
                size="small"
                :loading="followLoading"
                @click="toggleFollow"
              >
                {{ isFollowing ? '已关注' : '关注' }}
              </el-button>
              <el-button
                v-if="!isOwnProfile && authStore.isLoggedIn"
                size="small"
                @click="router.push({ path: '/notifications', query: { chat: user.id, username: user.username } })"
              >
                私信
              </el-button>
              <el-button
                v-if="isOwnProfile"
                size="small"
                @click="openEditDialog"
              >
                编辑资料
              </el-button>
            </div>
            <p class="bio">{{ user.bio || '暂无简介' }}</p>
            <div v-if="user.interest_tags && user.interest_tags.length" class="interest-tags">
              <el-tag
                v-for="tag in user.interest_tags"
                :key="tag.id"
                size="small"
                type="info"
                class="interest-tag"
              >
                {{ tag.name }}
              </el-tag>
            </div>
            <div class="stats">
              <span class="stat-item">
                <strong>{{ userPostsTotal }}</strong> 帖子
              </span>
              <span class="stat-divider">|</span>
              <span class="stat-item clickable" @click="activeTab = 'following'">
                <strong>{{ followingCount }}</strong> 关注
              </span>
              <span class="stat-divider">|</span>
              <span class="stat-item clickable" @click="activeTab = 'followers'">
                <strong>{{ followersCount }}</strong> 粉丝
              </span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Tab 内容区 -->
      <el-card class="content-card" shadow="never">
        <el-tabs v-model="activeTab" @tab-change="onTabChange">
          <el-tab-pane label="帖子" name="posts">
            <div v-loading="tabLoading">
              <div v-for="p in userPosts" :key="p.id" class="user-post-item">
                <PostCard :post="p" />
                <div v-if="isOwnProfile" class="post-manage-actions">
                  <el-button size="small" @click="goToEditPost(p.id)">编辑</el-button>
                  <el-button size="small" type="danger" @click="handleDeletePost(p.id)">删除</el-button>
                </div>
              </div>
              <el-empty v-if="!tabLoading && userPosts.length === 0" description="暂无帖子" />
            </div>
            <div v-if="userPostsTotal > pageSize" class="tab-pagination">
              <el-pagination
                v-model:current-page="postsPage"
                :page-size="pageSize"
                :total="userPostsTotal"
                layout="prev, pager, next"
                @current-change="fetchUserPosts"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane label="收藏" name="favorites">
            <div v-loading="tabLoading">
              <PostCard v-for="p in userFavorites" :key="p.id" :post="p" />
              <el-empty v-if="!tabLoading && userFavorites.length === 0" description="暂无收藏" />
            </div>
            <div v-if="favoritesTotal > pageSize" class="tab-pagination">
              <el-pagination
                v-model:current-page="favoritesPage"
                :page-size="pageSize"
                :total="favoritesTotal"
                layout="prev, pager, next"
                @current-change="fetchUserFavorites"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane label="关注" name="following">
            <div v-loading="tabLoading" class="user-grid">
              <div v-for="u in followingList" :key="u.id" class="user-item" @click="$router.push(`/users/${u.id}`)">
                <el-avatar :size="48" class="user-item-avatar">
                  {{ u.username?.charAt(0)?.toUpperCase() }}
                </el-avatar>
                <div class="user-item-name">{{ u.username }}</div>
                <div class="user-item-bio">{{ u.bio || '暂无简介' }}</div>
              </div>
              <el-empty v-if="!tabLoading && followingList.length === 0" description="暂无关注" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="粉丝" name="followers">
            <div v-loading="tabLoading" class="user-grid">
              <div v-for="u in followersList" :key="u.id" class="user-item" @click="$router.push(`/users/${u.id}`)">
                <el-avatar :size="48" class="user-item-avatar">
                  {{ u.username?.charAt(0)?.toUpperCase() }}
                </el-avatar>
                <div class="user-item-name">{{ u.username }}</div>
                <div class="user-item-bio">{{ u.bio || '暂无简介' }}</div>
              </div>
              <el-empty v-if="!tabLoading && followersList.length === 0" description="暂无粉丝" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="行为" name="behaviors">
            <div v-loading="tabLoading">
              <BehaviorTimeline :behaviors="userBehaviors" />
            </div>
          </el-tab-pane>

          <el-tab-pane v-if="isOwnProfile" label="屏蔽" name="blocks">
            <div v-loading="tabLoading" class="block-panel">
              <div class="block-section">
                <div class="block-title">已屏蔽作者</div>
                <div v-if="blockedAuthors.length" class="block-list">
                  <div v-for="author in blockedAuthors" :key="author.id" class="blocked-item">
                    <div class="blocked-main" @click="$router.push(`/users/${author.id}`)">
                      <el-avatar :size="36" class="user-item-avatar">
                        {{ author.username?.charAt(0)?.toUpperCase() }}
                      </el-avatar>
                      <div>
                        <div class="user-item-name">{{ author.username }}</div>
                        <div class="user-item-bio">{{ author.bio || '暂无简介' }}</div>
                      </div>
                    </div>
                    <el-button size="small" @click="handleRemoveBlockedAuthor(author.id)">取消屏蔽</el-button>
                  </div>
                </div>
                <el-empty v-else description="暂无已屏蔽作者" />
              </div>

              <div class="block-section">
                <div class="block-title">已屏蔽领域</div>
                <div v-if="blockedDomains.length" class="domain-list">
                  <div v-for="domain in blockedDomains" :key="domain.id" class="blocked-domain-item">
                    <el-tag size="large" type="warning">{{ domain.name }}</el-tag>
                    <el-button size="small" @click="handleRemoveBlockedDomain(domain.id)">取消屏蔽</el-button>
                  </div>
                </div>
                <el-empty v-else description="暂无已屏蔽领域" />
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="用户不存在" />

    <ProfileEditDialog
      v-model:visible="editDialogVisible"
      :saving="editLoading"
      :profile="editableProfile"
      :tag-groups="tagGroups"
      @save="handleSaveProfile"
    />
    <ChangeEmailVerifyDialog
      v-model:visible="emailVerifyDialogVisible"
      v-model:code="emailCode"
      :email="pendingEmail"
      :countdown="emailCountdown"
      :sending="emailSending"
      :verifying="emailVerifying"
      :verified="emailVerified"
      :dev-code="emailDevCode"
      :saving="editLoading"
      @send-code="handleSendProfileEmailCode"
      @verify-code="handleVerifyProfileEmailCode"
      @confirm="handleConfirmProfileEmailChange"
    />
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'
import { ElMessageBox } from 'element-plus/es/components/message-box/index'
import {
  getBlockedAuthors, getBlockedDomains, getUserBehaviors, getUserDetail, getUserPosts, getUserFavorites,
  followUser, unfollowUser, getFollowers, getFollowing,
  getFollowStatus, removeBlockedAuthor, removeBlockedDomain,
  sendProfileEmailCode, updateProfile, verifyProfileEmailCode,
} from '../api/user'
import { getTags } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import { deletePost } from '../api/post'
import PostCard from '../components/post/PostCard.vue'
import BehaviorTimeline from '../components/user/BehaviorTimeline.vue'
import ChangeEmailVerifyDialog from '../components/user/ChangeEmailVerifyDialog.vue'
import ProfileEditDialog from '../components/user/ProfileEditDialog.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const user = ref(null)
const loading = ref(false)
const activeTab = ref('posts')
const tabLoading = ref(false)
const pageSize = 20

// 关注状态
const isFollowing = ref(false)
const followLoading = ref(false)
const followingCount = ref(0)
const followersCount = ref(0)

// 帖子 tab
const userPosts = ref([])
const postsPage = ref(1)
const userPostsTotal = ref(0)

// 收藏 tab
const userFavorites = ref([])
const favoritesPage = ref(1)
const favoritesTotal = ref(0)

// 关注/粉丝 tab
const followingList = ref([])
const followersList = ref([])
const userBehaviors = ref([])
const blockedAuthors = ref([])
const blockedDomains = ref([])

// 编辑资料
const editDialogVisible = ref(false)
const editLoading = ref(false)
const tagGroups = ref([])
const emailVerifyDialogVisible = ref(false)
const emailCode = ref('')
const emailCountdown = ref(0)
const emailSending = ref(false)
const emailVerifying = ref(false)
const emailVerified = ref(false)
const emailDevCode = ref('')
const pendingProfilePayload = ref(null)

let emailCountdownTimer = null

// 已加载的 tab 集合（用于懒加载）
const loadedTabs = ref(new Set())

const userId = computed(() => Number(route.params.id))
const isOwnProfile = computed(() => authStore.userId === userId.value)
const editableProfile = computed(() => ({
  bio: user.value?.bio || '',
  gender: user.value?.gender || '',
  email: user.value?.email || '',
  tag_ids: (user.value?.interest_tags || []).map((tag) => tag.id),
}))
const pendingEmail = computed(() => pendingProfilePayload.value?.email || '')

function isValidEmail(email) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email || '')
}

function clearEmailCountdown() {
  if (!emailCountdownTimer) return
  window.clearInterval(emailCountdownTimer)
  emailCountdownTimer = null
}

function startEmailCountdown(seconds = 60) {
  emailCountdown.value = seconds
  clearEmailCountdown()
  emailCountdownTimer = window.setInterval(() => {
    if (emailCountdown.value <= 1) {
      clearEmailCountdown()
      emailCountdown.value = 0
      return
    }
    emailCountdown.value -= 1
  }, 1000)
}

function resetEmailVerifyState() {
  emailCode.value = ''
  emailCountdown.value = 0
  emailSending.value = false
  emailVerifying.value = false
  emailVerified.value = false
  emailDevCode.value = ''
  clearEmailCountdown()
}

function closeEmailVerifyDialog() {
  emailVerifyDialogVisible.value = false
  pendingProfilePayload.value = null
  resetEmailVerifyState()
}

async function fetchProfile() {
  loading.value = true
  try {
    const [u, followersData, followingData] = await Promise.all([
      getUserDetail(userId.value),
      getFollowers(userId.value),
      getFollowing(userId.value),
    ])
    user.value = u
    followersCount.value = followersData.count
    followingCount.value = followingData.count

    // 获取关注状态
    if (authStore.isLoggedIn && !isOwnProfile.value) {
      const status = await getFollowStatus(userId.value)
      isFollowing.value = status.is_following
    }

    // 加载默认 tab
    loadedTabs.value.clear()
    await fetchUserPosts()
  } finally {
    loading.value = false
  }
}

async function fetchUserPosts() {
  tabLoading.value = true
  try {
    const data = await getUserPosts(userId.value, postsPage.value, pageSize)
    userPosts.value = data.posts
    userPostsTotal.value = data.total
    loadedTabs.value.add('posts')
  } finally {
    tabLoading.value = false
  }
}

async function fetchUserFavorites() {
  tabLoading.value = true
  try {
    const data = await getUserFavorites(userId.value, favoritesPage.value, pageSize)
    userFavorites.value = data.posts
    favoritesTotal.value = data.total
    loadedTabs.value.add('favorites')
  } finally {
    tabLoading.value = false
  }
}

async function fetchFollowingList() {
  tabLoading.value = true
  try {
    const data = await getFollowing(userId.value)
    followingList.value = data.following
    loadedTabs.value.add('following')
  } finally {
    tabLoading.value = false
  }
}

async function fetchFollowersList() {
  tabLoading.value = true
  try {
    const data = await getFollowers(userId.value)
    followersList.value = data.followers
    loadedTabs.value.add('followers')
  } finally {
    tabLoading.value = false
  }
}

async function fetchUserBehaviorsList() {
  tabLoading.value = true
  try {
    const data = await getUserBehaviors(userId.value, 50)
    userBehaviors.value = data.behaviors || []
    loadedTabs.value.add('behaviors')
  } finally {
    tabLoading.value = false
  }
}

async function fetchBlockedItems() {
  tabLoading.value = true
  try {
    const [authorsData, domainsData] = await Promise.all([
      getBlockedAuthors(),
      getBlockedDomains(),
    ])
    blockedAuthors.value = authorsData.authors || []
    blockedDomains.value = domainsData.domains || []
    loadedTabs.value.add('blocks')
  } finally {
    tabLoading.value = false
  }
}

function onTabChange(tab) {
  if (loadedTabs.value.has(tab)) return
  const fetchMap = {
    posts: fetchUserPosts,
    favorites: fetchUserFavorites,
    following: fetchFollowingList,
    followers: fetchFollowersList,
    behaviors: fetchUserBehaviorsList,
    blocks: fetchBlockedItems,
  }
  fetchMap[tab]?.()
}

async function toggleFollow() {
  followLoading.value = true
  try {
    if (isFollowing.value) {
      await unfollowUser(userId.value)
      isFollowing.value = false
      followersCount.value = Math.max(followersCount.value - 1, 0)
      ElMessage.success('已取消关注')
    } else {
      await followUser(userId.value)
      isFollowing.value = true
      followersCount.value += 1
      ElMessage.success('关注成功')
    }
  } finally {
    followLoading.value = false
  }
}

function openEditDialog() {
  editDialogVisible.value = true
}

async function persistProfile(payload) {
  editLoading.value = true
  try {
    const updated = await updateProfile(payload)
    user.value = updated
    if (isOwnProfile.value) {
      await authStore.fetchUser()
    }
    editDialogVisible.value = false
    closeEmailVerifyDialog()
    ElMessage.success('资料已更新')
  } finally {
    editLoading.value = false
  }
}

async function handleSaveProfile(payload) {
  const currentEmail = (user.value?.email || '').trim().toLowerCase()
  const nextEmail = (payload.email || '').trim().toLowerCase()

  if (nextEmail !== currentEmail) {
    if (!nextEmail) {
      ElMessage.warning('请输入新邮箱')
      return
    }
    if (!isValidEmail(nextEmail)) {
      ElMessage.warning('邮箱格式不正确')
      return
    }

    pendingProfilePayload.value = {
      ...payload,
      email: nextEmail,
    }
    resetEmailVerifyState()
    emailVerifyDialogVisible.value = true
    return
  }

  await persistProfile(payload)
}

async function handleSendProfileEmailCode() {
  if (!pendingEmail.value) {
    ElMessage.warning('请先输入新邮箱')
    return
  }

  emailSending.value = true
  try {
    const data = await sendProfileEmailCode(pendingEmail.value)
    emailDevCode.value = data.dev_code || ''
    startEmailCountdown()
    ElMessage.success(emailDevCode.value ? `验证码已生成：${emailDevCode.value}` : '验证码已发送')
  } catch {
    // 错误已由拦截器处理
  } finally {
    emailSending.value = false
  }
}

async function handleVerifyProfileEmailCode() {
  if (!emailCode.value.trim()) {
    ElMessage.warning('请输入验证码')
    return
  }

  emailVerifying.value = true
  try {
    await verifyProfileEmailCode(pendingEmail.value, emailCode.value.trim())
    emailVerified.value = true
    ElMessage.success('邮箱验证成功')
  } catch {
    emailVerified.value = false
  } finally {
    emailVerifying.value = false
  }
}

async function handleConfirmProfileEmailChange() {
  if (!pendingProfilePayload.value) return
  if (!emailVerified.value) {
    ElMessage.warning('请先完成邮箱验证')
    return
  }
  await persistProfile(pendingProfilePayload.value)
}

function goToEditPost(postId) {
  router.push(`/posts/${postId}/edit`)
}

async function handleDeletePost(postId) {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确认删除这篇帖子吗？', '删除帖子', {
      type: 'warning',
    })
    await deletePost(postId)
    await fetchUserPosts()
    ElMessage.success('帖子已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      // 错误已由拦截器处理
    }
  }
}

async function handleRemoveBlockedAuthor(authorId) {
  try {
    await removeBlockedAuthor(authorId)
    blockedAuthors.value = blockedAuthors.value.filter((author) => author.id !== authorId)
    ElMessage.success('已取消屏蔽作者')
  } catch {
    // 错误已由拦截器处理
  }
}

async function handleRemoveBlockedDomain(domainId) {
  try {
    await removeBlockedDomain(domainId)
    blockedDomains.value = blockedDomains.value.filter((domain) => domain.id !== domainId)
    ElMessage.success('已取消屏蔽领域')
  } catch {
    // 错误已由拦截器处理
  }
}

// 监听路由变化（用户主页间跳转）
watch(
  () => route.params.id,
  () => {
    if (route.name === 'UserDetail') {
      activeTab.value = 'posts'
      fetchProfile()
    }
  }
)

watch(activeTab, (tab) => {
  if (!loadedTabs.value.has(tab)) {
    onTabChange(tab)
  }
})

watch(emailVerifyDialogVisible, (visible, previousVisible) => {
  if (!visible && previousVisible) {
    pendingProfilePayload.value = null
    resetEmailVerifyState()
  }
})

onMounted(async () => {
  fetchProfile()
  // 加载按领域分组的标签（编辑用）
  try {
    const data = await getTags()
    tagGroups.value = data.groups || []
  } catch {
    // ignore
  }
})

onBeforeUnmount(() => {
  clearEmailCountdown()
})
</script>

<style scoped>
.user-detail-page {
  max-width: 1040px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.profile-card,
.content-card {
  border-radius: 32px;
}

.content-card {
  margin-top: 0;
}

.profile {
  display: flex;
  gap: 22px;
  align-items: flex-start;
  padding: 4px 2px;
}

.avatar {
  background: linear-gradient(135deg, var(--kr-primary), var(--kr-hot));
  color: #fff;
  font-size: 24px;
  flex-shrink: 0;
}

.profile-info {
  flex: 1;
}

.profile-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
}

.profile-top h2 {
  font-size: clamp(2.2rem, 4vw, 3.4rem);
  line-height: 0.95;
  letter-spacing: -0.05em;
  margin: 0;
}

.bio {
  font-size: 14px;
  color: var(--kr-text-soft);
  line-height: 1.8;
  margin-bottom: 12px;
}

.interest-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.interest-tag {
  margin-right: 0;
  margin-bottom: 0;
}

.stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 14px;
  color: var(--kr-text-soft);
}

.stat-item strong {
  color: var(--kr-text);
}

.stat-item.clickable {
  cursor: pointer;
}

.stat-item.clickable:hover {
  color: var(--kr-primary);
}

.stat-divider {
  color: rgba(216, 183, 157, 0.9);
}

.tab-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.user-post-item {
  margin-bottom: 12px;
}

.post-manage-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin: -2px 8px 12px;
}

.block-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.block-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--kr-text);
}

.block-list,
.domain-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.blocked-item,
.blocked-domain-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 22px;
  border: 1px solid var(--kr-border);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: var(--kr-shadow-clay-soft);
}

.blocked-main {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.user-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.user-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px 10px;
  border-radius: 16px;
  border: 1px solid var(--kr-border);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: var(--kr-shadow-clay-soft);
  cursor: pointer;
  text-align: center;
}

.user-item:hover .user-item-name {
  color: var(--kr-primary);
}

.user-item-avatar {
  background: linear-gradient(135deg, var(--kr-primary), var(--kr-secondary));
  color: #fff;
  font-size: 18px;
  flex-shrink: 0;
}

.user-item-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--kr-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.user-item-bio {
  font-size: 11px;
  color: var(--kr-text-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}

@media (max-width: 720px) {
  .profile,
  .post-manage-actions,
  .blocked-item,
  .blocked-domain-item {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
