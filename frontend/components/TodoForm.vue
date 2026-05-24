<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200 ease-out"
      leave-active-class="transition-opacity duration-150 ease-in"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="formTitleId"
      >
        <div class="absolute inset-0 bg-black/50 dark:bg-black/70" @click="handleCancel"></div>

        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          leave-active-class="transition-all duration-150 ease-in"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="visible"
            class="relative w-full max-w-2xl bg-white dark:bg-secondary-800 rounded-xl shadow-xl p-6 max-h-[92vh] overflow-y-auto"
          >
            <div class="flex items-center justify-between mb-5">
              <h2 :id="formTitleId" class="text-xl font-semibold text-secondary-900 dark:text-white">
                {{ isEditing ? 'Edit Todo' : 'Create Todo' }}
              </h2>
              <button
                type="button"
                class="text-secondary-400 hover:text-secondary-600 dark:hover:text-secondary-300 transition-colors duration-200"
                aria-label="Close"
                @click="handleCancel"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <form @submit.prevent="handleSubmit" novalidate>
              <!-- Title with mic -->
              <div class="mb-4">
                <label for="todo-title" class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">
                  Title <span class="text-red-500">*</span>
                </label>
                <div class="relative">
                  <input
                    id="todo-title"
                    v-model="form.title"
                    type="text"
                    class="input-field pr-10"
                    :class="{ 'border-red-500 focus:ring-red-500 focus:border-red-500': errors.title }"
                    placeholder="What needs to be done?"
                    maxlength="200"
                    :disabled="submitting"
                  />
                  <button
                    v-if="voice.supported"
                    type="button"
                    class="absolute inset-y-0 right-0 flex items-center justify-center w-9 transition-colors duration-150"
                    :class="micButtonClasses"
                    :aria-label="voice.listening.value ? 'Stop voice input' : 'Start voice input'"
                    @click="onVoiceClick"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 11-14 0M12 18v3m-4 0h8M12 3a3 3 0 00-3 3v5a3 3 0 006 0V6a3 3 0 00-3-3z" /></svg>
                  </button>
                </div>
                <p v-if="errors.title" class="mt-1.5 text-sm text-red-600 dark:text-red-400" role="alert">{{ errors.title }}</p>
                <p v-else-if="voice.listening.value" class="mt-1 text-xs text-red-500 dark:text-red-400 animate-pulse">
                  Listening… click mic to stop.
                </p>
                <p v-else-if="voice.transcribing.value" class="mt-1 text-xs text-secondary-500 dark:text-secondary-400">
                  Transcribing with Whisper…
                </p>
                <p v-else-if="voice.error.value" class="mt-1 text-xs text-red-600 dark:text-red-400">
                  {{ voice.error.value }}
                </p>
              </div>

              <!-- Description -->
              <div class="mb-4">
                <label for="todo-description" class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">
                  Description
                </label>
                <textarea
                  id="todo-description"
                  v-model="form.description"
                  class="input-field resize-none"
                  :class="{ 'border-red-500 focus:ring-red-500 focus:border-red-500': errors.description }"
                  placeholder="Add more details (optional)"
                  rows="3"
                  maxlength="2000"
                  :disabled="submitting"
                ></textarea>
                <p v-if="errors.description" class="mt-1.5 text-sm text-red-600 dark:text-red-400" role="alert">{{ errors.description }}</p>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <label for="todo-folder" class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">Folder</label>
                  <select id="todo-folder" v-model="form.folder_id" class="input-field" :disabled="submitting">
                    <option value="">No folder</option>
                    <option v-for="f in folders" :key="f.id" :value="f.id">
                      {{ f.icon ? `${f.icon} ` : '' }}{{ f.name }}
                    </option>
                  </select>
                </div>
                <div>
                  <label for="todo-status" class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">Status</label>
                  <select id="todo-status" v-model="form.status" class="input-field" :disabled="submitting">
                    <option value="pending">Pending</option>
                    <option value="in-progress">In Progress</option>
                    <option value="done">Done</option>
                  </select>
                </div>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <label for="todo-priority" class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">Priority</label>
                  <select id="todo-priority" v-model="form.priority" class="input-field" :disabled="submitting">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
                <div>
                  <label for="todo-due-date" class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">Due Date</label>
                  <input
                    id="todo-due-date"
                    v-model="form.due_date"
                    type="date"
                    class="input-field"
                    :class="{ 'border-red-500': errors.due_date }"
                    :disabled="submitting"
                  />
                  <p v-if="errors.due_date" class="mt-1.5 text-sm text-red-600 dark:text-red-400" role="alert">{{ errors.due_date }}</p>
                </div>
              </div>

              <div class="mb-4">
                <label for="todo-reminder-at" class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">Reminder</label>
                <input
                  id="todo-reminder-at"
                  v-model="form.reminder_at"
                  type="datetime-local"
                  class="input-field"
                  :class="{ 'border-red-500': errors.reminder_at }"
                  :disabled="submitting"
                />
                <p v-if="errors.reminder_at" class="mt-1.5 text-sm text-red-600 dark:text-red-400" role="alert">{{ errors.reminder_at }}</p>
                <p v-else class="mt-1 text-xs text-secondary-500 dark:text-secondary-400">Set a date and time to be reminded</p>
              </div>

              <!-- Tags -->
              <div class="mb-4">
                <label class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">Tags</label>
                <div class="flex flex-wrap items-center gap-1.5 p-2 input-field min-h-[2.5rem]">
                  <span
                    v-for="tag in form.tags"
                    :key="tag"
                    class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300"
                  >
                    #{{ tag }}
                    <button type="button" class="hover:text-red-600 focus:outline-none" :aria-label="`Remove tag ${tag}`" @click="removeTag(tag)">×</button>
                  </span>
                  <input
                    v-model="tagDraft"
                    type="text"
                    class="flex-1 min-w-[6rem] bg-transparent border-0 focus:ring-0 text-sm p-0"
                    placeholder="Type and press Enter"
                    :disabled="submitting"
                    @keydown.enter.prevent="commitTagDraft"
                    @keydown.="onTagBackspace"
                  />
                </div>
                <div v-if="suggestionPool.length" class="mt-1.5 flex flex-wrap gap-1.5">
                  <button
                    v-for="s in suggestionPool"
                    :key="s"
                    type="button"
                    class="text-xs px-2 py-0.5 rounded-full bg-secondary-100 text-secondary-700 hover:bg-secondary-200 dark:bg-secondary-700 dark:text-secondary-300 dark:hover:bg-secondary-600"
                    @click="addTag(s)"
                  >
                    + {{ s }}
                  </button>
                </div>
              </div>

              <!-- Subtasks -->
              <div class="mb-4">
                <div class="flex items-center justify-between mb-1.5">
                  <label class="block text-sm font-medium text-secondary-700 dark:text-secondary-300">Subtasks</label>
                  <button
                    v-if="aiAvailable && isEditing"
                    type="button"
                    class="text-xs text-violet-600 dark:text-violet-400 hover:underline disabled:opacity-50"
                    :disabled="suggesting"
                    @click="suggestSubtasks"
                  >
                    {{ suggesting ? 'Thinking…' : '✨ Suggest with AI' }}
                  </button>
                </div>
                <ul v-if="form.subtasks.length" class="space-y-1.5 mb-2">
                  <li v-for="(s, i) in form.subtasks" :key="s.id" class="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      v-model="s.done"
                      class="rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                    />
                    <input
                      v-model="s.title"
                      type="text"
                      class="flex-1 bg-transparent border-0 border-b border-secondary-200 dark:border-secondary-700 focus:ring-0 focus:border-primary-500 text-sm py-1 px-0"
                      :class="s.done ? 'line-through text-secondary-400' : ''"
                      maxlength="200"
                    />
                    <button type="button" class="text-secondary-400 hover:text-red-600 focus:outline-none" :aria-label="`Remove subtask ${i + 1}`" @click="removeSubtask(s.id)">×</button>
                  </li>
                </ul>
                <div class="flex items-center gap-2">
                  <input
                    v-model="subtaskDraft"
                    type="text"
                    class="input-field text-sm flex-1"
                    placeholder="Add a subtask…"
                    maxlength="200"
                    :disabled="submitting"
                    @keydown.enter.prevent="commitSubtaskDraft"
                  />
                  <button type="button" class="btn-secondary text-sm" :disabled="!subtaskDraft.trim()" @click="commitSubtaskDraft">Add</button>
                </div>
              </div>

              <!-- Recurrence -->
              <div class="mb-4 rounded-md border border-secondary-200 dark:border-secondary-700 p-3">
                <div class="flex items-center gap-2 mb-2">
                  <label class="text-sm font-medium text-secondary-700 dark:text-secondary-300">🔁 Repeats</label>
                  <select v-model="form.recurrence" class="text-sm bg-white dark:bg-secondary-800 border border-secondary-300 dark:border-secondary-700 rounded px-2 py-1">
                    <option value="none">None</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="yearly">Yearly</option>
                  </select>
                </div>
                <div v-if="form.recurrence !== 'none'" class="flex flex-wrap gap-3 text-xs">
                  <label class="flex items-center gap-1">
                    Ends on
                    <input type="date" v-model="form.recurrence_until" :disabled="!!form.recurrence_count" class="text-xs border border-secondary-300 dark:border-secondary-700 rounded px-1 bg-white dark:bg-secondary-800" />
                  </label>
                  <label class="flex items-center gap-1">
                    After N times
                    <input type="number" min="1" max="1000" v-model.number="form.recurrence_count" :disabled="!!form.recurrence_until" class="w-20 text-xs border border-secondary-300 dark:border-secondary-700 rounded px-1 bg-white dark:bg-secondary-800" />
                  </label>
                </div>
                <div v-if="isEditing && (props.todo?.recurrence && props.todo.recurrence !== 'none')" class="mt-2 text-xs">
                  <label class="mr-2">Apply to:</label>
                  <label class="mr-3"><input type="radio" v-model="applyTo" value="occurrence" /> this occurrence</label>
                  <label><input type="radio" v-model="applyTo" value="series" /> this and future</label>
                </div>
              </div>

              <!-- Image -->
              <div class="mb-4">
                <label class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">Image</label>
                <div v-if="imagePreview" class="mb-2 flex items-start gap-3">
                  <img :src="imagePreview" alt="Selected attachment" class="max-h-32 rounded-md border border-secondary-200 dark:border-secondary-700" />
                  <button type="button" class="text-xs text-red-600 dark:text-red-400 hover:underline" @click="clearImage">Remove</button>
                </div>
                <input
                  type="file"
                  accept="image/png, image/jpeg, image/gif, image/webp"
                  class="block text-xs text-secondary-700 dark:text-secondary-300 file:mr-3 file:rounded-md file:border-0 file:bg-secondary-100 dark:file:bg-secondary-700 file:px-3 file:py-1.5 file:text-xs hover:file:bg-secondary-200 dark:hover:file:bg-secondary-600"
                  :disabled="submitting"
                  @change="onImageChange"
                />
              </div>

              <div v-if="errors.general" class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg" role="alert">
                <p class="text-sm text-red-700 dark:text-red-400">{{ errors.general }}</p>
              </div>

              <CommentsSection v-if="isEditing && props.todo" :key="props.todo.id" :todo-id="props.todo.id" />

              <div class="flex gap-3 justify-end">
                <button type="button" class="btn-secondary" :disabled="submitting" @click="handleCancel">Cancel</button>
                <button type="submit" class="btn-primary flex items-center gap-2" :disabled="submitting">
                  <svg v-if="submitting" class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>{{ submitting ? 'Saving...' : (isEditing ? 'Save Changes' : 'Create Todo') }}</span>
                </button>
              </div>
            </form>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useVoiceInput } from '~/composables/useVoiceInput'
