<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150"
      leave-active-class="transition-opacity duration-100"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="modelValue" class="fixed inset-0 z-40 bg-black/50" @click="close" />
    </Transition>

    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 translate-y-4"
      leave-to-class="opacity-0 translate-y-4"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-4 overflow-y-auto"
        role="dialog"
        aria-modal="true"
        aria-labelledby="image-import-title"
      >
        <div
          class="relative bg-white dark:bg-secondary-800 rounded-xl shadow-xl border border-secondary-200 dark:border-secondary-700 w-full max-w-2xl my-8"
          @click.stop
        >
          <header class="flex items-center justify-between px-5 py-3 border-b border-secondary-200 dark:border-secondary-700">
            <h2 id="image-import-title" class="text-base font-semibold text-secondary-900 dark:text-white">
              Import todos from image
            </h2>
            <button
              type="button"
              class="p-1.5 rounded-md text-secondary-500 hover:text-secondary-900 dark:hover:text-white hover:bg-secondary-100 dark:hover:bg-secondary-700"
              aria-label="Close"
              @click="close"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </header>

          <div class="px-5 py-4 space-y-4">
            <!-- Step 1: pick / drop a file -->
            <div v-if="items.length === 0 && !uploading">
              <label
                for="image-import-file"
                class="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-secondary-300 dark:border-secondary-600 rounded-lg py-10 cursor-pointer hover:border-primary-400 dark:hover:border-primary-500 transition-colors"
                :class="{ 'border-primary-500 bg-primary-50/30 dark:bg-primary-900/10': dragOver }"
                @dragover.prevent="dragOver = true"
                @dragleave="dragOver = false"
                @drop.prevent="onDrop"
              >
                <svg class="w-10 h-10 text-secondary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                <span class="text-sm text-secondary-700 dark:text-secondary-300">
                  Click to upload, or drag & drop
                </span>
                <span class="text-xs text-secondary-500 dark:text-secondary-400">
                  PNG, JPG, WEBP, GIF — up to 8 MB
                </span>
                <input
                  id="image-import-file"
                  ref="fileInput"
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp,image/gif"
                  class="sr-only"
                  @change="onFileChange"
                />
              </label>
            </div>

            <!-- Loading -->
            <div v-if="uploading" class="flex flex-col items-center justify-center py-10 gap-3">
              <svg class="animate-spin h-8 w-8 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              <p class="text-sm text-secondary-600 dark:text-secondary-400">
                Extracting todos from the image…
              </p>
            </div>

            <!-- Step 2: review extracted items -->
            <div v-if="items.length > 0 && !uploading">
              <!-- Mode toggle -->
              <div class="flex rounded-lg border border-secondary-200 dark:border-secondary-700 overflow-hidden mb-3 text-xs">
                <button
                  type="button"
                  class="flex-1 px-3 py-1.5 font-medium transition-colors"
                  :class="importMode === 'individual' ? 'bg-primary-600 text-white' : 'text-secondary-600 dark:text-secondary-300 hover:bg-secondary-100 dark:hover:bg-secondary-700'"
                  @click="importMode = 'individual'"
                >
                  Individual todos
                </button>
                <button
                  type="button"
                  class="flex-1 px-3 py-1.5 font-medium transition-colors border-l border-secondary-200 dark:border-secondary-700"
                  :class="importMode === 'single' ? 'bg-primary-600 text-white' : 'text-secondary-600 dark:text-secondary-300 hover:bg-secondary-100 dark:hover:bg-secondary-700'"
                  @click="importMode = 'single'"
                >
                  One todo + subtasks
                </button>
              </div>

              <!-- Single-todo mode: parent title input -->
              <div v-if="importMode === 'single'" class="mb-3">
                <label class="block text-xs text-secondary-600 dark:text-secondary-400 mb-1">
                  Todo title
                </label>
                <input
                  v-model="singleTitle"
                  type="text"
                  class="input-field text-sm"
                  maxlength="200"
                  placeholder="e.g. Grocery shopping"
                />
              </div>

              <div class="flex items-center justify-between mb-3">
                <p class="text-sm text-secondary-700 dark:text-secondary-300">
                  <template v-if="importMode === 'individual'">
                    Found <strong>{{ items.length }}</strong> item{{ items.length === 1 ? '' : 's' }}.
                    Review and choose which to create.
                  </template>
                  <template v-else>
                    <strong>{{ items.length }}</strong> item{{ items.length === 1 ? '' : 's' }} will become subtasks.
                  </template>
                </p>
                <div v-if="importMode === 'individual'" class="flex items-center gap-2 text-xs">
                  <button type="button" class="text-primary-600 hover:underline" @click="selectAll">All</button>
                  <span class="text-secondary-400">·</span>
                  <button type="button" class="text-primary-600 hover:underline" @click="selectNone">None</button>
                </div>
              </div>

              <div class="mb-3">
                <label class="block text-xs text-secondary-600 dark:text-secondary-400 mb-1">
                  Target folder
                </label>
                <select v-model="batchFolderId" class="input-field text-sm">
                  <option value="">(no folder)</option>
                  <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
                </select>
              </div>

              <ul class="space-y-2 max-h-72 overflow-y-auto pr-1">
                <li
                  v-for="(item, idx) in items"
                  :key="idx"
                  class="flex items-start gap-3 p-2 rounded border border-secondary-200 dark:border-secondary-700"
                >
                  <input
                    v-if="importMode === 'individual'"
                    type="checkbox"
                    class="mt-2 rounded text-primary-600 focus:ring-primary-500"
                    :checked="item._selected"
                    :aria-label="`Include ${item.title}`"
                    @change="item._selected = ($event.target as HTMLInputElement).checked"
                  />
                  <span v-else class="mt-2 text-secondary-400 select-none">•</span>
                  <div class="flex-1 min-w-0 space-y-1">
                    <input
                      v-model="item.title"
                      type="text"
                      class="input-field text-sm"
                      maxlength="200"
                    />
                    <div v-if="importMode === 'individual'" class="flex items-center gap-2 text-xs">
                      <select v-model="item.priority" class="text-xs border border-secondary-300 dark:border-secondary-700 rounded px-1.5 py-0.5 bg-white dark:bg-secondary-800 dark:text-white">
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                      <input
                        v-model="item.due_date"
                        type="date"
                        class="text-xs border border-secondary-300 dark:border-secondary-700 rounded px-1.5 py-0.5 bg-white dark:bg-secondary-800 dark:text-white"
                      />
                      <span v-if="item.tags && item.tags.length" class="text-secondary-500 truncate">
                        #{{ item.tags.join(' #') }}
                      </span>
                    </div>
                  </div>
                </li>
              </ul>
            </div>
          </div>

          <footer class="flex items-center justify-end gap-2 px-5 py-3 border-t border-secondary-200 dark:border-secondary-700">
            <button
              type="button"
              class="btn-secondary text-sm"
              :disabled="creating"
              @click="close"
            >
              Cancel
            </button>
            <button
              v-if="items.length > 0"
              type="button"
              class="btn-primary text-sm"
              :disabled="creating || (importMode === 'individual' && selectedCount === 0) || (importMode === 'single' && !singleTitle.trim())"
              @click="createSelected"
            >
              <span v-if="creating">Creating…</span>
              <span v-else-if="importMode === 'single'">Create todo with {{ items.length }} subtask{{ items.length === 1 ? '' : 's' }}</span>
              <span v-else>Create {{ selectedCount }} todo{{ selectedCount === 1 ? '' : 's' }}</span>
            </button>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { aiApi, todosApi, type ParsedTodo } from '~/utils/api'
