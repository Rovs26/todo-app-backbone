<template>
  <div class="min-h-screen bg-secondary-50 dark:bg-secondary-900 transition-colors duration-200">
    <!-- Header -->
    <header class="bg-white dark:bg-secondary-800 border-b border-secondary-200 dark:border-secondary-700 sticky top-0 z-10">
      <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16 gap-3">
          <div class="flex items-center gap-3 min-w-0">
            <svg class="w-8 h-8 text-primary-600 dark:text-primary-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            <h1 class="text-xl font-bold text-secondary-900 dark:text-white truncate">Todo Dashboard</h1>
          </div>

          <!-- Search (desktop) -->
          <div class="hidden md:block flex-1 max-w-md">
            <label for="search-input" class="sr-only">Search</label>
            <div class="relative">
              <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-secondary-400">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" /></svg>
              </span>
              <input
                id="search-input"
                ref="searchInputRef"
                v-model="searchInput"
                type="text"
                placeholder="Search title, description, tags…"
                class="input-field pl-9 text-sm"
                @keyup.escape="searchInput = ''"
              />
            </div>
          </div>

          <div class="flex items-center gap-2 flex-shrink-0">
            <NotificationBell />
            <DarkModeToggle />
            <button
              type="button"
              class="btn-secondary text-sm flex items-center gap-1.5"
              :disabled="loggingOut"
              @click="handleLogout"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
              <span class="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>

        <!-- Search (mobile) -->
        <div class="md:hidden pb-3">
          <input
            v-model="searchInput"
            type="text"
            placeholder="Search…"
            class="input-field text-sm"
            aria-label="Search"
          />
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <!-- Left rail -->
        <aside class="lg:col-span-3 space-y-4">
          <FoldersSidebar
            v-model="folderFilter"
            :folders="folders"
            :stats="folderStats"
            :total-count="folderAllTotal"
            @create="onCreateFolder"
            @update="onUpdateFolder"
            @delete="onDeleteFolder"
          />
          <SummaryPanel :refresh-key="summaryRefresh" />
          <a
            class="block text-center text-xs text-primary-600 dark:text-primary-400 hover:underline"
            :href="calendarUrl"
            target="_blank"
            rel="noopener"
          >
            Subscribe (.ics) →
          </a>
        </aside>

        <!-- Right column -->
        <div class="lg:col-span-9 space-y-6">
          <section aria-label="Todo statistics">
            <LoadingSkeleton v-if="loading && !stats" variant="stats" aria-label="Loading statistics" />
            <StatsCards v-else :stats="stats" />
          </section>

          <!-- View switcher + filters -->
          <section class="bg-white dark:bg-secondary-800 rounded-lg border border-secondary-200 dark:border-secondary-700 p-3">
            <div class="flex flex-wrap items-center gap-3">
              <div class="inline-flex rounded-md border border-secondary-200 dark:border-secondary-700 overflow-hidden">
                <button
                  v-for="opt in viewOptions"
                  :key="opt.id"
                  type="button"
                  class="px-3 py-1.5 text-xs font-medium transition-colors duration-150 focus:outline-none"
                  :class="view === opt.id
                    ? 'bg-primary-600 text-white'
                    : 'bg-white dark:bg-secondary-800 text-secondary-700 dark:text-secondary-300 hover:bg-secondary-50 dark:hover:bg-secondary-700'"
                  @click="view = opt.id"
                >
                  {{ opt.label }}
                </button>
              </div>

              <div v-if="view === 'list'" class="flex flex-wrap items-center gap-2 ml-auto">
                <button
                  type="button"
                  class="text-xs px-3 py-1.5 rounded-md border transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  :class="selectMode
                    ? 'bg-primary-600 border-primary-600 text-white hover:bg-primary-700'
                    : 'bg-white dark:bg-secondary-800 border-secondary-300 dark:border-secondary-600 text-secondary-700 dark:text-secondary-200 hover:bg-secondary-50 dark:hover:bg-secondary-700'"
                  @click="toggleSelectMode"
                >
                  {{ selectMode ? 'Done' : 'Select' }}
                </button>
                <button
                  v-if="selectMode"
                  type="button"
                  class="text-xs px-2 py-1.5 rounded-md text-secondary-600 dark:text-secondary-300 hover:text-secondary-900 dark:hover:text-white"
                  @click="selectAllVisible"
                >
                  {{ allVisibleSelected ? 'Unselect all' : 'Select all' }}
                </button>
                <FilterBar
                  :status-filter="statusFilter"
                  :priority-filter="priorityFilter"
                  :sort-by="sortBy"
                  @update:status-filter="handleStatusFilter"
                  @update:priority-filter="handlePriorityFilter"
                  @update:sort-by="handleSortBy"
                />
              </div>
            </div>

            <!-- Tags row -->
            <div v-if="availableTags.length" class="mt-3 flex flex-wrap items-center gap-1.5">
              <span class="text-[11px] uppercase tracking-wide text-secondary-500 dark:text-secondary-400 mr-1">Tags</span>
              <button
                type="button"
                class="text-xs px-2 py-0.5 rounded-full transition-colors"
                :class="!tagFilter
                  ? 'bg-primary-600 text-white'
                  : 'bg-secondary-100 text-secondary-700 hover:bg-secondary-200 dark:bg-secondary-700 dark:text-secondary-200 dark:hover:bg-secondary-600'"
                @click="tagFilter = undefined"
              >
                All
              </button>
              <button
                v-for="t in availableTags"
                :key="t.name"
                type="button"
                class="text-xs px-2 py-0.5 rounded-full transition-colors"
                :class="tagFilter === t.name
                  ? 'bg-primary-600 text-white'
                  : 'bg-secondary-100 text-secondary-700 hover:bg-secondary-200 dark:bg-secondary-700 dark:text-secondary-200 dark:hover:bg-secondary-600'"
                @click="tagFilter = t.name"
              >
                #{{ t.name }} <span class="text-secondary-400 dark:text-secondary-500">{{ t.count }}</span>
              </button>
            </div>
          </section>

          <!-- Active folder header -->
          <section v-if="folderFilter" class="flex items-center gap-2">
            <span
              v-if="activeFolder?.color"
              class="inline-block w-3 h-3 rounded-full"
              :style="{ backgroundColor: activeFolder.color }"
              aria-hidden="true"
            ></span>
            <span v-else aria-hidden="true">{{ activeFolder?.icon || (folderFilter === 'none' ? '🗒' : '📁') }}</span>
            <h2 class="text-base font-semibold text-secondary-900 dark:text-white">
              {{ folderFilter === 'none' ? 'Unassigned' : activeFolder?.name || 'Folder' }}
            </h2>
            <button type="button" class="ml-auto text-xs text-primary-600 dark:text-primary-400 hover:underline" @click="folderFilter = null">
              Show all
            </button>
          </section>

          <!-- View bodies -->
          <section v-if="view === 'list'" aria-label="Todo list">
            <LoadingSkeleton v-if="loading && todos.length === 0" variant="card" :count="5" aria-label="Loading todos" />
            <EmptyState
              v-else-if="!loading && todos.length === 0"
              :title="folderFilter ? 'No todos in this folder yet' : (searchInput ? 'No todos match your search' : 'No todos yet')"
              :description="folderFilter
                ? 'Add your first task to this folder to start tracking it.'
                : (searchInput ? 'Try a different search term or clear the search.' : 'Get started by creating your first todo.')"
              action-text="Create Todo"
              @action="openCreate"
            />
            <ul v-else class="space-y-3">
              <li
                v-for="(todo, idx) in todos"
                :key="todo.id"
                class="bg-white dark:bg-secondary-800 rounded-lg p-4 border transition-colors duration-200"
                :class="dragOverIndex === idx
                  ? 'border-primary-500 ring-2 ring-primary-500/30'
                  : 'border-secondary-200 dark:border-secondary-700 hover:border-primary-300 dark:hover:border-primary-700'"
                draggable="true"
                @dragstart="onDragStart(idx, $event)"
                @dragover.prevent="onDragOver(idx, $event)"
                @dragleave="onDragLeave(idx)"
                @drop="onDrop(idx)"
                @dragend="onDragEnd"
              >
                <div class="flex items-start gap-3">
                  <input
                    v-if="selectMode"
                    type="checkbox"
                    class="flex-shrink-0 mt-1 rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                    :checked="selectedIds.has(todo.id)"
                    :aria-label="`Select ${todo.title}`"
                    @change="toggleSelected(todo.id)"
                  />
                  <span v-else class="flex-shrink-0 mt-1 text-secondary-300 dark:text-secondary-600 cursor-grab" aria-hidden="true" title="Drag to reorder">
                    <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><circle cx="9" cy="6" r="1.5" /><circle cx="9" cy="12" r="1.5" /><circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="6" r="1.5" /><circle cx="15" cy="12" r="1.5" /><circle cx="15" cy="18" r="1.5" /></svg>
                  </span>
                  <button
                    type="button"
                    class="flex-shrink-0 mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-1"
                    :class="todo.status === 'done'
                      ? 'bg-green-500 border-green-500 text-white'
                      : 'border-secondary-300 dark:border-secondary-600 hover:border-primary-500'"
                    :aria-label="todo.status === 'done' ? 'Mark as pending' : 'Mark as done'"
                    @click="toggleTodoStatus(todo)"
                  >
                    <svg v-if="todo.status === 'done'" class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
                  </button>

                  <div class="flex-1 min-w-0">
                    <p
                      class="text-sm font-medium transition-colors duration-150"
                      :class="todo.status === 'done'
                        ? 'text-secondary-400 dark:text-secondary-500 line-through'
                        : 'text-secondary-900 dark:text-white'"
                    >
                      {{ todo.title }}
                    </p>
                    <p v-if="todo.description" class="mt-1 text-xs text-secondary-500 dark:text-secondary-400 line-clamp-2">
                      {{ todo.description }}
                    </p>

                    <img
                      v-if="todo.image_url"
                      :src="resolveImageUrl(todo.image_url)"
                      :alt="`Image attached to ${todo.title}`"
                      class="mt-2 max-h-40 rounded-md border border-secondary-200 dark:border-secondary-700 object-cover"
                    />

                    <!-- Subtasks -->
                    <ul v-if="todo.subtasks?.length" class="mt-2 space-y-1">
                      <li v-for="s in todo.subtasks" :key="s.id" class="flex items-center gap-2 text-xs">
                        <input
                          type="checkbox"
                          :checked="s.done"
                          class="rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                          @change="toggleSubtask(todo, s.id)"
                        />
                        <span :class="s.done ? 'line-through text-secondary-400' : 'text-secondary-700 dark:text-secondary-300'">
                          {{ s.title }}
                        </span>
                      </li>
                    </ul>

                    <div class="mt-2 flex flex-wrap items-center gap-2">
                      <span
                        v-if="todo.folder_id && folderById[todo.folder_id]"
                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-100 text-secondary-700 dark:bg-secondary-700 dark:text-secondary-300"
                      >
                        <span
                          v-if="folderById[todo.folder_id].color"
                          class="inline-block w-1.5 h-1.5 rounded-full"
                          :style="{ backgroundColor: folderById[todo.folder_id].color! }"
                          aria-hidden="true"
                        ></span>
                        <span v-else aria-hidden="true">{{ folderById[todo.folder_id].icon || '📁' }}</span>
                        {{ folderById[todo.folder_id].name }}
                      </span>
                      <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium" :class="priorityClasses(todo.priority)">
                        {{ todo.priority }}
                      </span>
                      <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium" :class="statusClasses(todo.status)">
                        {{ formatStatus(todo.status) }}
                      </span>
                      <span
                        v-if="todo.due_date"
                        class="text-xs"
                        :class="isOverdue(todo) ? 'text-red-600 dark:text-red-400 font-medium' : 'text-secondary-500 dark:text-secondary-400'"
                      >
                        Due: {{ formatDate(todo.due_date) }}
                      </span>
                      <span
                        v-if="todo.reminder_at"
                        class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                        :class="reminderBadgeClasses(todo)"
                        :title="`Reminder: ${formatDateTime(todo.reminder_at)}`"
                      >
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
                        {{ reminderBadgeLabel(todo) }}
                      </span>
                      <span
                        v-if="todo.time_spent_seconds > 0"
                        class="text-xs text-secondary-500 dark:text-secondary-400"
                        :title="'Tracked focus time'"
                      >
                        🍅 {{ humanTime(todo.time_spent_seconds) }}
                      </span>
                      <span
                        v-for="t in todo.tags"
                        :key="t"
                        class="text-xs text-violet-700 dark:text-violet-300"
                      >
                        #{{ t }}
                      </span>
                    </div>
                  </div>

                  <div class="flex-shrink-0 flex items-center gap-1">
                    <button
                      type="button"
                      class="p-1.5 rounded-md text-secondary-400 hover:text-primary-600 hover:bg-secondary-100 dark:hover:text-primary-400 dark:hover:bg-secondary-700 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary-500"
                      aria-label="Edit todo"
                      @click="openEdit(todo)"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                    <button
                      type="button"
                      class="p-1.5 rounded-md text-secondary-400 hover:text-red-600 hover:bg-secondary-100 dark:hover:text-red-400 dark:hover:bg-secondary-700 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-red-500"
                      aria-label="Delete todo"
                      @click="confirmDelete(todo)"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                  </div>
                </div>
              </li>
            </ul>
          </section>

          <CalendarView v-if="view === 'calendar'" :todos="todos" @select="openEdit" />

          <PomodoroTimer v-if="view === 'focus'" :todos="todos" @logged="onPomodoroLogged" />
        </div>
      </div>

      <!-- Bulk action bar -->
      <BulkActionBar
        v-if="selectMode"
        :selected-count="selectedIds.size"
        :folders="folders"
        :busy="bulkBusy"
        @action="handleBulkAction"
        @clear="clearSelection"
      />

      <!-- Floating create button -->
      <button
        type="button"
        class="fixed bottom-6 right-6 w-14 h-14 bg-primary-600 hover:bg-primary-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all duration-200 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
        aria-label="Create new todo (n)"
        @click="openCreate"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
      </button>
    </main>

    <!-- Create / edit modal -->
    <TodoForm
      :visible="showForm"
      :todo="editingTodo"
      :folders="folders"
      :tag-suggestions="availableTags.map(t => t.name)"
      @submit="handleFormSubmit"
      @cancel="closeForm"
      @update:visible="(v: boolean) => { if (!v) closeForm() }"
    />

    <ConfirmDialog
      :visible="showDeleteConfirm"
      title="Delete Todo"
      message="Are you sure you want to delete this todo? This action cannot be undone."
      confirm-text="Delete"
      cancel-text="Cancel"
      variant="danger"
      @confirm="handleDeleteTodo"
      @cancel="showDeleteConfirm = false"
      @update:visible="showDeleteConfirm = $event"
    />

    <!-- Chatbot -->
    <ChatbotWidget v-if="aiEnabled" />

    <!-- Keyboard help -->
    <div
      v-if="showKeyboardHelp"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      @click.self="showKeyboardHelp = false"
    >
      <div class="absolute inset-0 bg-black/50"></div>
      <div class="relative bg-white dark:bg-secondary-800 rounded-xl shadow-xl p-6 w-full max-w-sm">
        <h2 class="text-base font-semibold text-secondary-900 dark:text-white mb-3">Keyboard shortcuts</h2>
        <dl class="text-sm space-y-2">
          <div class="flex justify-between"><dt>New todo</dt><dd><kbd class="px-1.5 py-0.5 rounded bg-secondary-100 dark:bg-secondary-700 text-xs">n</kbd></dd></div>
          <div class="flex justify-between"><dt>Focus search</dt><dd><kbd class="px-1.5 py-0.5 rounded bg-secondary-100 dark:bg-secondary-700 text-xs">/</kbd></dd></div>
          <div class="flex justify-between"><dt>List / Calendar / Focus</dt><dd><kbd class="px-1.5 py-0.5 rounded bg-secondary-100 dark:bg-secondary-700 text-xs">1</kbd> <kbd class="px-1.5 py-0.5 rounded bg-secondary-100 dark:bg-secondary-700 text-xs">2</kbd> <kbd class="px-1.5 py-0.5 rounded bg-secondary-100 dark:bg-secondary-700 text-xs">3</kbd></dd></div>
          <div class="flex justify-between"><dt>Show help</dt><dd><kbd class="px-1.5 py-0.5 rounded bg-secondary-100 dark:bg-secondary-700 text-xs">?</kbd></dd></div>
          <div class="flex justify-between"><dt>Close dialogs</dt><dd><kbd class="px-1.5 py-0.5 rounded bg-secondary-100 dark:bg-secondary-700 text-xs">Esc</kbd></dd></div>
        </dl>
        <button class="mt-4 btn-secondary text-sm w-full" @click="showKeyboardHelp = false">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useTodos } from '~/composables/useTodos'
