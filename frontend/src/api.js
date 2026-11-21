import { useEffect, useState } from 'react'

const origin = (import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')).replace(/\/+$/, '')
const POLL_MS = 5000

async function fetchJson(path, signal) {
  if (!origin) throw new Error('Set VITE_API_BASE_URL and rebuild the dashboard.')
  const url = new URL(origin)
  if (url.protocol !== 'https:' &&
    !(url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname))) {
    throw new Error('Use an HTTPS API URL or loopback HTTP for local development.')
  }
  const response = await fetch(origin + path, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(8000)]),
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.error || `API returned HTTP ${response.status}.`)
  }
  return response.json()
}

export function useApi(path) {
  const [state, setState] = useState({ path: null, data: null, error: null })
  const [attempt, retry] = useState(0)

  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    let timer
    async function refresh() {
      const started = Date.now()
      try {
        const data = await fetchJson(path, controller.signal)
        if (!controller.signal.aborted) setState({ path, data, error: null })
      } catch (error) {
        if (!controller.signal.aborted) {
          setState(previous => ({
            path,
            data: previous.path === path ? previous.data : null,
            error: error.name === 'TimeoutError' ? 'The API took too long to respond.'
              : error instanceof TypeError ? 'The API is unreachable. Check the service and allowed origin.'
                : error.message,
          }))
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, Math.max(0, POLL_MS - (Date.now() - started)))
      }
    }
    refresh()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [path, attempt])

  const current = state.path === path ? state : { data: null, error: null }
  return { ...current, loading: Boolean(path && !current.data && !current.error), retry: () => retry(n => n + 1) }
}
