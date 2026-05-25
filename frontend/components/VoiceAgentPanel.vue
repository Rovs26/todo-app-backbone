<template>
  <Teleport to="body">
    <Transition name="slide-up">
      <div
        v-if="visible"
        class="fixed bottom-4 right-4 z-40 w-[min(420px,calc(100vw-2rem))] bg-white dark:bg-secondary-800 rounded-lg shadow-2xl border border-secondary-200 dark:border-secondary-700 overflow-hidden"
        role="dialog"
        aria-labelledby="voice-panel-title"
      >
        <header class="flex items-center justify-between px-4 py-3 border-b border-secondary-200 dark:border-secondary-700 bg-secondary-50 dark:bg-secondary-900/50">
          <h2 id="voice-panel-title" class="text-sm font-semibold text-secondary-900 dark:text-white flex items-center gap-2">
            <svg class="w-4 h-4 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-14 0m7 7v4m-4 0h8M12 1a3 3 0 00-3 3v7a3 3 0 006 0V4a3 3 0 00-3-3z" /></svg>
            <span>{{ headerTitle }}</span>
          </h2>
          <button
            type="button"
            class="text-secondary-400 hover:text-secondary-700 dark:hover:text-white"
            aria-label="Close voice panel"
            @click="onCancel"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </header>

        <div class="p-4 max-h-[60vh] overflow-y-auto space-y-3 text-sm">
          <!-- Status / progress -->
          <p v-if="phase === 'recording'" class="flex items-center gap-2 text-red-600 dark:text-red-400">
            <span class="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            Recording… press the mic again or click Stop.
          </p>
          <p v-else-if="phase === 'transcribing'" class="text-secondary-600 dark:text-secondary-400">
            Transcribing audio…
          </p>
          <p v-else-if="phase === 'planning'" class="text-secondary-600 dark:text-secondary-400">
            Planning actions…
          </p>
          <p v-else-if="phase === 'applying'" class="text-secondary-600 dark:text-secondary-400">
            Applying actions…
          </p>

          <!-- Error -->
          <p
            v-if="phase === 'error' && errorMessage"
            class="px-3 py-2 rounded bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800"
          >
            {{ errorMessage }}
          </p>

          <!-- Transcript -->
          <div v-if="plan && (phase === 'reviewing' || phase === 'applying' || phase === 'done')">
            <div class="text-xs uppercase tracking-wide text-secondary-500 dark:text-secondary-400 mb-1">
              You said
            </div>
            <div v-if="!editingTranscript" class="flex items-start gap-2">
              <p class="flex-1 italic text-secondary-700 dark:text-secondary-200">"{{ plan.transcript }}"</p>
              <button
                v-if="phase === 'reviewing'"
                type="button"
                class="text-xs text-primary-600 dark:text-primary-400 hover:underline flex-shrink-0"
                @click="startEditTranscript"
              >
                Edit
              </button>
            </div>
            <div v-else class="space-y-2">
              <textarea
                v-model="transcriptDraft"
                rows="2"
                class="input-field text-sm w-full"
                aria-label="Edit transcript"
              />
              <div class="flex justify-end gap-2">
                <button type="button" class="btn-secondary text-xs" @click="editingTranscript = false">
                  Cancel
                </button>
                <button
                  type="button"
                  class="btn-primary text-xs"
                  :disabled="!transcriptDraft.trim()"
                  @click="submitEditTranscript"
                >
                  Re-plan
                </button>
              </div>
            </div>
          </div>

          <!-- Assistant reply -->
          <p
            v-if="plan?.reply && phase === 'reviewing'"
            class="text-secondary-600 dark:text-secondary-300"
          >
            {{ plan.reply }}
          </p>

          <!-- Action checklist -->
          <div v-if="plan && plan.actions.length > 0 && (phase === 'reviewing' || phase === 'applying')">
            <div class="text-xs uppercase tracking-wide text-secondary-500 dark:text-secondary-400 mb-1">
              Proposed actions
            </div>
            <ul class="space-y-1.5">
              <li
                v-for="(action, idx) in plan.actions"
                :key="idx"
                class="flex items-start gap-2 px-2 py-1.5 rounded border border-secondary-200 dark:border-secondary-700"
              >
                <input
                  :id="`voice-action-${idx}`"
                  v-model="action._selected"
                  type="checkbox"
                  class="mt-0.5"
                  :disabled="phase === 'applying'"
                />
                <label :for="`voice-action-${idx}`" class="flex-1 cursor-pointer text-secondary-800 dark:text-secondary-100">
                  {{ describeAction(action) }}
                </label>
              </li>
            </ul>
          </div>

          <p
            v-else-if="plan && plan.actions.length === 0 && phase === 'reviewing'"
            class="text-secondary-500 dark:text-secondary-400 italic"
          >
            No actions detected. Try rephrasing or edit the transcript.
          </p>

          <!-- Apply outcomes -->
          <div v-if="phase === 'done' && applyOutcomes" class="space-y-1.5">
            <div class="text-xs uppercase tracking-wide text-secondary-500 dark:text-secondary-400 mb-1">
              Result
            </div>
            <ul class="space-y-1">
              <li
                v-for="item in applyOutcomes.applied"
                :key="`ok-${item.index}`"
                class="flex items-start gap-2 text-green-700 dark:text-green-400"
              >
                <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                <span>{{ formatOutcomeName(item.name) }}</span>
              </li>
              <li
                v-if="applyOutcomes.failed"
                class="flex items-start gap-2 text-red-700 dark:text-red-400"
              >
                <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                <span>Failed at step {{ applyOutcomes.failed.index + 1 }}: {{ applyOutcomes.failed.error_message }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- Footer actions -->
        <footer class="flex items-center justify-end gap-2 px-4 py-3 border-t border-secondary-200 dark:border-secondary-700 bg-secondary-50 dark:bg-secondary-900/50">
          <template v-if="phase === 'reviewing'">
            <button type="button" class="btn-secondary text-sm" @click="onCancel">Cancel</button>
            <button
              type="button"
              class="btn-primary text-sm"
              :disabled="selectedCount === 0"
              @click="onApply"
            >
              Apply{{ selectedCount > 0 ? ` (${selectedCount})` : '' }}
            </button>
          </template>
          <template v-else-if="phase === 'recording'">
            <button type="button" class="btn-secondary text-sm" @click="onCancel">Cancel</button>
            <button type="button" class="btn-primary text-sm" @click="emit('stop')">Stop</button>
          </template>
          <template v-else-if="phase === 'done' || phase === 'error'">
            <button type="button" class="btn-primary text-sm" @click="onCancel">Close</button>
          </template>
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { VoiceAction } from '~/utils/api'
import type { VoiceAgentPhase } from '~/composables/useVoiceAgent'
import type { Folder } from '~/types'

interface PlanState {
  transcript: string
  reply: string
  actions: (VoiceAction & { _selected: boolean })[]
}

interface ApplyOutcomes {
  applied: { index: number; name: string }[]
  failed: { index: number; error_message: string } | null
}

const props = defineProps<{
  phase: VoiceAgentPhase
  plan: PlanState | null
  applyOutcomes: ApplyOutcomes | null
  errorMessage: string | null
  folders: Folder[]
}>()

const emit = defineEmits<{
  (e: 'stop'): void
  (e: 'cancel'): void
  (e: 'apply'): void
  (e: 'edit-transcript', text: string): void
}>()

const editingTranscript = ref(false)
const transcriptDraft = ref('')

const visible = computed(() =>
  ['recording', 'transcribing', 'planning', 'reviewing', 'applying', 'done', 'error'].includes(
    props.phase,
  ),
)

const headerTitle = computed(() => {
  if (props.phase === 'recording') return 'Listening…'
  if (props.phase === 'transcribing') return 'Transcribing…'
  if (props.phase === 'planning') return 'Planning…'
  if (props.phase === 'reviewing') return 'Confirm actions'
  if (props.phase === 'applying') return 'Applying…'
  if (props.phase === 'done') return 'Done'
  if (props.phase === 'error') return 'Voice agent'
  return 'Voice agent'
})

const selectedCount = computed(
  () => props.plan?.actions.filter((a) => a._selected).length ?? 0,
)

const folderById = computed(() => {
  const m = new Map<string, string>()
  for (const f of props.folders) m.set(f.id, f.name)
  return m
})

function describeAction(action: VoiceAction & { _selected: boolean }): string {
  const args = action.arguments || {}
  switch (action.name) {
    case 'create_folder':
      return `Create folder "${args.name || '?'}"`
    case 'create_todo': {
      const folderName =
        (action.resolved_folder_id && folderById.value.get(action.resolved_folder_id)) ||
        args.folder_name ||
        null
      const where = folderName ? ` in "${folderName}"` : ''
      const pri = args.priority ? ` [${args.priority}]` : ''
      const due = args.due_date ? ` (due ${args.due_date})` : ''
      return `Create todo "${args.title || '?'}"${where}${pri}${due}`
    }
    case 'add_comment': {
      const target = args.todo_title || action.resolved_todo_id || '?'
      const body = (args.body || '').slice(0, 60)
      return `Comment on "${target}": "${body}"`
    }
    case 'mark_done': {
      const target = args.todo_title || action.resolved_todo_id || '?'
      return `Mark "${target}" as done`
    }
    case 'set_priority': {
      const target = args.todo_title || action.resolved_todo_id || '?'
      return `Set "${target}" priority to ${args.priority || '?'}`
    }
    default:
      return action.name
  }
}

function formatOutcomeName(name: string): string {
  switch (name) {
    case 'create_folder':
      return 'Folder created'
    case 'create_todo':
      return 'Todo created'
    case 'add_comment':
      return 'Comment added'
    case 'mark_done':
      return 'Marked as done'
    case 'set_priority':
      return 'Priority updated'
    default:
      return name
  }
}

function startEditTranscript() {
  transcriptDraft.value = props.plan?.transcript ?? ''
  editingTranscript.value = true
}

function submitEditTranscript() {
  const text = transcriptDraft.value.trim()
  if (!text) return
  editingTranscript.value = false
  emit('edit-transcript', text)
}

function onCancel() {
  editingTranscript.value = false
  emit('cancel')
}

function onApply() {
  emit('apply')
}

// Reset edit-mode if we leave reviewing phase.
watch(
  () => props.phase,
  (p) => {
    if (p !== 'reviewing') editingTranscript.value = false
  },
)
</script>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(20px);
  opacity: 0;
}
</style>
