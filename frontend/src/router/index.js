import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../components/layout/AppLayout.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/IndexPage.vue'),
  },
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
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('../views/ForgotPasswordPage.vue'),
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: 'recommend',
        name: 'Recommend',
        component: () => import('../views/RecommendPage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'hot',
        name: 'Hot',
        component: () => import('../views/HotPage.vue'),
      },
      {
        path: 'posts',
        redirect: '/hot',
      },
      {
        path: 'posts/:id',
        name: 'PostDetail',
        component: () => import('../views/PostDetailPage.vue'),
      },
      {
        path: 'posts/:id/edit',
        name: 'EditPost',
        component: () => import('../views/EditPostPage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'create-post',
        name: 'CreatePost',
        component: () => import('../views/CreatePostPage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'my-posts',
        name: 'MyPosts',
        component: () => import('../views/MyPostsPage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'search',
        name: 'Search',
        component: () => import('../views/SearchPage.vue'),
      },
      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('../views/NotificationPage.vue'),
        meta: { requiresAuth: true },
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
      {
        path: 'evaluation',
        name: 'Evaluation',
        component: () => import('../views/EvaluationPage.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }

    return {
      left: 0,
      top: 0,
    }
  },
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const authStore = useAuthStore()
    if (!authStore.token) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
})

export default router
