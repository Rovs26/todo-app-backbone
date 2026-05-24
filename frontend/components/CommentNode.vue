<template>
  <div :class="['rounded-md border', tombstone ? 'border-dashed border-secondary-300 dark:border-secondary-700' : 'border-secondary-200 dark:border-secondary-700', 'p-2 bg-white dark:bg-secondary-900']">
    <div class="flex items-center justify-between text-xs text-secondary-500">
      <span>
        <span class="font-medium text-secondary-700 dark:text-secondary-200">{{ comment.author_username || 'user' }}</span>
        <span class="ml-2">{{ formatTime(comment.created_at) }}</span>
        <span v-if="comment.updated_at" class="ml-1 italic">(edited)</span>
      </span>
      <span v-if="!tombstone" class="flex items-center gap-2">
        <button v-if="depth < 5" class="hover:underline" @click="$emit('reply', comment)">reply</button>
        <button class="hover:underline" @click="$emit('edit', comment)">edit</button>
        <button class="text-red-600 hover:underline" @click="$emit('delete', comment)">delete</button>
      </span>
    </div>

    <div v-if="tombstone" class="text-xs italic text-secondary-500 mt-1">[deleted]</div>
    <div v-else class="text-sm text-secondary-800 dark:text-secondary-200 mt-1 whitespace-pre-wrap" v-html="renderedBody"></div>

    <div v-if="!tombstone && comment.attachments.length" class="mt-2 flex flex-wrap gap-2">
      <a v-for="att in comment.attachments" :key="att.id" :href="absUrl(att.url)" target="_blank" rel="noopener">
        <img :src="absUrl(att.url)" class="h-16 w-16 object-cover rounded border border-secondary-200 dark:border-secondary-700" />
      </a>
    </div>

    <ul v-if="replies.length" class="mt-2 ml-3 border-l border-secondary-200 dark:border-secondary-700 pl-3 space-y-2">
      <li v-for="r in replies" :key="r.id">
        <CommentNode
          :comment="r"
          :all="all"
          :depth="depth + 1"
          @reply="(c) => $emit('reply', c)"
          @edit="(c) => $emit('edit', c)"
          @delete="(c) => $emit('delete', c)"
        />
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Comment } from '~/types'

const props = defineProps<{ comment: Comment; all: Comment[]; depth: number }>()
defineEmits<{ reply: [c: Comment]; edit: [c: Comment]; delete: [c: Comment] }>()

const tombstone = computed(() => props.comment.is_tombstone)
const replies = computed(() =>
  props.all
    .filter((c) => c.parent_comment_id === props.comment.id)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
)

const mentionSet = computed(() => new Set(props.comment.mentions.map((m) => m.username.toLowerCase())))

const renderedBody = computed(() => {
  const escaped = escapeHtml(props.comment.body)
  return escaped.replace(/(^|[^A-Za-z0-9_])@([A-Za-z0-9_]{3,30})(?![A-Za-z0-9_])/g, (full, pre, name) => {
    if (mentionSet.value.has(name.toLowerCase())) {
      return `${pre}<span class="text-primary-600 dark:text-primary-400 font-medium">@${name}</span>`
    }
    return full
  })
})

function escapeHtml(s: string) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function absUrl(rel: string) {
  if (rel.startsWith('http')) return rel
  return `http://localhost:8000${rel}`
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}
</script>
