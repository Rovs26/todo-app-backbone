<template>
  <form class="mb-4" @submit.prevent="onSubmit">
    <label for="quick-add-input" class="sr-only">Quick add a todo</label>
    <div class="relative">
      <span
        class="absolute inset-y-0 left-0 flex items-center pl-3 text-secondary-400"
        aria-hidden="true"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </span>
      <input
        id="quick-add-input"
        v-model="text"
        type="text"
        class="input-field pl-9 pr-10"
        placeholder="Type a task… (e.g. 'pay rent next Friday !high #bills')"
        :disabled="loading"
        maxlength="500"
        @keydown.enter.prevent="onSubmit"
      />
      <span
        v-if="loading"
        class="absolute inset-y-0 right-0 flex items-center pr-3"
        aria-hidden="true"
      >
        <svg class="animate-spin h-4 w-4 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </span>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { aiApi, type ParsedTodo } from '~/utils/api'
import { useToast } from '~/composables/useToast'

const emit = defineEmits<{
  parsed: [data: ParsedTodo, source: 'openai' | 'local']
}>()

const { error: toastError } = useToast()
const text = ref('')
const loading = ref(false)

async function onSubmit() {
  const trimmed = text.value.trim()
  if (!trimmed || loading.value) return
  loading.value = true
  try {
    const result = await aiApi.parseTodo(trimmed)
    emit('parsed', result.data, result.source)
    text.value = ''
  } catch (err: any) {
    const status = err?.response?.status || err?.statusCode
    if (status === 422) {
      toastError('Input is too long (max 500 characters)')
    } else if (status === 503) {
      toastError('AI parser is temporarily unavailable. Try again.')
    } else {
      toastError('Could not parse that. Try again or open the form manually.')
    }
  } finally {
    loading.value = false
  }
}
</script>
