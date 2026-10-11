import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const username = ref<string>(localStorage.getItem('username') || '')
  const role = ref<string>(localStorage.getItem('role') || '')

  function setAuth(data: { token: string; role: string; username?: string }) {
    token.value = data.token
    role.value = data.role
    if (data.username) username.value = data.username
    localStorage.setItem('token', data.token)
    localStorage.setItem('role', data.role)
    if (data.username) localStorage.setItem('username', data.username)
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
  }

  return { token, username, role, setAuth, logout }
})
