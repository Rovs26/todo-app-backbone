<template>
  <div class="border-t border-secondary-200 dark:border-secondary-700 pt-4 mt-4">
    <h3 class="text-sm font-semibold text-secondary-800 dark:text-secondary-200 mb-3 flex items-center gap-2">
      <span>💬 Comments</span>
      <span class="text-xs text-secondary-500">({{ visibleCount }})</span>
    </h3>

    <div v-if="loading" class="text-xs text-secondary-500">Loading…</div>

    <ul v-else-if="topLevel.length" class="space-y-3">
      <li v-for="c in topLevel" :key="c.id">
        <CommentNode
          :comment="c"
          :all="comments"
          :depth="1"
          @reply="onReply"
          @edit="onEdit"
          @delete="onDelete"
        />
      </li>
    </ul>
    <div v-else class="text-xs text-secondary-500 mb-3">No comments yet.</div>

    <!-- Composer -->
    <div class="mt-4">
      <div v-if="replyTo" class="text-xs text-secondary-500 mb-1 flex items-center gap-2">
        <span>Replying to {{ replyTo.author_username || 'comment' }}</span>
        <button class="text-red-600 hover:underline" @click="replyTo = null">cancel</button>
      </div>
      <textarea
        v-model="draft"
        rows="2"
        class="w-full text-sm rounded-md border border-secondary-300 dark:border-secondary-700 bg-white dark:bg-secondary-800 p-2"
        placeholder="Add a comment… use @username to mention, drop or pick images"
        @paste="onPaste"
      />
      <div v-if="pending.length" class="mt-1 flex flex-wrap gap-2">
        <div v-for="att in pending" :key="att.id" class="relative">
          <img :src="absUrl(att.url)" class="h-14 w-14 object-cover rounded border border-secondary-200 dark:border-secondary-700" />
          <button class="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full w-4 h-4 leading-4 text-center" @click="removePending(att.id)">×</button>
        </div>
      </div>
      <div class="mt-2 flex items-center gap-2">
        <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple class="hidden" @change="onFiles" />
        <button type="button" class="text-xs text-secondary-600 hover:underline" @click="() => fileInput?.click()">📎 attach</button>
        <button
          type="button"
          class="ml-auto px-3 py-1 text-xs rounded bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
          :disabled="submitting || !draft.trim()"
          @click="submit"
        >
          {{ replyTo ? 'Reply' : 'Comment' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { commentsApi } from '~/utils/api'
import type { Attachment, Comment } from '~/types'
import CommentNode from './CommentNode.vue'

const props = defineProps<{ todoId: string }>()

const comments = ref<Comment[]>([])
const loading = ref(true)
const draft = ref('')
const submitting = ref(false)
const replyTo = ref<Comment | null>(null)
const pending = ref<Attachment[]>([])
const fileInput = ref<HTMLInputElement | null>(null)

const topLevel = computed(() =>
  [...comments.value].filter((c) => !c.parent_comment_id).sort(byDate)
)

const visibleCount = computed(() => comments.value.filter((c) => !c.is_tombstone).length)

function byDate(a: Comment, b: Comment) {
  return a.created_at.localeCompare(b.created_at)
}

function absUrl(rel: string) {
  if (rel.startsWith('http')) return rel
  return `http://localhost:8000${rel}`
}

async function refresh() {
  loading.value = true
  try {
    comments.value = await commentsApi.list(props.todoId)
  } finally {
    loading.value = false
  }
}

async function onFiles(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files) return
  for (const file of Array.from(files)) {
    if (pending.value.length >= 4) break
    try {
      const att = await commentsApi.uploadAttachment(file)
      pending.value.push(att)
    } catch (err) {
      console.error('upload failed', err)
    }
  }
  if (fileInput.value) fileInput.value.value = ''
}

async function onPaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const it of Array.from(items)) {
    if (it.kind === 'file' && it.type.startsWith('image/')) {
      const file = it.getAsFile()
      if (file && pending.value.length < 4) {
        try {
          const att = await commentsApi.uploadAttachment(file)
          pending.value.push(att)
        } catch {}
      }
    }
  }
}

async function removePending(id: string) {
  pending.value = pending.value.filter((a) => a.id !== id)
  try {
    await commentsApi.deleteAttachment(id)
  } catch {}
}

async function submit() {
  if (!draft.value.trim()) return
  submitting.value = true
  try {
    const body = draft.value.trim()
    const created = await commentsApi.create(props.todoId, {
      body,
      parent_comment_id: replyTo.value?.id ?? null,
      attachment_ids: pending.value.map((a) => a.id),
    })
    comments.value.push(created)
    draft.value = ''
    pending.value = []
    replyTo.value = null
  } catch (e) {
    console.error(e)
    alert('Failed to post comment')
  } finally {
    submitting.value = false
  }
}

function onReply(c: Comment) {
  replyTo.value = c
  draft.value = ''
}

async function onEdit(c: Comment) {
  const next = prompt('Edit comment', c.body)
  if (next == null) return
  const trimmed = next.trim()
  if (!trimmed) return
  try {
    const updated = await commentsApi.update(props.todoId, c.id, {
      body: trimmed,
      attachment_ids: c.attachments.map((a) => a.id),
    })
    const i = comments.value.findIndex((x) => x.id === c.id)
    if (i >= 0) comments.value[i] = updated
  } catch {
    alert('Failed to update comment')
  }
}

async function onDelete(c: Comment) {
  if (!confirm('Delete this comment?')) return
  try {
    await commentsApi.delete(props.todoId, c.id)
    await refresh()
  } catch {
    alert('Failed to delete comment')
  }
}

onMounted(refresh)
</script>
