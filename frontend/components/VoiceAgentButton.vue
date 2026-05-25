<template>
  <button
    type="button"
    class="relative p-2 rounded-md transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary-500"
    :class="buttonClass"
    :disabled="disabled"
    :title="title"
    :aria-label="title"
    :aria-pressed="isRecording"
    @click="onClick"
  >
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-14 0m7 7v4m-4 0h8M12 1a3 3 0 00-3 3v7a3 3 0 006 0V4a3 3 0 00-3-3z" />
    </svg>
    <span
      v-if="isRecording"
      class="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500 animate-pulse"
      aria-hidden="true"
    />
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { VoiceAgentPhase } from '~/composables/useVoiceAgent'

const props = defineProps<{
  phase: VoiceAgentPhase
  supported: boolean
  aiEnabled: boolean
}>()

const emit = defineEmits<{
  (e: 'start'): void
  (e: 'stop'): void
}>()

const isRecording = computed(() => props.phase === 'recording')
const isBusy = computed(() =>
  ['transcribing', 'planning', 'applying'].includes(props.phase),
)
const disabled = computed(
  () => !props.supported || !props.aiEnabled || isBusy.value,
)

const title = computed(() => {
  if (!props.supported) return 'Voice recording is not supported in this browser'
  if (!props.aiEnabled) return 'Voice agent requires an OpenAI API key'
  if (isRecording.value) return 'Stop recording'
  if (isBusy.value) return 'Working…'
  return 'Voice command'
})

const buttonClass = computed(() => {
  if (disabled.value) {
    return 'text-secondary-400 cursor-not-allowed'
  }
  if (isRecording.value) {
    return 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50'
  }
  return 'text-secondary-500 dark:text-secondary-400 hover:text-secondary-900 dark:hover:text-white hover:bg-secondary-100 dark:hover:bg-secondary-700'
})

function onClick() {
  if (disabled.value) return
  if (isRecording.value) emit('stop')
  else emit('start')
}
</script>
