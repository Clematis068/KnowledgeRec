import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../components/layout/AppLayout.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginPage.vue'),
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterPage.vue'),
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/recommend',
    children: [
      {
        path: 'recommend',
        name: 'Recommend',
        component: () => import('../views/RecommendPage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'posts',
        name: 'PostList',
        component: () => import('../views/PostListPage.vue'),
      },
      {
        path: 'posts/:id',
        name: 'PostDetail',
        component: () => import('../views/PostDetailPage.vue'),
      },
      {
        path: 'users',
        name: 'UserList',
        component: () => import('../views/UserListPage.vue'),
      },
      {
        path: 'users/:id',
        name: 'UserDetail',
        component: () => import('../views/UserDetailPage.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const authStore = useAuthStore()
    if (!authStore.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
})

export default router
