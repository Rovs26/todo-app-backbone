import { computed, ref } from 'vue'
import { aiApi, type VoiceAction } from '~/utils/api'

export type VoiceAgentPhase =
  | 'idle'
  | 'recording'
  | 'transcribing'
  | 'planning'
  | 'reviewing'
  | 'applying'
  | 'done'
  | 'error'

interface PlanResult {
  transcript: string
  reply: string
  actions: (VoiceAction & { _selected: boolean })[]
}

export function useVoiceAgent() {
  const phase = ref<VoiceAgentPhase>('idle')
  const errorMessage = ref<string | null>(null)
  const plan = ref<PlanResult | null>(null)
  const applyOutcomes = ref<{
    applied: { index: number; name: string }[]
    failed: { index: number; error_message: string } | null
  } | null>(null)

  let mediaRecorder: MediaRecorder | null = null
  let mediaStream: MediaStream | null = null
  let chunks: Blob[] = []

  const hasMediaRecorder =
    typeof window !== 'undefined' && typeof window.MediaRecorder !== 'undefined'
  const supported = computed(() => hasMediaRecorder)

  async function start() {
    if (!hasMediaRecorder) {
      errorMessage.value = 'Voice recording is not supported in this browser.'
      phase.value = 'error'
      return
    }
    errorMessage.value = null
    applyOutcomes.value = null
    plan.value = null
    chunks = []
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (err: any) {
      errorMessage.value = err?.message ?? 'Microphone access denied.'
      phase.value = 'error'
      return
    }
    mediaRecorder = new MediaRecorder(mediaStream)
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data)
    }
    mediaRecorder.onstop = onStop
    mediaRecorder.start()
    phase.value = 'recording'
  }

  function stop() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop()
    }
  }

  function cancel() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.onstop = null
      mediaRecorder.stop()
    }
    cleanupStream()
    phase.value = 'idle'
    chunks = []
    plan.value = null
    applyOutcomes.value = null
    errorMessage.value = null
  }

  function cleanupStream() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop())
      mediaStream = null
    }
    mediaRecorder = null
  }

  async function onStop() {
    phase.value = 'transcribing'
    const blob = new Blob(chunks, { type: 'audio/webm' })
    cleanupStream()
    chunks = []

    let transcript = ''
    try {
      const transResult = await aiApi.transcribe(blob)
      transcript = (transResult?.text || '').trim()
    } catch (err: any) {
      errorMessage.value = 'Transcription failed.'
      phase.value = 'error'
      return
    }
    if (!transcript) {
      errorMessage.value = 'I could not hear anything. Try again.'
      phase.value = 'error'
      return
    }
    await runPlan(transcript)
  }

  async function runPlan(transcript: string) {
    phase.value = 'planning'
    try {
      const result = await aiApi.voiceAction(transcript)
      plan.value = {
        transcript,
        reply: result.assistant_reply,
        actions: result.actions.map((a) => ({ ...a, _selected: true })),
      }
      phase.value = 'reviewing'
    } catch (err: any) {
      const status = err?.response?.status || err?.statusCode
      if (status === 503) errorMessage.value = 'Voice agent requires an OpenAI API key.'
      else errorMessage.value = 'The planner failed. Please try again.'
      phase.value = 'error'
    }
  }

  async function editTranscript(newText: string) {
    const trimmed = newText.trim()
    if (!trimmed) return
    await runPlan(trimmed)
  }

  async function applySelected(): Promise<boolean> {
    if (!plan.value) return false
    const chosen = plan.value.actions.filter((a) => a._selected)
    if (chosen.length === 0) return false
    phase.value = 'applying'
    try {
      const result = await aiApi.applyVoiceActions(
        chosen.map(({ _selected, ...rest }) => rest as VoiceAction),
      )
      applyOutcomes.value = {
        applied: result.applied.map((a) => ({ index: a.index, name: a.name })),
        failed: result.failed
          ? { index: result.failed.index, error_message: result.failed.error_message }
          : null,
      }
      phase.value = 'done'
      return result.failed === null
    } catch (err: any) {
      errorMessage.value = 'Apply failed.'
      phase.value = 'error'
      return false
    }
  }

  function reset() {
    phase.value = 'idle'
    plan.value = null
    applyOutcomes.value = null
    errorMessage.value = null
  }

  return {
    phase,
    supported,
    errorMessage,
    plan,
    applyOutcomes,
    start,
    stop,
    cancel,
    editTranscript,
    applySelected,
    reset,
  }
}
