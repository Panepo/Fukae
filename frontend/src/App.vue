<script setup>
import { onMounted, ref } from 'vue'
import { clearStoredKey, createApiClient, loadStoredKey, storeKey, verifyKey } from './api'
import FilesView from './FilesView.vue'
import IndexingView from './IndexingView.vue'

const key = ref('')
const activeTab = ref('indexing')
const authenticated = ref(false)
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const api = ref(null)

async function authenticate(candidate) {
  if (!candidate) {
    error.value = 'Enter a bearer key.'
    return
  }

  submitting.value = true
  error.value = ''
  try {
    if (!await verifyKey(candidate)) {
      clearStoredKey()
      error.value = 'The bearer key was not accepted.'
      return
    }
    storeKey(candidate)
    api.value = createApiClient(candidate, signOut)
    authenticated.value = true
    key.value = ''
  } catch {
    clearStoredKey()
    error.value = 'Unable to verify the bearer key. Check the server and try again.'
  } finally {
    submitting.value = false
  }
}

async function submitKey() {
  await authenticate(key.value.trim())
}

function signOut() {
  clearStoredKey()
  authenticated.value = false
  activeTab.value = 'indexing'
}

onMounted(async () => {
  const storedKey = loadStoredKey()
  if (storedKey) {
    await authenticate(storedKey)
  }
  loading.value = false
})
</script>

<template>
  <main class="app-shell">
    <section v-if="loading" class="credential-panel" aria-live="polite">
      <h1>Fukae</h1>
      <p>Verifying your session.</p>
    </section>

    <section v-else-if="!authenticated" class="credential-panel">
      <p class="eyebrow">Document intelligence</p>
      <h1>Fukae</h1>
      <p>Enter a bearer key to access indexing and file management.</p>
      <form @submit.prevent="submitKey">
        <label for="bearer-key">Bearer key</label>
        <input id="bearer-key" v-model="key" type="password" autocomplete="off" :disabled="submitting" />
        <p v-if="error" class="message error" role="alert">{{ error }}</p>
        <button class="filled-button" type="submit" :disabled="submitting">{{ submitting ? 'Verifying...' : 'Continue' }}</button>
      </form>
    </section>

    <template v-else>
      <header class="app-header">
        <div>
          <p class="eyebrow">Document intelligence</p>
          <h1>Fukae</h1>
        </div>
        <button class="text-button" type="button" @click="signOut">Sign out</button>
      </header>

      <nav class="tabs" aria-label="Application sections">
        <button :class="{ active: activeTab === 'indexing' }" type="button" @click="activeTab = 'indexing'">Indexing</button>
        <button :class="{ active: activeTab === 'files' }" type="button" @click="activeTab = 'files'">File Management</button>
      </nav>

      <section class="workspace">
        <IndexingView v-if="api" v-show="activeTab === 'indexing'" :api="api" />
        <FilesView v-if="api" v-show="activeTab === 'files'" :api="api" />
      </section>
    </template>
  </main>
</template>
