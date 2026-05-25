<template>
  <aside class="bg-white dark:bg-secondary-800 rounded-lg border border-secondary-200 dark:border-secondary-700 p-3">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-secondary-900 dark:text-white">Folders</h3>
      <button
        type="button"
        class="text-xs text-primary-600 dark:text-primary-400 hover:underline focus:outline-none"
        @click="openCreate"
      >
        + New
      </button>
    </div>

    <ul class="space-y-1">
      <li>
        <button
          type="button"
          class="w-full flex items-center justify-between px-2 py-1.5 rounded-md text-sm transition-colors duration-150"
          :class="modelValue == null ? activeClasses : inactiveClasses"
          @click="select(null)"
        >
          <span class="flex items-center gap-2">
            <span aria-hidden="true">🗂</span>
            <span>All</span>
          </span>
          <span class="text-xs text-secondary-400">{{ totalCount }}</span>
        </button>
      </li>
      <li v-for="f in folders" :key="f.id">
        <div
          class="group flex items-center gap-1 px-2 py-1.5 rounded-md text-sm transition-colors duration-150"
          :class="modelValue === f.id ? activeClasses : inactiveClasses"
        >
          <button
            type="button"
            class="flex-1 flex items-center gap-2 truncate text-left focus:outline-none"
            @click="select(f.id)"
          >
            <span
              v-if="f.color"
              class="inline-block w-2.5 h-2.5 rounded-full"
              :style="{ backgroundColor: f.color }"
              aria-hidden="true"
            ></span>
            <span v-else aria-hidden="true">{{ f.icon || '📁' }}</span>
            <span class="truncate">{{ f.name }}</span>
          </button>
          <span class="text-xs text-secondary-400">{{ countFor(f.id) }}</span>
          <button
            type="button"
            class="opacity-0 group-hover:opacity-100 text-secondary-400 hover:text-primary-600 dark:hover:text-primary-400 transition-opacity duration-150 px-1"
            aria-label="Edit folder"
            @click.stop="openEdit(f)"
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
          </button>
        </div>
      </li>
      <li>
        <button
          type="button"
          class="w-full flex items-center justify-between px-2 py-1.5 rounded-md text-sm transition-colors duration-150"
          :class="modelValue === 'none' ? activeClasses : inactiveClasses"
          @click="select('none')"
        >
          <span class="flex items-center gap-2">
            <span aria-hidden="true">🗒</span>
            <span>Unassigned</span>
          </span>
          <span class="text-xs text-secondary-400">{{ unassignedCount }}</span>
        </button>
      </li>
    </ul>

    <!-- Create / Edit dialog -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-150 ease-out"
        leave-active-class="transition-opacity duration-100 ease-in"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="dialogOpen"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div class="absolute inset-0 bg-black/50 dark:bg-black/70" @click="closeDialog"></div>
          <div class="relative w-full max-w-sm bg-white dark:bg-secondary-800 rounded-xl shadow-xl p-5">
            <h2 class="text-base font-semibold text-secondary-900 dark:text-white mb-4">
              {{ editing ? 'Edit folder' : 'New folder' }}
            </h2>
            <form @submit.prevent="save" novalidate>
              <label class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mb-1.5">
                Name
              </label>
              <input
                v-model="form.name"
                type="text"
                class="input-field"
                placeholder="School project"
                maxlength="80"
                required
              />

              <label class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mt-3 mb-1.5">
                Icon (emoji)
              </label>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="w-10 h-10 text-xl flex items-center justify-center rounded-lg border border-secondary-300 dark:border-secondary-600 bg-white dark:bg-secondary-700 hover:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  :title="form.icon || 'Choose emoji'"
                  @click="showEmojiPicker = !showEmojiPicker"
                >{{ form.icon || '➕' }}</button>
                <input
                  v-model="form.icon"
                  type="text"
                  class="input-field flex-1"
                  placeholder="or type one…"
                  maxlength="4"
                  @focus="showEmojiPicker = false"
                />
                <button
                  v-if="form.icon"
                  type="button"
                  class="text-secondary-400 hover:text-secondary-600 dark:hover:text-secondary-200 text-xs"
                  title="Clear icon"
                  @click="form.icon = ''"
                >✕</button>
              </div>
              <!-- Emoji grid picker -->
              <div v-if="showEmojiPicker" class="mt-2 p-2 rounded-lg border border-secondary-200 dark:border-secondary-600 bg-white dark:bg-secondary-800 grid grid-cols-8 gap-1">
                <button
                  v-for="e in emojiChoices"
                  :key="e"
                  type="button"
                  class="w-8 h-8 text-lg flex items-center justify-center rounded hover:bg-secondary-100 dark:hover:bg-secondary-700 transition-colors"
                  :class="form.icon === e ? 'bg-primary-100 dark:bg-primary-900/30 ring-1 ring-primary-400' : ''"
                  @click="form.icon = e; showEmojiPicker = false"
                >{{ e }}</button>
              </div>

              <label class="block text-sm font-medium text-secondary-700 dark:text-secondary-300 mt-3 mb-1.5">
                Color
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="c in colorChoices"
                  :key="c"
                  type="button"
                  class="w-7 h-7 rounded-full border-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  :style="{ backgroundColor: c, borderColor: form.color === c ? '#111827' : 'transparent' }"
                  :aria-label="`Use color ${c}`"
                  @click="form.color = c"
                ></button>
                <button
                  type="button"
                  class="w-7 h-7 rounded-full border border-secondary-300 dark:border-secondary-600 text-xs text-secondary-500 focus:outline-none"
                  :aria-label="'Clear color'"
                  @click="form.color = null"
                >
                  ✕
                </button>
              </div>

              <p v-if="dialogError" class="mt-3 text-sm text-red-600 dark:text-red-400">
                {{ dialogError }}
              </p>

              <div class="flex justify-between gap-2 mt-5">
                <button
                  v-if="editing"
                  type="button"
                  class="text-sm text-red-600 dark:text-red-400 hover:underline"
                  @click="confirmDelete"
                >
                  Delete folder
                </button>
                <span v-else></span>
                <div class="flex gap-2">
                  <button type="button" class="btn-secondary" @click="closeDialog">Cancel</button>
                  <button type="submit" class="btn-primary" :disabled="saving">
                    {{ saving ? 'Saving...' : editing ? 'Save' : 'Create' }}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </Teleport>
  </aside>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { Folder, FolderStats } from '~/types'

