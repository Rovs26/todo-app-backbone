export interface User {
  id: string
  email: string
  username: string
  created_at: string
}

export interface Subtask {
  id: string
  title: string
  done: boolean
}

export interface Folder {
  id: string
  user_id: string
  name: string
  color: string | null
  icon: string | null
  created_at: string
  updated_at: string | null
}

export interface FolderStats {
  id: string
  name: string
  color: string | null
  icon: string | null
  total: number
  completed: number
  pending: number
}

export type Recurrence = 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly'

export interface Todo {
  id: string
  user_id: string
  title: string
  description: string | null
  priority: 'low' | 'medium' | 'high'
  due_date: string | null
  reminder_at: string | null
  status: 'pending' | 'in-progress' | 'done'
  folder_id: string | null
  tags: string[]
  subtasks: Subtask[]
  image_url: string | null
  position: number
  time_spent_seconds: number
  recurrence: Recurrence
  recurrence_until: string | null
  recurrence_count: number | null
  recurrence_series_id: string | null
  recurrence_index: number
  created_at: string
  updated_at: string | null
}

export interface TodoStats {
  total: number
  completed: number
  pending: number
  overdue: number
}

export interface StreakStats {
  today_completed: number
  week_completed: number
  current_streak_days: number
  longest_streak_days: number
  last_completion_date: string | null
}

export type TodoCreate = Pick<Todo, 'title'> &
  Partial<Pick<Todo, 'description' | 'priority' | 'due_date' | 'reminder_at' | 'status' | 'folder_id' | 'tags' | 'subtasks' | 'recurrence' | 'recurrence_until' | 'recurrence_count'>>

export type TodoUpdate = Partial<
  Pick<Todo, 'title' | 'description' | 'priority' | 'due_date' | 'reminder_at' | 'status' | 'folder_id' | 'tags' | 'subtasks' | 'position' | 'recurrence' | 'recurrence_until' | 'recurrence_count'>
>

export interface TagInfo {
  name: string
  count: number
}

export interface SummaryResponse {
  stats: TodoStats
  next_due_id: string | null
  next_due_title: string | null
  next_due_date: string | null
  high_priority_pending_ids: string[]
  top_tags: TagInfo[]
  summary: string
  summary_source?: 'openai' | 'local'
}

export interface FolderCreate {
  name: string
  color?: string | null
  icon?: string | null
}

export type FolderUpdate = Partial<FolderCreate>

export interface Attachment {
  id: string
  owner_id: string
  comment_id: string | null
  todo_id: string | null
  url: string
  mime_type: string
  size_bytes: number
  original_name: string
  created_at: string
}

export interface MentionRef {
  username: string
  user_id: string
}

export interface Comment {
  id: string
  todo_id: string
  author_id: string
  author_username: string
  parent_comment_id: string | null
  body: string
  attachments: Attachment[]
  mentions: MentionRef[]
  is_tombstone: boolean
  created_at: string
  updated_at: string | null
}

export interface CommentCreate {
  body: string
  parent_comment_id?: string | null
  attachment_ids?: string[]
}

export interface CommentUpdate {
  body: string
  attachment_ids?: string[]
}

export interface UserSearchResult {
  id: string
  username: string
}

export type NotificationType = 'reminder_due' | 'overdue' | 'ai_coach'

export interface Notification {
  id: string
  user_id: string
  todo_id: string
  todo_title: string
  notification_type: NotificationType
  triggered_at: string
  delivered_at: string
  read: boolean
}