import { useToast } from '~/composables/useToast'
import type { Folder, TodoCreate } from '~/types'

interface DialogItem extends ParsedTodo {
  _selected: boolean
}

const props = defineProps<{
  modelValue: boolean
  folders: Folder[]
  defaultFolderId?: string | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'created'): void
}>()

const { success: toastSuccess, error: toastError } = useToast()

const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
const uploading = ref(false)
const creating = ref(false)
const items = ref<DialogItem[]>([])
const batchFolderId = ref<string>('')
const importMode = ref<'individual' | 'single'>('individual')
const singleTitle = ref('')

const selectedCount = computed(() => items.value.filter((i) => i._selected).length)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      items.value = []
      dragOver.value = false
      uploading.value = false
      creating.value = false
      batchFolderId.value = props.defaultFolderId ?? ''
      importMode.value = 'individual'
      singleTitle.value = ''
    }
  },
)

function close() {
  if (creating.value) return
  emit('update:modelValue', false)
}

async function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) await upload(file)
  if (fileInput.value) fileInput.value.value = ''
}

async function onDrop(e: DragEvent) {
  dragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) await upload(file)
}

async function upload(file: File) {
  if (uploading.value) return
  uploading.value = true
  try {
    const result = await aiApi.parseImage(file)
    items.value = (result.items || []).map((it) => ({
      title: it.title,
      priority: (it.priority as 'low' | 'medium' | 'high' | null) ?? 'medium',
      due_date: (it.due_date as string | null) ?? '',
      tags: Array.isArray(it.tags) ? it.tags : [],
      _selected: true,
    }))
    if (items.value.length === 0) {
      toastError('No todos found in that image.')
    } else if (!singleTitle.value) {
      // Auto-suggest a parent title from the first item when switching to single mode
      singleTitle.value = items.value[0]?.title?.slice(0, 60) || ''
    }
  } catch (err: any) {
    const status = err?.response?.status || err?.statusCode
    if (status === 503) {
      toastError('Vision OCR requires an OpenAI API key.')
    } else if (status === 415) {
      toastError('Unsupported image type.')
    } else if (status === 413) {
      toastError('Image too large (max 8 MB).')
    } else {
      toastError('Could not extract todos from that image.')
    }
  } finally {
    uploading.value = false
  }
}

