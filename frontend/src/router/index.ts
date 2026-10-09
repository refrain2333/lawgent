import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: () => {
        const auth = useAuthStore()
        return auth.token ? { name: 'chat' } : { name: 'login' }
      },
    },
    {
      path: '/home',
      name: 'home',
      component: () => import('@/pages/home/HomeView.vue'),
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('@/pages/about/AboutView.vue'),
    },
    {
      path: '/tech',
      name: 'tech',
      component: () => import('@/pages/tech/TechView.vue'),
    },
    {
      path: '/graph',
      name: 'graph',
      component: () => import('@/pages/graph/GraphView.vue'),
    },
    {
      path: '/data',
      name: 'data',
      component: () => import('@/pages/data/DataView.vue'),
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/pages/search/SearchView.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/pages/chat/ChatView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/auth/LoginView.vue'),
    },
    {
      path: '/dev/components',
      name: 'components-hub',
      component: () => import('@/pages/dev/ComponentsHubView.vue'),
    },
    {
      path: '/dev/components/:name',
      name: 'components-detail',
      component: () => import('@/pages/dev/ComponentDetailView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.token) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.token) {
    return { name: 'chat' }
  }
})

export default router
