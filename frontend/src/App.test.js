import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'
import { clearStoredKey, createApiClient, loadStoredKey, storeKey } from './api'

function response(ok, body = {}) {
  return { ok, status: ok ? 200 : 401, json: async () => body }
}

function mockFetch(verifyOk = true) {
  globalThis.fetch = vi.fn((path) => {
    if (path === '/auth/verify') return Promise.resolve(response(verifyOk, { authenticated: verifyOk }))
    if (path.includes('/files/')) return Promise.resolve(response(true, { files: [] }))
    return Promise.resolve(response(true))
  })
}

describe('Fukae credential gate', () => {
  afterEach(() => {
    clearStoredKey()
    vi.unstubAllGlobals()
  })

  it('unlocks the tabs and stores a verified key', async () => {
    mockFetch()
    const wrapper = mount(App)
    await flushPromises()
    await wrapper.get('#bearer-key').setValue('valid-key')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(loadStoredKey()).toBe('valid-key')
    expect(wrapper.text()).toContain('Indexing')
    expect(wrapper.text()).toContain('File Management')
  })

  it('revalidates a stored key and clears it when rejected', async () => {
    storeKey('expired-key')
    mockFetch(false)
    const wrapper = mount(App)
    await flushPromises()

    expect(loadStoredKey()).toBeNull()
    expect(wrapper.text()).toContain('The bearer key was not accepted.')
  })

  it('injects a bearer header and clears storage after an unauthorized response', async () => {
    storeKey('valid-key')
    const onUnauthorized = vi.fn()
    globalThis.fetch = vi.fn().mockResolvedValue(response(false))
    const client = createApiClient('valid-key', onUnauthorized)

    await expect(client.request('/files/uploads/list')).rejects.toThrow('no longer valid')
    expect(globalThis.fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer valid-key')
    expect(loadStoredKey()).toBeNull()
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })
})