function selectAll() {
  items.value.forEach((i) => (i._selected = true))
}
function selectNone() {
  items.value.forEach((i) => (i._selected = false))
}

async function createSelected() {
  creating.value = true
  const folderId = batchFolderId.value || null

  if (importMode.value === 'single') {
    const title = singleTitle.value.trim().slice(0, 200) || 'Imported list'
    const subtasks = items.value.map((it, idx) => ({
      id: `sub-${Date.now()}-${idx}`,
      title: it.title.trim().slice(0, 200) || 'Item',
      done: false,
    }))
    try {
      await todosApi.create({ title, folder_id: folderId, subtasks })
      toastSuccess(`Created 1 todo with ${subtasks.length} subtask${subtasks.length === 1 ? '' : 's'}.`)
      emit('created')
      emit('update:modelValue', false)
    } catch {
      toastError('Failed to create todo.')
    } finally {
      creating.value = false
    }
    return
  }

  const chosen = items.value.filter((i) => i._selected)
  if (chosen.length === 0) { creating.value = false; return }

  const results = await Promise.allSettled(
    chosen.map((it) => {
      const payload: TodoCreate = {
        title: it.title.trim().slice(0, 200) || 'Untitled',
        priority: (it.priority as 'low' | 'medium' | 'high') || 'medium',
        due_date: it.due_date || undefined,
        tags: it.tags && it.tags.length ? it.tags : undefined,
        folder_id: folderId,
      }
      return todosApi.create(payload)
    }),
  )
  creating.value = false

  const failed: number[] = []
  results.forEach((r, i) => {
    if (r.status === 'rejected') failed.push(i)
  })

  if (failed.length === 0) {
    toastSuccess(`Created ${chosen.length} todo${chosen.length === 1 ? '' : 's'}.`)
    emit('created')
    emit('update:modelValue', false)
  } else {
    const failedIds = new Set(failed.map((idx) => chosen[idx]))
    items.value.forEach((it) => (it._selected = failedIds.has(it)))
    toastError(`${failed.length} of ${chosen.length} todos failed to create. Try again.`)
    if (failed.length < chosen.length) emit('created')
  }
}
</script>
