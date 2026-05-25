<template>
  <div class="fixed bottom-6 right-24 z-40">
    <!-- Toggle button -->
    <button
      v-if="!open"
      type="button"
      class="w-12 h-12 rounded-full bg-violet-600 hover:bg-violet-700 text-white shadow-lg flex items-center justify-center transition-all duration-200 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2"
      aria-label="Open AI assistant"
      @click="toggle"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4-.81L3 21l1.81-4A8.36 8.36 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
    </button>

    <!-- Panel -->
    <div
      v-if="open"
      class="w-80 sm:w-96 max-w-[calc(100vw-2rem)] h-[28rem] bg-white dark:bg-secondary-800 rounded-xl shadow-2xl border border-secondary-200 dark:border-secondary-700 flex flex-col overflow-hidden"
      role="dialog"
      aria-label="AI assistant"
    >
      <header class="flex items-center justify-between px-4 py-3 border-b border-secondary-200 dark:border-secondary-700 bg-violet-50 dark:bg-violet-900/20">
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center justify-center w-7 h-7 rounded-full bg-violet-600 text-white">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
          </span>
          <div>
            <p class="text-sm font-semibold text-secondary-900 dark:text-white leading-none">Assistant</p>
            <p class="text-[11px] text-secondary-500 dark:text-secondary-400 mt-0.5">
              Knows your todos
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            v-if="messages.length"
            type="button"
            class="text-xs text-secondary-500 hover:text-red-600 dark:hover:text-red-400 focus:outline-none"
            aria-label="Clear conversation"
            @click="reset"
          >
            Clear
          </button>
          <button
            type="button"
            class="text-secondary-500 hover:text-secondary-900 dark:hover:text-white focus:outline-none"
            aria-label="Close"
            @click="open = false"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </header>

      <div ref="scrollRef" class="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-secondary-50/40 dark:bg-secondary-900/40">
        <p
          v-if="messages.length === 0 && !pending"
          class="text-sm text-secondary-500 dark:text-secondary-400 text-center px-2 py-6"
        >
          Ask anything about your todos. Try:
          <span class="block mt-2 space-y-1">
            <button class="block w-full text-left text-xs text-violet-700 dark:text-violet-300 hover:underline" @click="ask('What should I focus on today?')">
              "What should I focus on today?"
            </button>
            <button class="block w-full text-left text-xs text-violet-700 dark:text-violet-300 hover:underline" @click="ask('Anything overdue?')">
              "Anything overdue?"
            </button>
            <button class="block w-full text-left text-xs text-violet-700 dark:text-violet-300 hover:underline" @click="ask('Summarize my school project tasks.')">
              "Summarize my school project tasks."
            </button>
          </span>
        </p>

        <div v-for="(m, i) in messages" :key="i" class="flex" :class="m.role === 'user' ? 'justify-end' : 'justify-start'">
          <div
            class="max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap break-words"
            :class="m.role === 'user'
              ? 'bg-primary-600 text-white'
              : 'bg-white dark:bg-secondary-700 text-secondary-900 dark:text-secondary-100 border border-secondary-200 dark:border-secondary-600'"
          >
            {{ m.content }}
          </div>
        </div>

        <div v-if="pending" class="flex justify-start">
          <div class="rounded-lg px-3 py-2 bg-white dark:bg-secondary-700 border border-secondary-200 dark:border-secondary-600 text-sm text-secondary-500">
            <span class="inline-flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-secondary-400 animate-bounce [animation-delay:-0.2s]"></span>
              <span class="w-1.5 h-1.5 rounded-full bg-secondary-400 animate-bounce [animation-delay:-0.1s]"></span>
              <span class="w-1.5 h-1.5 rounded-full bg-secondary-400 animate-bounce"></span>
            </span>
          </div>
        </div>

        <p v-if="error" class="text-xs text-red-600 dark:text-red-400 text-center">{{ error }}</p>
      </div>

      <form class="border-t border-secondary-200 dark:border-secondary-700 p-2 flex items-center gap-2" @submit.prevent="send">
        <input
          v-model="draft"
          type="text"
          class="input-field flex-1 text-sm"
          placeholder="Ask about your todos…"
          :disabled="pending"
          aria-label="Chat with assistant"
        />
        <button
          type="submit"
          class="btn-primary text-sm px-3"
          :disabled="pending || !draft.trim()"
        >
          Send
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { aiApi } from '~/utils/api'
import { useWeather } from '~/composables/useWeather'

const { weather, load: loadWeather } = useWeather()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const open = ref(false)
const draft = ref('')
const messages = ref<ChatMessage[]>([])
const pending = ref(false)
const error = ref<string | null>(null)
const scrollRef = ref<HTMLDivElement | null>(null)

function toggle() {
  open.value = !open.value
}

function reset() {
  messages.value = []
  error.value = null
}

async function ask(seed: string) {
  draft.value = seed
  await send()
}

async function send() {
  const text = draft.value.trim()
  if (!text || pending.value) return
  draft.value = ''
  error.value = null

  const history = [...messages.value]
  messages.value.push({ role: 'user', content: text })
  pending.value = true
  await scrollToBottom()

  // Best-effort: include weather context so the assistant can answer
  // "what's the weather tomorrow?" using real Open-Meteo data we already
  // fetch for the quick-add hint. Silently skipped if geolocation is denied.
  if (!weather.value) {
    try { await loadWeather() } catch { /* ignore */ }
  }

  try {
    const response = await aiApi.chat(text, history, weather.value)
    messages.value.push({ role: 'assistant', content: response.reply })
  } catch (err: any) {
    error.value = err?.message ?? 'Could not reach the assistant'
    messages.value.pop()
  } finally {
    pending.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

watch(open, async (val) => {
  if (val) await scrollToBottom()
})
</script>
