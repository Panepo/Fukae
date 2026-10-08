<script setup>
import { ref } from 'vue'
import { AuthenticationError } from './api'

const props = defineProps({
  api: { type: Object, required: true },
})

const supportedTypes = '.pdf,.docx,.doc,.odt,.rtf,.html,.htm,.xlsx,.xls,.csv,.pptx,.ppt,.json,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.md,.txt'
const fileInput = ref(null)
const entries = ref([])
const error = ref('')
const uploading = ref(false)

async function pollTask(entry) {
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    const response = await props.api.request(`/status/${entry.taskId}`)
    if (!response.ok) throw new Error(`Status request failed (${response.status}).`)
    const data = await response.json()
    entry.progress = data.progress ?? entry.progress
    entry.status = data.status

    if (data.status === 'completed') {
      entry.result = data.result
      return
    }
    if (data.status === 'failed') {
      entry.error = data.error || 'Indexing failed.'
      return
    }
  }
}

async function uploadFiles() {
  const files = Array.from(fileInput.value?.files || [])
  if (!files.length) {
    error.value = 'Choose at least one file to upload.'
    return
  }

  uploading.value = true
  error.value = ''
  for (const file of files) {
    const entry = { name: file.name, progress: 0, status: 'uploading', taskId: '', result: null, error: '' }
    entries.value.push(entry)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await props.api.request('/upload', { method: 'POST', body: formData })
      if (!response.ok) throw new Error(`Upload failed (${response.status}).`)
      const data = await response.json()
      entry.taskId = data.task_id
      entry.status = data.status
      await pollTask(entry)
    } catch (requestError) {
      if (requestError instanceof AuthenticationError) return
      entry.status = 'failed'
      entry.error = requestError.message
    }
  }
  uploading.value = false
}

async function downloadChunks(docStem) {
  try {
    const response = await props.api.request(`/download/chunks/${encodeURIComponent(docStem)}_chunks.json`)
    if (!response.ok) throw new Error(`Download failed (${response.status}).`)
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = `${docStem}_chunks.json`
    link.click()
    URL.revokeObjectURL(url)
  } catch (requestError) {
    if (!(requestError instanceof AuthenticationError)) error.value = requestError.message
  }
}
</script>

<template>
  <section aria-labelledby="indexing-heading">
    <div class="section-heading">
      <div>
        <h2 id="indexing-heading">Index documents</h2>
        <p>Select supported documents to create embedded chunks.</p>
      </div>
    </div>
    <form class="upload-form" @submit.prevent="uploadFiles">
      <label for="documents">Documents</label>
      <input id="documents" ref="fileInput" type="file" multiple :accept="supportedTypes" :disabled="uploading" />
      <p v-if="error" class="message error" role="alert">{{ error }}</p>
      <button class="filled-button" type="submit" :disabled="uploading">{{ uploading ? 'Processing...' : 'Upload and process' }}</button>
    </form>

    <div v-if="entries.length" class="job-list" aria-live="polite">
      <article v-for="entry in entries" :key="`${entry.name}-${entry.taskId}`" class="job-row">
        <div class="job-summary">
          <strong>{{ entry.name }}</strong>
          <span class="status-chip">{{ entry.status }}</span>
        </div>
        <div class="progress-track" :aria-label="`${entry.name} progress`">
          <div class="progress-fill" :style="{ width: `${entry.progress}%` }"></div>
        </div>
        <p v-if="entry.error" class="message error">{{ entry.error }}</p>
        <div v-if="entry.result" class="job-result">
          <span>{{ entry.result.chunks_count }} chunks created</span>
          <button type="button" class="secondary-button" @click="downloadChunks(entry.result.doc_stem)">Download JSON</button>
        </div>
      </article>
    </div>
  </section>
</template>
