import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { get, post, TOKEN_KEY } from '@/api/http'

const USER_KEY = 'forge_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref(null)

  try {
    const raw = localStorage.getItem(USER_KEY)
    if (raw) user.value = JSON.parse(raw)
  } catch {
    user.value = null
  }

  const isAdmin = computed(() => user.value?.role === 'admin')
  const isGuest = computed(() => user.value?.role === 'guest')
  const isLoggedIn = computed(() => !!token.value)

  function persist(nextToken, nextUser) {
    token.value = nextToken || ''
    user.value = nextUser || null
    if (nextToken) localStorage.setItem(TOKEN_KEY, nextToken)
    else localStorage.removeItem(TOKEN_KEY)
    if (nextUser) localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
    else localStorage.removeItem(USER_KEY)
  }

  async function login(username, password) {
    const res = await post('/api/auth/login', { username, password })
    if (res.error) return res
    persist(res.token, res.user)
    return res
  }

  async function guestLogin() {
    const res = await post('/api/auth/guest', {})
    if (res.error) return res
    persist(res.token, res.user)
    return res
  }

  async function register(payload) {
    const res = await post('/api/auth/register', payload)
    if (res.error) return res
    persist(res.token, res.user)
    return res
  }

  function logout() {
    persist('', null)
  }

  async function fetchMe() {
    if (!token.value) return { error: '未登录' }
    const res = await get('/api/auth/me')
    if (res.error) {
      logout()
      return res
    }
    user.value = res.user
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    return res
  }

  async function changePassword(oldPassword, newPassword) {
    return post('/api/auth/change_password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  }

  return {
    token,
    user,
    isAdmin,
    isGuest,
    isLoggedIn,
    login,
    guestLogin,
    register,
    logout,
    fetchMe,
    changePassword,
  }
})