const props = defineProps<{
  modelValue: string | null
  folders: Folder[]
  stats: FolderStats[]
  totalCount: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
  create: [data: { name: string; color: string | null; icon: string | null }]
  update: [id: string, data: { name: string; color: string | null; icon: string | null }]
  delete: [id: string]
}>()

const activeClasses = 'bg-primary-100 text-primary-800 dark:bg-primary-900/30 dark:text-primary-300'
const inactiveClasses = 'text-secondary-700 dark:text-secondary-300 hover:bg-secondary-100 dark:hover:bg-secondary-700/60'

const colorChoices = ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#0EA5E9']

const dialogOpen = ref(false)
const editing = ref<Folder | null>(null)
const saving = ref(false)
const dialogError = ref<string | null>(null)
const showEmojiPicker = ref(false)

const emojiChoices = [
  '📁','📂','📚','📖','📝','📋','📌','📍',
  '🏠','🏢','💼','🎯','✅','🔔','⭐','❤️',
  '🛒','🍽️','🏋️','🎵','🎮','💻','📱','🚗',
  '✈️','🌍','💰','🎁','🔑','⚙️','🩺','📅',
  '🌱','🌿','🔬','🎓','💡','🔧','🏆','🎨',
]
const form = reactive({
  name: '',
  icon: '' as string | null,
  color: null as string | null,
})

const unassignedCount = computed(
  () => props.stats.find((s) => s.id === 'none')?.total ?? 0,
)

function countFor(id: string): number {
  return props.stats.find((s) => s.id === id)?.total ?? 0
}

function select(value: string | null) {
  emit('update:modelValue', value)
}

function openCreate() {
  editing.value = null
  form.name = ''
  form.icon = ''
  form.color = colorChoices[0]
  dialogError.value = null
  dialogOpen.value = true
}

function openEdit(folder: Folder) {
  editing.value = folder
  form.name = folder.name
  form.icon = folder.icon ?? ''
  form.color = folder.color ?? null
  dialogError.value = null
  dialogOpen.value = true
}

function closeDialog() {
  dialogOpen.value = false
  editing.value = null
  showEmojiPicker.value = false
}

async function save() {
  const name = form.name.trim()
  if (!name) {
    dialogError.value = 'Name is required'
    return
  }
  saving.value = true
  dialogError.value = null
  const payload = {
    name,
    icon: form.icon ? form.icon.trim() : null,
    color: form.color,
  }
  try {
    if (editing.value) {
      emit('update', editing.value.id, payload)
    } else {
      emit('create', payload)
    }
    closeDialog()
  } finally {
    saving.value = false
  }
}

function confirmDelete() {
  if (!editing.value) return
  if (window.confirm(`Delete folder "${editing.value.name}"? Todos inside will be unassigned, not deleted.`)) {
    emit('delete', editing.value.id)
    closeDialog()
  }
}
</script>