import { todosApi, aiApi } from '~/utils/api'
import type { Folder, Subtask, Todo, TodoCreate, TodoUpdate } from '~/types'
import CommentsSection from './CommentsSection.vue'

interface Props {
  visible: boolean
  todo?: Todo | null
  folders?: Folder[]
  tagSuggestions?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  todo: null,
  folders: () => [],
  tagSuggestions: () => [],
})

const emit = defineEmits<{
  submit: [data: (TodoCreate | TodoUpdate) & { _imageFile?: File | null; _removeImage?: boolean }]
  cancel: []
  'update:visible': [value: boolean]
}>()

const formTitleId = useId()
const isEditing = computed(() => !!props.todo)

const form = reactive({
  title: '',
  description: '',
  priority: 'medium' as 'low' | 'medium' | 'high',
  due_date: '',
  reminder_at: '',
  status: 'pending' as 'pending' | 'in-progress' | 'done',
  folder_id: '' as string,
  tags: [] as string[],
  subtasks: [] as Subtask[],
  recurrence: 'none' as 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly',
  recurrence_until: '',
  recurrence_count: null as number | null,
})

const applyTo = ref<'occurrence' | 'series'>('occurrence')

const errors = reactive({
  title: '',
  description: '',
  due_date: '',
  reminder_at: '',
  general: '',
})

