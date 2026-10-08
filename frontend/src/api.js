const storageKey = 'fukae.bearer-key'

export class AuthenticationError extends Error {}

export function loadStoredKey() {
  return sessionStorage.getItem(storageKey)
}

export function storeKey(key) {
  sessionStorage.setItem(storageKey, key)
}

export function clearStoredKey() {
  sessionStorage.removeItem(storageKey)
}

export function createApiClient(key, onUnauthorized) {
  async function request(path, options = {}) {
    const headers = new Headers(options.headers)
    headers.set('Authorization', `Bearer ${key}`)

    const response = await fetch(path, { ...options, headers })
    if (response.status === 401 || response.status === 403) {
      clearStoredKey()
      onUnauthorized?.()
      throw new AuthenticationError('Your bearer key is no longer valid.')
    }
    return response
  }

  return { request }
}

export async function verifyKey(key) {
  const response = await fetch('/auth/verify', {
    headers: { Authorization: `Bearer ${key}` },
  })
  return response.ok
}
