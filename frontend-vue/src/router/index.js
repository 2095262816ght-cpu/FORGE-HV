import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/layouts/MainLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'outliers', name: 'outliers', component: () => import('@/views/OutliersView.vue') },
      { path: 'correlation', name: 'correlation', component: () => import('@/views/CorrelationView.vue') },
      { path: 'ddpg', name: 'ddpg', component: () => import('@/views/DdpgView.vue') },
      { path: 'ddpg-arch', name: 'ddpg-arch', component: () => import('@/views/DdpgArchView.vue') },
      { path: 'gan-process', name: 'gan-process', component: () => import('@/views/GanProcessView.vue') },
      { path: 'cmp53', name: 'cmp53', component: () => import('@/views/Cmp53View.vue') },
      { path: 'cmp54', name: 'cmp54', component: () => import('@/views/Cmp54View.vue') },
      { path: 'results', name: 'results', component: () => import('@/views/ResultsView.vue') },
      { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (auth.token && to.name === 'login') return '/dashboard'
    return true
  }

  if (!auth.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (!auth.user) {
    const res = await auth.fetchMe()
    if (res.error) return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.meta.adminOnly && !auth.isAdmin) {
    return '/dashboard'
  }

  return true
})

export default router