import { useAuth } from '~/composables/useAuth'
import { useToast } from '~/composables/useToast'
import { useFolders } from '~/composables/useFolders'
import { useNotifications } from '~/composables/useNotifications'
import { todosApi, aiApi } from '~/utils/api'
import type { Folder, TagInfo, Todo, TodoCreate, TodoUpdate } from '~/types'

definePageMeta({ layout: false })

const router = useRouter()
const { logout } = useAuth()
const { success: toastSuccess, error: toastError, info: toastInfo } = useToast()
const {
  todos,
  stats,
  loading,
  error: todosError,
  fetchTodos,
  fetchStats,
  createTodo,
  updateTodo,
  deleteTodo,
  setFilter,
  setSortBy,
} = useTodos()
const {
  folders,
  stats: folderStats,
  fetchAll: fetchFolders,
  fetchStats: fetchFolderStats,
  create: createFolderFn,
  update: updateFolderFn,
  remove: removeFolderFn,
} = useFolders()
const { requestDesktopPermission } = useNotifications()

const calendarUrl = todosApi.calendarUrl()

// View / filters
type ViewId = 'list' | 'calendar' | 'focus'
const viewOptions: { id: ViewId; label: string }[] = [
  { id: 'list', label: 'List' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'focus', label: 'Focus' },
]
const view = ref<ViewId>('list')

