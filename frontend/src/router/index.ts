import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
    {
      path: '/',
      component: () => import('../views/LayoutView.vue'),
      redirect: '/upload',
      children: [
        { path: 'upload', name: 'upload', component: () => import('../views/UploadView.vue') },
        { path: 'tasks', name: 'tasks', component: () => import('../views/TaskListView.vue') },
        { path: 'alerts', name: 'alerts', component: () => import('../views/AlertView.vue') },
        {
          path: 'tasks/:id/report',
          name: 'report',
          component: () => import('../views/ReportView.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 路由守卫：未登录跳登录页
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.token) return '/login'
  if (to.path === '/login' && auth.token) return '/'
  return true
})

export default router
