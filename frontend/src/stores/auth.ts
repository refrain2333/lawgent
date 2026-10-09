import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export interface UserInfo {
  id: number
  username: string
  email: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserInfo | null>(null)

  // dev 走相对路径（Vite proxy），prod 用 VITE_API_BASE_URL
  const baseURL = import.meta.env.PROD
    ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
    : '/api/v1'
  const api = axios.create({ baseURL })

  api.interceptors.request.use((config) => {
    if (token.value) {
      config.headers.Authorization = `Bearer ${token.value}`
    }
    return config
  })

  async function login(email: string, password: string) {
    const resp = await api.post('/user/login', { email, password })
    token.value = resp.data.access_token
    localStorage.setItem('token', token.value!)
  }

  async function register(email: string, password: string, nickname?: string) {
    const resp = await api.post('/user/register', { email, password, nickname })
    token.value = resp.data.access_token
    localStorage.setItem('token', token.value!)
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, login, register, logout, api }
})