const statusFilter = ref<string | undefined>(undefined)
const priorityFilter = ref<string | undefined>(undefined)
const sortBy = ref<string | undefined>(undefined)
const folderFilter = ref<string | null>(null)
const tagFilter = ref<string | undefined>(undefined)
const searchInput = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)

// Modals
const showForm = ref(false)
const editingTodo = ref<Todo | null>(null)
const showDeleteConfirm = ref(false)
const todoToDelete = ref<Todo | null>(null)
const loggingOut = ref(false)
const showKeyboardHelp = ref(false)
const summaryRefresh = ref(0)

// Drag & drop
const draggingIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

// Bulk selection
const selectMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const bulkBusy = ref(false)

const allVisibleSelected = computed(
  () => todos.value.length > 0 && todos.value.every((t) => selectedIds.value.has(t.id)),
)

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.value = new Set()
}

function toggleSelected(id: string) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function selectAllVisible() {
  if (allVisibleSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(todos.value.map((t) => t.id))
  }
}

function clearSelection() {
  selectedIds.value = new Set()
}

async function handleBulkAction(action: string, payload?: Record<string, unknown>) {
  const ids = Array.from(selectedIds.value)
  if (ids.length === 0) return
  bulkBusy.value = true
  try {
    const result = await todosApi.bulk(ids, action, payload)
    const s = result.summary
    const parts: string[] = []
    if (s.succeeded) parts.push(`${s.succeeded} updated`)
    if (s.no_change) parts.push(`${s.no_change} unchanged`)
    if (s.not_found) parts.push(`${s.not_found} missing`)
    if (s.validation_error) parts.push(`${s.validation_error} invalid`)
    toastSuccess(parts.length ? parts.join(', ') : 'Done')
    await Promise.all([fetchTodos(), fetchStats(), refreshTags()])
    clearSelection()
  } catch (err: any) {
    toastError(err?.data?.detail || err?.message || 'Bulk action failed')
  } finally {
    bulkBusy.value = false
  }
}

