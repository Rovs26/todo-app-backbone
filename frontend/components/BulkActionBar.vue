<template>
  <div
    v-if="selectedCount > 0"
    class="fixed left-1/2 -translate-x-1/2 bottom-24 z-30 bg-white dark:bg-secondary-800 border border-secondary-200 dark:border-secondary-700 rounded-xl shadow-lg px-4 py-3 flex items-center gap-2 max-w-[95vw] flex-wrap"
    role="region"
    aria-label="Bulk actions"
  >
    <span class="text-sm font-medium text-secondary-700 dark:text-secondary-200">
      {{ selectedCount }} selected
    </span>

    <span class="h-5 w-px bg-secondary-200 dark:bg-secondary-700 mx-1" aria-hidden="true" />

    <button
      type="button"
      class="text-xs px-2 py-1 rounded-md bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50 disabled:opacity-50"
      :disabled="busy"
      @click="emitAction('mark_done')"
    >
      Mark done
    </button>
    <button
      type="button"
      class="text-xs px-2 py-1 rounded-md bg-secondary-100 text-secondary-700 dark:bg-secondary-700 dark:text-secondary-200 hover:bg-secondary-200 dark:hover:bg-secondary-600 disabled:opacity-50"
      :disabled="busy"
      @click="emitAction('mark_pending')"
    >
      Mark pending
    </button>
    <button
      type="button"
      class="text-xs px-2 py-1 rounded-md bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 disabled:opacity-50"
      :disabled="busy"
      @click="emitAction('mark_in_progress')"
    >
      In progress
    </button>

    <span class="h-5 w-px bg-secondary-200 dark:bg-secondary-700 mx-1" aria-hidden="true" />

    <select
      class="text-xs px-2 py-1 rounded-md bg-white dark:bg-secondary-700 border border-secondary-200 dark:border-secondary-600 text-secondary-700 dark:text-secondary-200 disabled:opacity-50"
      :disabled="busy"
      :value="''"
      aria-label="Set priority"
      @change="onPriorityChange($event)"
    >
      <option value="" disabled>Set priority…</option>
      <option value="low">Low</option>
      <option value="medium">Medium</option>
      <option value="high">High</option>
    </select>

    <select
      class="text-xs px-2 py-1 rounded-md bg-white dark:bg-secondary-700 border border-secondary-200 dark:border-secondary-600 text-secondary-700 dark:text-secondary-200 disabled:opacity-50"
      :disabled="busy"
      :value="''"
      aria-label="Move to folder"
      @change="onFolderChange($event)"
    >
      <option value="" disabled>Move to folder…</option>
      <option value="__none__">(Unassigned)</option>
      <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
    </select>

    <button
      type="button"
      class="text-xs px-2 py-1 rounded-md bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-900/50 disabled:opacity-50"
      :disabled="busy"
      @click="onAddTag"
    >
      + Tag
    </button>
    <button
      type="button"
      class="text-xs px-2 py-1 rounded-md bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-900/50 disabled:opacity-50"
      :disabled="busy"
      @click="onRemoveTag"
    >
      − Tag
    </button>

    <span class="h-5 w-px bg-secondary-200 dark:bg-secondary-700 mx-1" aria-hidden="true" />

    <button
      type="button"
      class="text-xs px-2 py-1 rounded-md bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/50 disabled:opacity-50"
      :disabled="busy"
      @click="emitAction('delete')"
    >
      Delete
    </button>

    <button
      type="button"
      class="text-xs px-2 py-1 rounded-md text-secondary-500 dark:text-secondary-400 hover:text-secondary-700 dark:hover:text-secondary-200 disabled:opacity-50"
      :disabled="busy"
      @click="$emit('clear')"
    >
      Clear
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Folder } from '~/types'

interface Props {
  selectedCount: number
  folders: Folder[]
  busy?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  action: [action: string, payload?: Record<string, unknown>]
  clear: []
}>()

function emitAction(action: string, payload?: Record<string, unknown>) {
  if (action === 'delete') {
    if (!window.confirm(`Delete ${props.selectedCount} todo(s)? This cannot be undone.`)) return
  }
  emit('action', action, payload)
}

function onPriorityChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  if (!v) return
  emit('action', 'set_priority', { priority: v })
  ;(e.target as HTMLSelectElement).value = ''
}

function onFolderChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  if (!v) return
  const folderId = v === '__none__' ? null : v
  emit('action', 'move_to_folder', { folder_id: folderId })
  ;(e.target as HTMLSelectElement).value = ''
}

function onAddTag() {
  const tag = window.prompt('Tag to add (lowercase, no spaces):')?.trim()
  if (!tag) return
  emit('action', 'add_tag', { tag })
}

function onRemoveTag() {
  const tag = window.prompt('Tag to remove:')?.trim()
  if (!tag) return
  emit('action', 'remove_tag', { tag })
}
</script>
