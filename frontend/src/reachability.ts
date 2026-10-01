export async function checkServiceReachable(url: string, fetcher: typeof fetch = fetch, timeoutMs = 4000) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetcher(url, { cache: 'no-store', signal: controller.signal })
    if (!response.ok) throw new Error('Service is unavailable')
  } finally {
    clearTimeout(timeoutId)
  }
}