const submitting = ref(false)
const tagDraft = ref('')
const subtaskDraft = ref('')
const imageFile = ref<File | null>(null)
const imagePreview = ref<string | null>(null)
const removeImageFlag = ref(false)
const aiAvailable = ref(false)
const suggesting = ref(false)
const voice = useVoiceInput()

const suggestionPool = computed(() =>
  (props.tagSuggestions || []).filter((s) => !form.tags.includes(s)).slice(0, 6),
)

const micButtonClasses = computed(() => {
  if (voice.listening.value) return 'text-red-600 dark:text-red-400 animate-pulse'
  if (voice.transcribing.value) return 'text-violet-600 dark:text-violet-400 animate-pulse'
  return 'text-secondary-500 hover:text-primary-600 dark:hover:text-primary-400'
})

watch(
  () => props.visible,
  async (newVal) => {
    if (newVal) {
      clearErrors()
      hydrateFromProps()
      try {
        const status = await aiApi.status()
        aiAvailable.value = !!status?.enabled
      } catch {
        aiAvailable.value = false
      }
    } else {
      voice.stop()
    }
  },
)

watch(
  () => props.todo,
  () => {
    if (props.visible) hydrateFromProps()
  },
)

function hydrateFromProps() {
  imageFile.value = null
  imagePreview.value = null
  removeImageFlag.value = false
  if (props.todo) {
    form.title = props.todo.title
    form.description = props.todo.description ?? ''
    form.priority = props.todo.priority
    form.due_date = props.todo.due_date ?? ''
    form.reminder_at = isoToLocalInput(props.todo.reminder_at)
    form.status = props.todo.status
    form.folder_id = props.todo.folder_id ?? ''
    form.tags = [...(props.todo.tags || [])]
    form.subtasks = (props.todo.subtasks || []).map((s) => ({ ...s }))
    form.recurrence = (props.todo.recurrence || 'none') as any
    form.recurrence_until = props.todo.recurrence_until ?? ''
    form.recurrence_count = props.todo.recurrence_count ?? null
    if (props.todo.image_url) {
      imagePreview.value = resolveImageUrl(props.todo.image_url)
    }
  } else {
    form.title = ''
    form.description = ''
    form.priority = 'medium'
    form.due_date = ''
    form.reminder_at = ''
    form.status = 'pending'
    form.folder_id = ''
    form.tags = []
    form.subtasks = []
    form.recurrence = 'none'
    form.recurrence_until = ''
    form.recurrence_count = null
  }
  applyTo.value = 'occurrence'
}

