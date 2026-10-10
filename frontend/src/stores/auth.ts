import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
import { apiUrl } from '@/lib/api'
import { useChatStore } from './chat'

export interface UserInfo {
  id: number
  username: string
  email: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserInfo | null>(null)

  const api = axios.create({ baseURL: apiUrl() })

  api.interceptors.request.use((config) => {
    if (token.value) {
      config.headers.Authorization = `Bearer ${token.value}`
    }
    return config
  })

  api.interceptors.response.use(response => response, error => {
    if (error.response?.status === 401 && token.value) logout()
    return Promise.reject(error)
  })

  async function login(email: string, password: string) {
    const resp = await api.post('/user/login', { email, password })
    useChatStore().reset(true)
    token.value = resp.data.access_token
    localStorage.setItem('token', token.value!)
  }

  async function register(email: string, password: string, nickname?: string) {
    const resp = await api.post('/user/register', { email, password, nickname })
    useChatStore().reset(true)
    token.value = resp.data.access_token
    localStorage.setItem('token', token.value!)
  }

  function logout() {
    useChatStore().reset(true)
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('lastNewChatTime')
  }

  return { token, user, login, register, logout, api }
})