// AI status
const aiEnabled = ref(false)

// Tags
const availableTags = ref<TagInfo[]>([])

const folderById = computed<Record<string, Folder>>(() =>
  Object.fromEntries(folders.value.map((f) => [f.id, f])),
)
const activeFolder = computed<Folder | null>(() =>
  folderFilter.value && folderFilter.value !== 'none'
    ? folders.value.find((f) => f.id === folderFilter.value) ?? null
    : null,
)
const folderAllTotal = computed(() =>
  (stats.value?.total ?? 0) -
  (folderStats.value.find((s) => s.id === 'none')?.total ?? 0),
)

onMounted(async () => {
  await Promise.all([fetchTodos(), fetchStats(), fetchFolders(), refreshTags()])
  try {
    const status = await aiApi.status()
    aiEnabled.value = !!status?.enabled
  } catch {
    aiEnabled.value = false
  }
  // Best-effort: ask for desktop notification permission once.
  requestDesktopPermission()

  window.addEventListener('keydown', onKeyDown)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
})

// Search debounce
let searchHandle: ReturnType<typeof setTimeout> | null = null
watch(searchInput, (val) => {
  if (searchHandle) clearTimeout(searchHandle)
  searchHandle = setTimeout(() => {
    setFilter('search', val ? val.trim() : undefined)
    fetchTodos()
  }, 220)
})

