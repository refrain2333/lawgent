<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import Button from '@/components/ui/Button.vue'
import NavBar from '@/components/ui/NavBar.vue'

const router = useRouter()
const authStore = useAuthStore()

const isLogin = ref(true)
const email = ref('')
const password = ref('')
const nickname = ref('')
const isLoading = ref(false)
const errorMessage = ref('')
const isDev = ['localhost', '127.0.0.1'].includes(window.location.hostname)

async function handleSubmit() {
  errorMessage.value = ''
  isLoading.value = true
  try {
    if (isLogin.value) {
      await authStore.login(email.value, password.value)
    } else {
      await authStore.register(email.value, password.value, nickname.value || undefined)
    }
    router.push({ name: 'chat' })
  } catch (error: any) {
    errorMessage.value = error.response?.data?.detail || '操作失败，请重试'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col bg-gradient-to-br from-background via-accent/20 to-background">

    <NavBar>
      <template #links>
        <router-link to="/search" class="text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5">检索演示</router-link>
      </template>
    </NavBar>

    <div class="flex-1 flex items-center justify-center p-4 relative">
      <!-- 背景装饰 -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none">
        <div class="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-primary/5 blur-3xl"></div>
        <div class="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-primary/5 blur-3xl"></div>
      </div>

      <div class="w-full max-w-md relative animate-fade-in">
      <!-- Logo 区 -->
      <div class="text-center mb-8 space-y-2">
        <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary shadow-lg shadow-primary/30 mb-3">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7 text-primary-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <h1 class="text-2xl font-bold tracking-tight font-serif">LawGent</h1>
        <p class="text-sm text-muted-foreground">智能刑事法律咨询助手</p>
      </div>

      <Card class="p-6 shadow-xl shadow-foreground/5 border-border/60">
        <!-- Tab 切换 -->
        <div class="flex rounded-lg bg-muted p-1 mb-6">
          <button
            class="flex-1 py-1.5 text-sm font-medium rounded-md transition-all duration-200"
            :class="isLogin ? 'bg-card shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'"
            @click="isLogin = true; errorMessage = ''"
          >登录</button>
          <button
            class="flex-1 py-1.5 text-sm font-medium rounded-md transition-all duration-200"
            :class="!isLogin ? 'bg-card shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'"
            @click="isLogin = false; errorMessage = ''"
          >注册</button>
        </div>

        <Transition name="form-switch" mode="out-in">
          <form :key="isLogin ? 'login' : 'register'" @submit.prevent="handleSubmit" class="space-y-4">

            <div v-if="!isLogin" class="space-y-1.5">
              <label class="text-sm font-medium" for="nickname">昵称</label>
              <Input id="nickname" v-model="nickname" placeholder="请输入昵称（可选）" />
            </div>

            <div class="space-y-1.5">
              <label class="text-sm font-medium" for="email">邮箱</label>
              <Input id="email" type="email" v-model="email" placeholder="请输入邮箱" required />
            </div>

            <div class="space-y-1.5">
              <label class="text-sm font-medium" for="password">密码</label>
              <Input id="password" type="password" v-model="password" placeholder="请输入密码" required />
            </div>

            <div v-if="errorMessage" class="text-xs text-destructive bg-destructive/8 border border-destructive/20 rounded-md px-3 py-2">
              {{ errorMessage }}
            </div>

            <Button type="submit" class="w-full mt-2" :disabled="isLoading">
              <svg v-if="isLoading" class="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              {{ isLoading ? '提交中...' : (isLogin ? '登录' : '注册') }}
            </Button>
          </form>
        </Transition>

        <div v-if="isDev" class="mt-4 pt-4 border-t border-border/60 text-center">
          <router-link to="/dev/components">
            <Button variant="ghost" size="sm" class="text-xs text-muted-foreground">组件展示</Button>
          </router-link>
        </div>
      </Card>

      <p class="text-center text-xs text-muted-foreground mt-6">
        内容由 AI 生成，仅供参考，不构成正式法律意见
      </p>
    </div>
    </div>
  </div>
</template>

<style scoped>
.form-switch-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.form-switch-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.form-switch-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.form-switch-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
