import { useEffect, useState } from 'react'

type ApiState = 'checking' | 'healthy' | 'unavailable'

interface HealthResponse {
  status: 'ok'
  service: string
}

export default function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')

  useEffect(() => {
    const controller = new AbortController()

    async function checkApi() {
      try {
        const response = await fetch('/api/health', { signal: controller.signal })
        if (!response.ok) throw new Error(`Health check failed: ${response.status}`)
        const health: HealthResponse = await response.json()
        setApiState(health.status === 'ok' ? 'healthy' : 'unavailable')
      } catch (error) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setApiState('unavailable')
        }
      }
    }

    void checkApi()
    return () => controller.abort()
  }, [])

  const statusText = {
    checking: 'Checking API…',
    healthy: 'API connected',
    unavailable: 'API unavailable',
  }[apiState]

  return (
    <main className="shell">
      <section className="hero" aria-labelledby="title">
        <p className="eyebrow">Technical knowledge, mapped</p>
        <h1 id="title">DevAtlas</h1>
        <p className="subtitle">AI Technical Research &amp; Knowledge Platform</p>
        <div className={`status status--${apiState}`} role="status">
          <span className="status__dot" aria-hidden="true" />
          {statusText}
        </div>
      </section>
    </main>
  )
}