watch(folderFilter, async (val) => {
  setFilter('folder_id', val ?? undefined)
  await fetchTodos()
})
watch(tagFilter, async (val) => {
  setFilter('tag', val)
  await fetchTodos()
})

async function refreshTags() {
  try {
    availableTags.value = await todosApi.tags()
  } catch {
    availableTags.value = []
  }
}

async function handleStatusFilter(value: string | undefined) {
  statusFilter.value = value
  setFilter('status', value)
  await fetchTodos()
}
async function handlePriorityFilter(value: string | undefined) {
  priorityFilter.value = value
  setFilter('priority', value)
  await fetchTodos()
}
async function handleSortBy(value: string | undefined) {
  sortBy.value = value
  setSortBy(value)
  await fetchTodos()
}

function openCreate() {
  editingTodo.value = null
  showForm.value = true
}
function openEdit(todo: Todo) {
  editingTodo.value = todo
  showForm.value = true
}
function closeForm() {
  showForm.value = false
  editingTodo.value = null
}

async function handleFormSubmit(payload: any) {
  if (editingTodo.value) {
    const id = editingTodo.value.id
    const data = payload as TodoUpdate & { _imageFile?: File | null; _removeImage?: boolean; _applyTo?: 'occurrence' | 'series' }
    const { _imageFile, _removeImage, _applyTo, ...rest } = data

    const result = await updateTodo(id, rest, _applyTo || 'occurrence')
    if (!result) {
      toastError(todosError.value || 'Could not save todo')
      return
    }

    if (_removeImage && result.image_url) {
      try {
        const updated = await todosApi.deleteImage(id)
        replaceTodo(updated)
      } catch {
        toastError('Could not remove image')
      }
    } else if (_imageFile) {
      try {
        const updated = await todosApi.uploadImage(id, _imageFile)
        replaceTodo(updated)
      } catch {
        toastError('Could not upload image')
      }
    }
    toastSuccess('Todo updated')
  } else {
    const data = payload as TodoCreate & { _imageFile?: File | null }
    const { _imageFile, ...rest } = data
    const created = await createTodo(rest)
    if (!created) {
      toastError(todosError.value || 'Could not create todo')
      return
    }
    if (_imageFile) {
      try {
        const updated = await todosApi.uploadImage(created.id, _imageFile)
        replaceTodo(updated)
      } catch {
        toastError('Created, but could not upload image')
      }
    }
    toastSuccess('Todo created')
  }

  closeForm()
  await Promise.all([fetchStats(), fetchFolderStats(), refreshTags()])
  summaryRefresh.value++
}

