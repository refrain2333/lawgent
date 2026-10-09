<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/ui/ThemeToggle.vue'
import { MessageSquare } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()

const navLinks = [
  { to: '/home', label: '首页' },
  { to: '/search', label: '检索演示' },
  { to: '/graph', label: '图谱探索' },
  { to: '/data', label: '数据浏览' },
  { to: '/about', label: '关于' },
  { to: '/tech', label: '技术详情' },
]

function handleLogout() {
  auth.logout()
  router.push({ name: 'home' })
}
</script>

<template>
  <nav class="sticky top-0 left-0 right-0 z-50 border-b border-border/60 bg-card">
    <div class="max-w-6xl mx-auto px-4 h-14 flex items-center gap-2">

      <!-- 左：Logo -->
      <router-link to="/home" class="flex items-center gap-2 shrink-0">
        <div class="w-7 h-7 rounded-lg bg-primary flex items-center justify-center shadow-sm shadow-primary/30">
          <svg class="w-4 h-4 text-primary-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="1.25" />
              <circle cx="14.5" cy="12" r="1.25" />
              <circle cx="9.5" cy="16" r="1.25" />
              <path d="M 6 4 h 12 M 6 4 L 3 14 Q 6 17 9 14 L 6 4 M 18 4 L 15 14 Q 18 17 21 14 L 18 4 M 12 4 v 2.75 M 12 9.25 v 0.25 l 1.6 1.6 M 13.6 12.9 l -3.2 3.2 M 9.5 17.25 v 1.25 l 2.5 2.5 m -4 0 h 8" />
            </svg>
        </div>
        <span class="font-bold font-serif">LawGent</span>
      </router-link>

      <!-- 中：普通导航链接 + 智能咨询 -->
      <div class="hidden md:flex items-center gap-1 min-w-0 flex-1 justify-center">
        <router-link v-for="item in navLinks" :key="item.to" :to="item.to" custom v-slot="{ isActive, navigate }">
          <button
            @click="navigate"
            class="relative text-sm px-3 py-1.5 rounded-md transition-colors whitespace-nowrap"
            :class="isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-muted/60'"
          >
            {{ item.label }}
            <span
              v-if="isActive"
              class="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-primary"
            />
          </button>
        </router-link>

        <!-- 分隔线 -->
        <div class="w-px h-4 bg-border/60 mx-1" />

        <!-- 智能咨询：核心入口 -->
        <router-link to="/chat" custom v-slot="{ isActive, navigate }">
          <button
            @click="navigate"
            class="flex items-center gap-1.5 text-sm px-3.5 py-1.5 rounded-full font-medium transition-all whitespace-nowrap"
            :class="isActive
              ? 'bg-primary text-primary-foreground shadow-sm shadow-primary/30'
              : 'bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20'"
          >
            <MessageSquare class="w-3.5 h-3.5" />
            智能咨询
          </button>
        </router-link>
      </div>

      <!-- 右：登录/退出 + 主题 -->
      <div class="flex items-center gap-2 shrink-0 ml-auto">
        <template v-if="auth.token">
          <button @click="handleLogout"
            class="text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 rounded-md hover:bg-muted transition-colors">
            退出登录
          </button>
        </template>
        <template v-else>
          <router-link to="/login">
            <button class="text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90 transition-colors">
              登录 / 注册
            </button>
          </router-link>
        </template>
        <ThemeToggle />
      </div>

    </div>
  </nav>
</template>