function clearErrors() {
  errors.title = ''
  errors.description = ''
  errors.due_date = ''
  errors.reminder_at = ''
  errors.general = ''
}

function isoToLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function localInputToIso(value: string): string | null {
  if (!value) return null
  const d = new Date(value)
  if (isNaN(d.getTime())) return null
  return d.toISOString()
}

function resolveImageUrl(url: string): string {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return `http://localhost:8000${url.startsWith('/') ? '' : '/'}${url}`
}

function commitTagDraft() {
  addTag(tagDraft.value)
  tagDraft.value = ''
}
function addTag(raw: string) {
  const cleaned = raw.trim().toLowerCase().replace(/^#+/, '')
  if (!cleaned) return
  if (form.tags.includes(cleaned)) return
  if (cleaned.length > 32) return
  form.tags.push(cleaned)
}
function removeTag(tag: string) {
  form.tags = form.tags.filter((t) => t !== tag)
}
function onTagBackspace() {
  if (tagDraft.value) return
  form.tags.pop()
}

function commitSubtaskDraft() {
  const title = subtaskDraft.value.trim()
  if (!title) return
  form.subtasks.push({ id: cryptoRandomId(), title, done: false })
  subtaskDraft.value = ''
}
function removeSubtask(id: string) {
  form.subtasks = form.subtasks.filter((s) => s.id !== id)
}
function cryptoRandomId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return Math.random().toString(36).slice(2, 11)
}

async function suggestSubtasks() {
  if (!props.todo) return
  suggesting.value = true
  try {
    const items = await todosApi.suggestSubtasks(props.todo.id)
    for (const item of items) {
      if (!form.subtasks.some((s) => s.title.toLowerCase() === item.title.toLowerCase())) {
        form.subtasks.push({ id: cryptoRandomId(), title: item.title, done: false })
      }
    }
  } catch {
    /* ignore - the AI status check covers the unavailable case */
  } finally {
    suggesting.value = false
  }
}

function onVoiceClick() {
  if (voice.listening.value || voice.transcribing.value) {
    voice.stop()
    return
  }
  voice.start((text) => {
    if (text) form.title = text
  })
}

function onImageChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  if (!file) return
  imageFile.value = file
  removeImageFlag.value = false
  const reader = new FileReader()
  reader.onload = () => {
    imagePreview.value = reader.result as string
  }
  reader.readAsDataURL(file)
}