function replaceTodo(updated: Todo) {
  const idx = todos.value.findIndex((t) => t.id === updated.id)
  if (idx !== -1) todos.value[idx] = updated
}

async function toggleTodoStatus(todo: Todo) {
  const newStatus = todo.status === 'done' ? 'pending' : 'done'
  const result = await updateTodo(todo.id, { status: newStatus })
  if (result) {
    toastSuccess(newStatus === 'done' ? 'Todo completed' : 'Todo reopened')
    await Promise.all([fetchStats(), fetchFolderStats()])
    summaryRefresh.value++
  } else {
    toastError(todosError.value || 'Failed to update todo')
  }
}

async function toggleSubtask(todo: Todo, subtaskId: string) {
  const next = todo.subtasks.map((s) => (s.id === subtaskId ? { ...s, done: !s.done } : s))
  const result = await updateTodo(todo.id, { subtasks: next as any })
  if (!result) toastError(todosError.value || 'Failed to update subtask')
}

function confirmDelete(todo: Todo) {
  todoToDelete.value = todo
  showDeleteConfirm.value = true
}
async function handleDeleteTodo() {
  if (!todoToDelete.value) return
  const success = await deleteTodo(todoToDelete.value.id)
  showDeleteConfirm.value = false
  if (success) {
    toastSuccess('Todo deleted')
    await Promise.all([fetchStats(), fetchFolderStats(), refreshTags()])
    summaryRefresh.value++
  } else {
    toastError(todosError.value || 'Failed to delete todo')
  }
  todoToDelete.value = null
}

