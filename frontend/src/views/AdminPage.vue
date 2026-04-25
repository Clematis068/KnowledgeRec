<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1 class="admin-title">管理后台</h1>
      <el-button text @click="router.push('/recommend')">返回首页</el-button>
    </div>

    <el-tabs v-model="activeTab" class="admin-tabs">
      <!-- ─── 数据概览 ─── -->
      <el-tab-pane label="数据概览" name="overview">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_users }}</div>
            <div class="stat-label">总用户数</div>
            <div class="stat-today">今日 +{{ stats.new_users_today }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_posts }}</div>
            <div class="stat-label">总帖子数</div>
            <div class="stat-today">今日 +{{ stats.new_posts_today }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_behaviors }}</div>
            <div class="stat-label">总行为数</div>
            <div class="stat-today">今日 +{{ stats.new_behaviors_today }}</div>
          </div>
          <div class="stat-card warn">
            <div class="stat-value">{{ stats.banned_users }}</div>
            <div class="stat-label">封禁用户</div>
          </div>
          <div class="stat-card warn">
            <div class="stat-value">{{ stats.pending_posts }}</div>
            <div class="stat-label">待审帖子</div>
          </div>
        </div>

        <div class="trend-section" v-if="stats.trend?.length">
          <h3 class="section-title">近 7 日趋势</h3>
          <div class="trend-table">
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th v-for="item in stats.trend" :key="item.date">{{ item.date }}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>新增用户</td>
                  <td v-for="item in stats.trend" :key="'u-' + item.date">{{ item.users }}</td>
                </tr>
                <tr>
                  <td>新增帖子</td>
                  <td v-for="item in stats.trend" :key="'p-' + item.date">{{ item.posts }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </el-tab-pane>

      <!-- ─── 用户管理 ─── -->
      <el-tab-pane label="用户管理" name="users">
        <div class="filter-bar">
          <el-input v-model="userKeyword" placeholder="搜索用户名/邮箱" clearable style="width: 240px" @keyup.enter="loadUsers" />
          <el-select v-model="userStatusFilter" placeholder="状态筛选" clearable style="width: 140px" @change="loadUsers">
            <el-option label="正常" value="active" />
            <el-option label="已封禁" value="banned" />
          </el-select>
          <el-button @click="loadUsers">查询</el-button>
        </div>

        <el-table :data="users" stripe class="admin-table">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column prop="role" label="角色" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.role === 'admin'" type="warning" size="small">管理员</el-tag>
              <el-tag v-else size="small">普通</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'banned'" type="danger" size="small">封禁</el-tag>
              <el-tag v-else type="success" size="small">正常</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="注册时间" width="170">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status !== 'banned' && row.role !== 'admin'" type="danger" text size="small" @click="handleBan(row)">封禁</el-button>
              <el-button v-if="row.status === 'banned'" type="success" text size="small" @click="handleUnban(row)">解封</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="userTotal > 20"
          class="admin-pagination"
          layout="total, prev, pager, next"
          :total="userTotal"
          :page-size="20"
          v-model:current-page="userPage"
          @current-change="loadUsers"
        />
      </el-tab-pane>

      <!-- ─── 内容审核 ─── -->
      <el-tab-pane label="内容审核" name="posts">
        <div class="filter-bar">
          <el-input v-model="postKeyword" placeholder="搜索帖子标题" clearable style="width: 240px" @keyup.enter="loadPosts" />
          <el-select v-model="postStatusFilter" placeholder="状态筛选" clearable style="width: 140px" @change="loadPosts">
            <el-option label="已发布" value="published" />
            <el-option label="待审核" value="pending" />
            <el-option label="已删除" value="removed" />
          </el-select>
          <el-button @click="loadPosts">查询</el-button>
        </div>

        <el-table :data="posts" stripe class="admin-table">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="author_name" label="作者" width="120" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'published'" type="success" size="small">已发布</el-tag>
              <el-tag v-else-if="row.status === 'pending'" type="warning" size="small">待审</el-tag>
              <el-tag v-else-if="row.status === 'rejected'" type="danger" size="small">已拒绝</el-tag>
              <el-tag v-else type="info" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="like_count" label="点赞" width="70" />
          <el-table-column prop="created_at" label="发布时间" width="170">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status !== 'published'" type="success" text size="small" @click="handleApprove(row)">通过</el-button>
              <el-button v-if="row.status === 'published'" type="warning" text size="small" @click="handleReject(row)">下架</el-button>
              <el-button type="danger" text size="small" @click="handleRemove(row)">删除</el-button>
              <el-button text size="small" @click="router.push(`/posts/${row.id}`)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="postTotal > 20"
          class="admin-pagination"
          layout="total, prev, pager, next"
          :total="postTotal"
          :page-size="20"
          v-model:current-page="postPage"
          @current-change="loadPosts"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAdminStats, getAdminUsers, banUser, unbanUser,
  getAdminPosts, approvePost, rejectPost, removePost,
} from '../api/admin'

