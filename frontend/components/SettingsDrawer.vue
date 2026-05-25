<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150"
      leave-active-class="transition-opacity duration-100"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 bg-black/40 z-40"
        @click="close"
      />
    </Transition>

    <Transition
      enter-active-class="transition-transform duration-200 ease-out"
      leave-active-class="transition-transform duration-150 ease-in"
      enter-from-class="translate-x-full"
      leave-to-class="translate-x-full"
    >
      <aside
        v-if="modelValue"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-drawer-title"
        class="fixed top-0 right-0 z-50 h-full w-full sm:w-96 max-w-full bg-white dark:bg-secondary-800 shadow-2xl border-l border-secondary-200 dark:border-secondary-700 flex flex-col"
      >
        <header class="flex items-center justify-between px-4 py-3 border-b border-secondary-200 dark:border-secondary-700">
          <h2 id="settings-drawer-title" class="text-base font-semibold text-secondary-900 dark:text-white">
            Settings
          </h2>
          <button
            type="button"
            class="p-1.5 rounded-md text-secondary-500 hover:text-secondary-900 dark:hover:text-white hover:bg-secondary-100 dark:hover:bg-secondary-700"
            aria-label="Close settings"
            @click="close"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div class="flex-1 overflow-y-auto px-4 py-5 space-y-6">
          <!-- Account section -->
          <section>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-secondary-500 dark:text-secondary-400 mb-2">
              Account
            </h3>
            <dl class="text-sm space-y-1.5">
              <div class="flex items-center justify-between">
                <dt class="text-secondary-600 dark:text-secondary-400">Username</dt>
                <dd class="text-secondary-900 dark:text-white font-medium truncate ml-2">
                  {{ effectiveUser?.username ?? '—' }}
                </dd>
              </div>
              <div class="flex items-center justify-between">
                <dt class="text-secondary-600 dark:text-secondary-400">Email</dt>
                <dd class="text-secondary-900 dark:text-white font-medium truncate ml-2">
                  {{ effectiveUser?.email ?? '—' }}
                </dd>
              </div>
            </dl>
          </section>

          <!-- Notifications section -->
          <section>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-secondary-500 dark:text-secondary-400 mb-2">
              Notifications
            </h3>
            <div class="rounded-md border border-secondary-200 dark:border-secondary-700 p-3">
              <label class="flex items-start justify-between gap-3 cursor-pointer">
                <span class="flex-1 min-w-0">
                  <span class="block text-sm font-medium text-secondary-900 dark:text-white">
                    Email reminders
                  </span>
                  <span class="block text-xs text-secondary-500 dark:text-secondary-400 mt-0.5">
                    Send a one-time email when a todo's reminder time arrives.
                  </span>
                </span>
                <button
                  type="button"
                  role="switch"
                  :aria-checked="emailRemindersEnabled"
                  :disabled="saving"
                  class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50"
                  :class="emailRemindersEnabled ? 'bg-primary-600' : 'bg-secondary-300 dark:bg-secondary-600'"
                  @click="toggleEmailReminders"
                >
                  <span
                    class="inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200"
                    :class="emailRemindersEnabled ? 'translate-x-5' : 'translate-x-0'"
                  />
                </button>
              </label>
              <p v-if="saving" class="mt-2 text-xs text-secondary-500 dark:text-secondary-400">
                Saving…
              </p>
            </div>
          </section>
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuth } from '~/composables/useAuth'
import { useToast } from '~/composables/useToast'
import type { User } from '~/types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const { user, updatePreferences } = useAuth()
const { success: toastSuccess, error: toastError } = useToast()

// Mirror auth state into a local user ref if the composable's `user` is empty
// (composable instance is per-call; `auth-user` shared state is updated by updatePreferences)
const sharedUser = useState<User | null>('auth-user')
const effectiveUser = computed<User | null>(() => user.value ?? sharedUser.value)

const emailRemindersEnabled = computed(() => effectiveUser.value?.email_reminders_enabled ?? true)
const saving = ref(false)

async function toggleEmailReminders() {
  if (saving.value) return
  const next = !emailRemindersEnabled.value
  saving.value = true
  try {
    const ok = await updatePreferences({ email_reminders_enabled: next })
    if (ok) {
      toastSuccess(next ? 'Email reminders turned on' : 'Email reminders turned off')
    } else {
      toastError('Could not update preference')
    }
  } catch {
    toastError('Could not update preference')
  } finally {
    saving.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}

// Close on Escape
watch(
  () => props.modelValue,
  (open) => {
    if (typeof window === 'undefined') return
    if (open) {
      window.addEventListener('keydown', onKeydown)
    } else {
      window.removeEventListener('keydown', onKeydown)
    }
  },
)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

</script>