async function handleLogout() {
  loggingOut.value = true
  const success = await logout()
  loggingOut.value = false
  if (success) await router.push('/login')
}

// --- Folders -----
async function onCreateFolder(data: { name: string; color: string | null; icon: string | null }) {
  const created = await createFolderFn(data)
  if (created) toastSuccess(`Folder "${created.name}" created`)
  else toastError('Could not create folder')
}
async function onUpdateFolder(id: string, data: { name: string; color: string | null; icon: string | null }) {
  const updated = await updateFolderFn(id, data)
  if (updated) toastSuccess('Folder updated')
  else toastError('Could not update folder')
}
async function onDeleteFolder(id: string) {
  const ok = await removeFolderFn(id)
  if (ok) {
    toastInfo('Folder deleted. Todos are now unassigned.')
    if (folderFilter.value === id) folderFilter.value = null
    await fetchTodos()
  } else {
    toastError('Could not delete folder')
  }
}

// --- Pomodoro -----
async function onPomodoroLogged(todoId: string, _seconds: number) {
  // Refetch the affected todo so the time pill updates.
  try {
    const updated = await todosApi.get(todoId)
    replaceTodo(updated)
  } catch {
    /* ignore */
  }
}

// --- Drag & drop -----
function onDragStart(idx: number, event: DragEvent) {
  draggingIndex.value = idx
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(idx))
  }
}
function onDragOver(idx: number, event: DragEvent) {
  if (draggingIndex.value === null || draggingIndex.value === idx) return
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dragOverIndex.value = idx
}
function onDragLeave(idx: number) {
  if (dragOverIndex.value === idx) dragOverIndex.value = null
}
async function onDrop(idx: number) {
  if (draggingIndex.value === null || draggingIndex.value === idx) {
    onDragEnd()
    return
  }
  const reordered = [...todos.value]
  const [moved] = reordered.splice(draggingIndex.value, 1)
  reordered.splice(idx, 0, moved)
  todos.value.splice(0, todos.value.length, ...reordered)
  onDragEnd()
  // Persist
  try {
    await todosApi.reorder(reordered.map((t) => t.id))
    if (sortBy.value !== 'position') {
      sortBy.value = 'position'
      setSortBy('position')
    }
  } catch {
    toastError('Could not save new order')
    await fetchTodos()
  }
}
function onDragEnd() {
  draggingIndex.value = null
  dragOverIndex.value = null
}