function clearImage() {
  imageFile.value = null
  imagePreview.value = null
  if (props.todo?.image_url) removeImageFlag.value = true
}

function validate(): boolean {
  clearErrors()
  let valid = true
  const t = form.title.trim()
  if (!t) { errors.title = 'Title is required'; valid = false }
  else if (t.length > 200) { errors.title = 'Title must be 200 characters or less'; valid = false }
  if (form.description && form.description.length > 2000) {
    errors.description = 'Description must be 2000 characters or less'
    valid = false
  }
  if (form.due_date && !/^\d{4}-\d{2}-\d{2}$/.test(form.due_date)) {
    errors.due_date = 'Due date must be YYYY-MM-DD'
    valid = false
  }
  if (form.reminder_at) {
    const r = new Date(form.reminder_at)
    if (isNaN(r.getTime())) { errors.reminder_at = 'Invalid date and time'; valid = false }
  }
  if (form.recurrence !== 'none' && !form.due_date) {
    errors.due_date = 'Recurring todos require a due date'
    valid = false
  }
  if (form.recurrence_until && form.recurrence_count) {
    errors.general = 'Set either an end date or a count, not both'
    valid = false
  }
  return valid
}

function handleSubmit() {
  if (!validate()) return
  submitting.value = true

  if (isEditing.value) {
    const data: TodoUpdate & { _imageFile?: File | null; _removeImage?: boolean } = {}
    const todo = props.todo!
    if (form.title.trim() !== todo.title) data.title = form.title.trim()
    const newDesc = form.description.trim() || null
    if (newDesc !== (todo.description ?? null)) data.description = newDesc
    if (form.priority !== todo.priority) data.priority = form.priority
    const newDue = form.due_date || null
    if (newDue !== (todo.due_date ?? null)) data.due_date = newDue
    const newReminder = localInputToIso(form.reminder_at)
    const currentReminder = todo.reminder_at ?? null
    const reminderChanged = (() => {
      if (newReminder === currentReminder) return false
      if (newReminder && currentReminder) {
        return new Date(newReminder).getTime() !== new Date(currentReminder).getTime()
      }
      return true
    })()
    if (reminderChanged) data.reminder_at = newReminder
    if (form.status !== todo.status) data.status = form.status
    const newFolder = form.folder_id || null
    if (newFolder !== (todo.folder_id ?? null)) data.folder_id = form.folder_id || ''
    if (!sameStringArray(form.tags, todo.tags || [])) data.tags = [...form.tags]
    if (subtasksDiffer(form.subtasks, todo.subtasks || [])) data.subtasks = form.subtasks.map((s) => ({ ...s })) as any

    if (imageFile.value) data._imageFile = imageFile.value
    if (removeImageFlag.value && !imageFile.value) data._removeImage = true

    if (form.recurrence !== (todo.recurrence || 'none')) data.recurrence = form.recurrence
    const newUntil = form.recurrence_until || null
    if (newUntil !== (todo.recurrence_until ?? null)) data.recurrence_until = newUntil
    const newCount = form.recurrence_count ?? null
    if (newCount !== (todo.recurrence_count ?? null)) data.recurrence_count = newCount as any

    ;(data as any)._applyTo = applyTo.value
    emit('submit', data)
  } else {
    const data: TodoCreate & { _imageFile?: File | null } = {
      title: form.title.trim(),
      priority: form.priority,
      status: form.status,
    }
    const desc = form.description.trim()
    if (desc) data.description = desc
    if (form.due_date) data.due_date = form.due_date
    const reminderIso = localInputToIso(form.reminder_at)
    if (reminderIso) data.reminder_at = reminderIso
    if (form.folder_id) data.folder_id = form.folder_id
    if (form.tags.length) data.tags = [...form.tags]
    if (form.subtasks.length) data.subtasks = form.subtasks.map((s) => ({ ...s })) as any
    if (imageFile.value) data._imageFile = imageFile.value
    if (form.recurrence !== 'none') {
      data.recurrence = form.recurrence
      if (form.recurrence_until) data.recurrence_until = form.recurrence_until
      if (form.recurrence_count) data.recurrence_count = form.recurrence_count
    }
    emit('submit', data)
  }
  submitting.value = false
}

function sameStringArray(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
}
function subtasksDiffer(a: Subtask[], b: Subtask[]): boolean {
  if (a.length !== b.length) return true
  for (let i = 0; i < a.length; i++) {
    if (a[i].title !== b[i].title) return true
    if (a[i].done !== b[i].done) return true
  }
  return false
}

function handleCancel() {
  emit('cancel')
  emit('update:visible', false)
}
</script>
