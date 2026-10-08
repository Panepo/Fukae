<script setup>
import { onMounted, ref } from 'vue'
import { AuthenticationError } from './api'
import FileList from './FileList.vue'

const props = defineProps({
  api: { type: Object, required: true },
})

const uploads = ref([])
const chunks = ref([])
const loading = ref(false)
const error = ref('')
const deletingFile = ref('')

function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit ? 1 : 0)} ${units[unit]}`
}

function formatModified(timestamp) {
  return new Date(timestamp * 1000).toLocaleString()
}

async function loadFiles() {
  loading.value = true
  error.value = ''
  try {
    const [uploadsResponse, chunksResponse] = await Promise.all([
      props.api.request('/files/uploads/list'),
      props.api.request('/files/chunks/list'),
    ])
    if (!uploadsResponse.ok || !chunksResponse.ok) throw new Error('Unable to load the file lists.')
    uploads.value = (await uploadsResponse.json()).files.sort((left, right) => left.name.localeCompare(right.name))
    chunks.value = (await chunksResponse.json()).files.sort((left, right) => left.name.localeCompare(right.name))
  } catch (requestError) {
    if (!(requestError instanceof AuthenticationError)) error.value = requestError.message
  } finally {
    loading.value = false
  }
}

async function download(directory, filename) {
  try {
    const response = await props.api.request(`/download/${directory}/${encodeURIComponent(filename)}`)
    if (!response.ok) throw new Error(`Download failed (${response.status}).`)
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (requestError) {
    if (!(requestError instanceof AuthenticationError)) error.value = requestError.message
  }
}

async function deleteFile(directory, filename) {
  if (!window.confirm(`Delete "${filename}"? This cannot be undone.`)) return

  deletingFile.value = `${directory}/${filename}`
  error.value = ''
  try {
    const response = await props.api.request(`/files/${directory}/${encodeURIComponent(filename)}`, { method: 'DELETE' })
    if (!response.ok) throw new Error(`Delete failed (${response.status}).`)
    await loadFiles()
  } catch (requestError) {
    if (!(requestError instanceof AuthenticationError)) error.value = requestError.message
  } finally {
    deletingFile.value = ''
  }
}

onMounted(loadFiles)
</script>

<template>
  <section aria-labelledby="files-heading">
    <div class="section-heading">
      <div>
        <h2 id="files-heading">File management</h2>
        <p>Browse and download uploaded documents and generated chunks.</p>
      </div>
      <button class="secondary-button" type="button" :disabled="loading" @click="loadFiles">Refresh</button>
    </div>
    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-else-if="loading" class="message">Loading files...</p>

    <div v-else class="file-groups">
      <FileList heading="Uploads" directory="uploads" :files="uploads" :format-size="formatSize" :format-modified="formatModified" :deleting-file="deletingFile" @download="download" @delete="deleteFile" />
      <FileList heading="Chunks" directory="chunks" :files="chunks" :format-size="formatSize" :format-modified="formatModified" :deleting-file="deletingFile" @download="download" @delete="deleteFile" />
    </div>
  </section>
</template>