// --- Keyboard shortcuts -----
function onKeyDown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  const tag = target?.tagName?.toLowerCase()
  const isTyping = tag === 'input' || tag === 'textarea' || tag === 'select' || target?.isContentEditable
  if (event.key === 'Escape') {
    if (showForm.value) closeForm()
    else if (showDeleteConfirm.value) showDeleteConfirm.value = false
    else if (showKeyboardHelp.value) showKeyboardHelp.value = false
    return
  }
  if (isTyping) return

  if (event.key === 'n') { event.preventDefault(); openCreate() }
  else if (event.key === '/') { event.preventDefault(); searchInputRef.value?.focus() }
  else if (event.key === '?') { event.preventDefault(); showKeyboardHelp.value = true }
  else if (event.key === '1') { view.value = 'list' }
  else if (event.key === '2') { view.value = 'calendar' }
  else if (event.key === '3') { view.value = 'focus' }
}

// --- Display helpers -----
function priorityClasses(priority: string): string {
  switch (priority) {
    case 'high': return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    case 'medium': return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
    case 'low': return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
    default: return 'bg-secondary-100 text-secondary-700 dark:bg-secondary-700 dark:text-secondary-300'
  }
}
function statusClasses(status: string): string {
  switch (status) {
    case 'done': return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
    case 'in-progress': return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
    case 'pending': return 'bg-secondary-100 text-secondary-700 dark:bg-secondary-700 dark:text-secondary-300'
    default: return 'bg-secondary-100 text-secondary-700 dark:bg-secondary-700 dark:text-secondary-300'
  }
}
function formatStatus(status: string): string {
  return status === 'in-progress' ? 'In Progress' : status.charAt(0).toUpperCase() + status.slice(1)
}
function formatDate(s: string): string {
  const d = new Date(s + 'T00:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}
function isOverdue(todo: Todo): boolean {
  if (!todo.due_date || todo.status === 'done') return false
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return new Date(todo.due_date + 'T00:00:00') < today
}
function reminderBadgeClasses(todo: Todo): string {
  if (!todo.reminder_at) return ''
  const r = new Date(todo.reminder_at)
  if (isNaN(r.getTime())) return 'bg-secondary-100 text-secondary-700'
  return r.getTime() > Date.now()
    ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400'
    : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
}
function reminderBadgeLabel(todo: Todo): string {
  if (!todo.reminder_at) return ''
  const r = new Date(todo.reminder_at)
  if (isNaN(r.getTime())) return 'Reminder'
  return r.getTime() > Date.now() ? 'Upcoming' : 'Due'
}
function humanTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  const remM = m % 60
  return remM ? `${h}h ${remM}m` : `${h}h`
}
function resolveImageUrl(url: string): string {
  if (url.startsWith('http')) return url
  return `http://localhost:8000${url.startsWith('/') ? '' : '/'}${url}`
}
</script>