const router = useRouter()
const activeTab = ref('overview')

// 概览
const stats = ref({})

// 用户管理
const users = ref([])
const userTotal = ref(0)
const userPage = ref(1)
const userKeyword = ref('')
const userStatusFilter = ref('')

// 内容审核
const posts = ref([])
const postTotal = ref(0)
const postPage = ref(1)
const postKeyword = ref('')
const postStatusFilter = ref('')

function formatDate(iso) {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 16)
}

async function loadStats() {
  try {
    stats.value = await getAdminStats()
  } catch {
    ElMessage.error('加载统计数据失败')
  }
}

async function loadUsers() {
  try {
    const data = await getAdminUsers({
      page: userPage.value,
      per_page: 20,
      keyword: userKeyword.value,
      status: userStatusFilter.value,
    })
    users.value = data.users
    userTotal.value = data.total
  } catch {
    ElMessage.error('加载用户列表失败')
  }
}

async function handleBan(row) {
  try {
    await ElMessageBox.confirm(`确定封禁用户「${row.username}」？`, '封禁确认', { type: 'warning' })
    await banUser(row.id)
    ElMessage.success('已封禁')
    loadUsers()
    loadStats()
  } catch { /* cancel */ }
}

async function handleUnban(row) {
  try {
    await unbanUser(row.id)
    ElMessage.success('已解封')
    loadUsers()
    loadStats()
  } catch {
    ElMessage.error('解封失败')
  }
}

async function loadPosts() {
  try {
    const data = await getAdminPosts({
      page: postPage.value,
      per_page: 20,
      keyword: postKeyword.value,
      status: postStatusFilter.value,
    })
    posts.value = data.posts
    postTotal.value = data.total
  } catch {
    ElMessage.error('加载帖子列表失败')
  }
}

async function handleApprove(row) {
  try {
    await approvePost(row.id)
    ElMessage.success('已通过审核')
    loadPosts()
    loadStats()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleReject(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入下架原因', '下架帖子', {
      inputPlaceholder: '内容不符合社区规范',
    })
    await rejectPost(row.id, value || '内容不符合社区规范')
    ElMessage.success('已下架')
    loadPosts()
    loadStats()
  } catch { /* cancel */ }
}

async function handleRemove(row) {
  try {
    await ElMessageBox.confirm(`确定永久删除帖子「${row.title}」？此操作不可恢复。`, '删除确认', { type: 'error' })
    await removePost(row.id)
    ElMessage.success('已删除')
    loadPosts()
    loadStats()
  } catch { /* cancel */ }
}

onMounted(() => {
  loadStats()
  loadUsers()
  loadPosts()
})
</script>

<style scoped>
.admin-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.admin-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--cds-text-primary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  padding: 20px;
  background: var(--cds-layer-01);
  border-left: 3px solid var(--cds-link-primary);
}

.stat-card.warn {
  border-left-color: var(--cds-support-error);
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--cds-text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--cds-text-secondary);
  margin-top: 4px;
}

.stat-today {
  font-size: 12px;
  color: var(--cds-link-primary);
  margin-top: 8px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--cds-text-primary);
  margin-bottom: 12px;
}

.trend-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.trend-table th,
.trend-table td {
  padding: 8px 12px;
  text-align: center;
  border-bottom: 1px solid var(--cds-border-subtle);
}

.trend-table th {
  color: var(--cds-text-secondary);
  font-weight: 400;
}

.trend-table td:first-child,
.trend-table th:first-child {
  text-align: left;
  font-weight: 600;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.admin-table {
  width: 100%;
}

.admin-pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
