import { ref } from 'vue'
import { todosApi } from '~/utils/api'
import type { StreakStats } from '~/types'

const STALE_AFTER_MS = 60_000  // 60s SWR

const streak = ref<StreakStats | null>(null)
const fetchedAt = ref<number>(0)
const loading = ref(false)
const error = ref<string | null>(null)
let inflight: Promise<StreakStats | null> | null = null

async function refresh(force = false): Promise<StreakStats | null> {
  if (inflight) return inflight
  const fresh = !force && Date.now() - fetchedAt.value < STALE_AFTER_MS
  if (fresh && streak.value) return streak.value
  loading.value = true
  error.value = null
  inflight = (async () => {
    try {
      const data = await todosApi.streak()
      streak.value = data
      fetchedAt.value = Date.now()
      return data
    } catch (err: any) {
      error.value = err?.message || 'Failed to load streak'
      return null
    } finally {
      loading.value = false
      inflight = null
    }
  })()
  return inflight
}

function invalidate() {
  fetchedAt.value = 0
  return refresh(true)
}

export function useStreak() {
  return {
    streak,
    loading,
    error,
    refresh,
    invalidate,
  }
}
