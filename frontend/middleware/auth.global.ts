import { authApi } from '~/utils/api'
import type { User } from '~/types'

const AUTH_CACHE_KEY = 'todo-app-auth-user'

function readCachedUser(): User | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(AUTH_CACHE_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

function writeCachedUser(u: User | null) {
  if (typeof window === 'undefined') return
  try {
    if (u) window.localStorage.setItem(AUTH_CACHE_KEY, JSON.stringify(u))
    else window.localStorage.removeItem(AUTH_CACHE_KEY)
  } catch { /* ignore quota / disabled storage */ }
}

export default defineNuxtRouteMiddleware(async (to) => {
  const publicPages = ['/login', '/register']
  const protectedPages = ['/dashboard']

  const isPublicPage = publicPages.includes(to.path)
  const isProtectedPage = protectedPages.includes(to.path) || to.path.startsWith('/dashboard')

  const user = useState<User | null>('auth-user', () => null)
  const authChecked = useState<boolean>('auth-checked', () => false)

  // On the client, seed from localStorage immediately so a refresh shows the
  // dashboard without a flash to /login while the backend round-trip runs.
  if (!authChecked.value && import.meta.client && !user.value) {
    const cached = readCachedUser()
    if (cached) user.value = cached
  }

  if (!authChecked.value) {
    try {
      const headers = import.meta.server
        ? useRequestHeaders(['cookie'])
        : undefined
      const currentUser = await authApi.me(headers)
      user.value = currentUser
      if (import.meta.client) writeCachedUser(currentUser)
    } catch {
      // Backend rejected the cookie — clear both in-memory and cached user.
      user.value = null
      if (import.meta.client) writeCachedUser(null)
    }
    authChecked.value = true
  }

  const isAuthenticated = !!user.value

  if (isProtectedPage && !isAuthenticated) {
    return navigateTo('/login')
  }

  if (isPublicPage && isAuthenticated) {
    return navigateTo('/dashboard')
  }
})
