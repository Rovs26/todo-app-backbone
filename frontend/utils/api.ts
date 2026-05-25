import type {
  User,
  Todo,
  TodoStats,
  TodoCreate,
  TodoUpdate,
  Notification,
  TagInfo,
  StreakStats,
  SummaryResponse,
  Folder,
  FolderCreate,
  FolderStats,
  FolderUpdate,
  Attachment,
  Comment,
  CommentCreate,
  CommentUpdate,
  UserSearchResult,
} from '~/types'

const BASE_URL = 'http://localhost:8000/api'
const TIMEOUT_MS = 15000

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  params?: Record<string, string | undefined>
  headers?: Record<string, string>
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, params, headers } = options

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const response = await $fetch<T>(path, {
      baseURL: BASE_URL,
      method,
      body: body ? body : undefined,
      params: params
        ? Object.fromEntries(
            Object.entries(params).filter(([, v]) => v !== undefined)
          )
        : undefined,
      headers,
      credentials: 'include',
      signal: controller.signal,
    })
    return response
  } catch (error: any) {
    if (error.name === 'AbortError') {
      throw new Error('Request timed out. Please try again.')
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

// Auth API
export const authApi = {
  register(data: { email: string; username: string; password: string; password_confirm: string }) {
    return apiFetch<User>('/auth/register', { method: 'POST', body: data })
  },

  login(data: { identifier: string; password: string }) {
    return apiFetch<User>('/auth/login', { method: 'POST', body: data })
  },

  logout() {
    return apiFetch<void>('/auth/logout', { method: 'POST' })
  },

  me(headers?: Record<string, string>) {
    return apiFetch<User>('/auth/me', { headers })
  },

  updateMe(data: { email_reminders_enabled: boolean }) {
    return apiFetch<User>('/auth/me', { method: 'PUT', body: data })
  },
}

// Todos API
export const todosApi = {
  list(params?: { status?: string; priority?: string; sort_by?: string; tag?: string; search?: string; folder_id?: string }) {
    return apiFetch<Todo[]>('/todos', { params })
  },

  get(id: string) {
    return apiFetch<Todo>(`/todos/${id}`)
  },

  create(data: TodoCreate) {
    return apiFetch<Todo>('/todos', { method: 'POST', body: data })
  },

  update(id: string, data: TodoUpdate, applyTo: 'occurrence' | 'series' = 'occurrence') {
    return apiFetch<Todo>(`/todos/${id}`, { method: 'PUT', body: data, params: { apply_to: applyTo } })
  },

  delete(id: string, applyTo: 'occurrence' | 'series' = 'occurrence') {
    return apiFetch<void>(`/todos/${id}`, { method: 'DELETE', params: { apply_to: applyTo } })
  },

  bulk(ids: string[], action: string, payload?: Record<string, unknown>) {
    return apiFetch<{
      outcomes: Record<string, { status: string }>
      summary: {
        total: number
        succeeded: number
        not_found: number
        forbidden: number
        validation_error: number
        no_change: number
      }
    }>('/todos/bulk', { method: 'POST', body: { ids, action, payload: payload ?? null } })
  },

  stats() {
    return apiFetch<TodoStats>('/todos/stats')
  },

  streak() {
    return apiFetch<StreakStats>('/todos/streak')
  },

  tags() {
    return apiFetch<TagInfo[]>('/todos/tags/list')
  },

  reorder(ordered_ids: string[]) {
    return apiFetch<Todo[]>('/todos/reorder', { method: 'POST', body: { ordered_ids } })
  },

  addTime(id: string, seconds: number) {
    return apiFetch<Todo>(`/todos/${id}/time`, { method: 'POST', body: { seconds } })
  },

  uploadImage(id: string, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    return $fetch<Todo>(`/todos/${id}/image`, {
      baseURL: BASE_URL,
      method: 'POST',
      body: fd,
      credentials: 'include',
    })
  },

  deleteImage(id: string) {
    return apiFetch<Todo>(`/todos/${id}/image`, { method: 'DELETE' })
  },

  summary() {
    return apiFetch<SummaryResponse>('/todos/summary')
  },

  calendarUrl() {
    return `${BASE_URL}/todos/calendar.ics`
  },

  suggestSubtasks(id: string) {
    return apiFetch<{ title: string }[]>(`/todos/${id}/suggest-subtasks`, { method: 'POST' })
  },

  aiStatus() {
    return apiFetch<{ enabled: boolean }>('/todos/ai-status')
  },
}

// AI / chat / Whisper API

export interface ParsedTodo {
  title: string
  description?: string | null
  priority?: 'low' | 'medium' | 'high' | null
  due_date?: string | null
  reminder_at?: string | null
  recurrence?: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly' | null
  tags?: string[] | null
  folder_id?: string | null
  subtasks?: string[] | null
}

export const aiApi = {
  status() {
    return apiFetch<{ enabled: boolean }>('/ai/status')
  },

  parseTodo(text: string) {
    return apiFetch<{ data: ParsedTodo; source: 'openai' | 'local'; error?: string }>(
      '/ai/parse-todo',
      { method: 'POST', body: { text } },
    )
  },

  transcribe(blob: Blob, filename = 'recording.webm') {
    const fd = new FormData()
    fd.append('file', blob, filename)
    return $fetch<{ text: string | null; source: string }>('/ai/transcribe', {
      baseURL: BASE_URL,
      method: 'POST',
      body: fd,
      credentials: 'include',
    })
  },

  chat(message: string, history: { role: 'user' | 'assistant'; content: string }[]) {
    return apiFetch<{ reply: string; source: string }>('/ai/chat', {
      method: 'POST',
      body: { message, history },
    })
  },
}

// Folders API
export const foldersApi = {
  list() {
    return apiFetch<Folder[]>('/folders')
  },

  stats() {
    return apiFetch<FolderStats[]>('/folders/stats')
  },

  get(id: string) {
    return apiFetch<Folder>(`/folders/${id}`)
  },

  create(data: FolderCreate) {
    return apiFetch<Folder>('/folders', { method: 'POST', body: data })
  },

  update(id: string, data: FolderUpdate) {
    return apiFetch<Folder>(`/folders/${id}`, { method: 'PUT', body: data })
  },

  delete(id: string) {
    return apiFetch<void>(`/folders/${id}`, { method: 'DELETE' })
  },
}

// Comments API
export const commentsApi = {
  list(todoId: string) {
    return apiFetch<Comment[]>(`/todos/${todoId}/comments`)
  },

  create(todoId: string, data: CommentCreate) {
    return apiFetch<Comment>(`/todos/${todoId}/comments`, { method: 'POST', body: data })
  },

  update(todoId: string, commentId: string, data: CommentUpdate) {
    return apiFetch<Comment>(`/todos/${todoId}/comments/${commentId}`, { method: 'PUT', body: data })
  },

  delete(todoId: string, commentId: string) {
    return apiFetch<void>(`/todos/${todoId}/comments/${commentId}`, { method: 'DELETE' })
  },

  uploadAttachment(file: File) {
    const fd = new FormData()
    fd.append('file', file)
    return $fetch<Attachment>('/comment-attachments', {
      baseURL: BASE_URL,
      method: 'POST',
      body: fd,
      credentials: 'include',
    })
  },

  deleteAttachment(attachmentId: string) {
    return apiFetch<void>(`/comment-attachments/${attachmentId}`, { method: 'DELETE' })
  },

  searchUsers(q: string) {
    return apiFetch<UserSearchResult[]>('/users/search', { params: { q } })
  },
}

// Notifications API
export const notificationsApi = {
  list(unreadOnly = false) {
    return apiFetch<Notification[]>('/notifications', {
      params: { unread_only: unreadOnly ? 'true' : undefined },
    })
  },

  check() {
    return apiFetch<Notification[]>('/notifications/check', { method: 'POST' })
  },

  unreadCount() {
    return apiFetch<{ count: number }>('/notifications/unread-count')
  },

  markRead(id: string) {
    return apiFetch<Notification>(`/notifications/${id}/read`, { method: 'POST' })
  },

  markAllRead() {
    return apiFetch<{ updated: number }>('/notifications/read-all', { method: 'POST' })
  },

  clearAll() {
    return apiFetch<{ removed: number }>('/notifications', { method: 'DELETE' })
  },
}
