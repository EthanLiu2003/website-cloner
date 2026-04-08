'use client'
import { useState, useEffect, useRef, useCallback } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type JobStatus = {
  status: string
  progress: number
  message: string
  error?: string
  result_url?: string
  pages_found?: number
  pages_cloned?: number
}

type ClonedPage = {
  url: string
  path: string
  title?: string
}

export default function Home() {
  const [url, setUrl] = useState('')
  const [crawl, setCrawl] = useState(false)
  const [maxPages, setMaxPages] = useState(5)
  const [isLoading, setIsLoading] = useState(false)
  const [jobId, setJobId] = useState('')
  const [error, setError] = useState('')
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [activeTab, setActiveTab] = useState<'clone' | 'compare'>('clone')
  const [pages, setPages] = useState<ClonedPage[]>([])
  const [selectedPage, setSelectedPage] = useState(0)
  const eventSourceRef = useRef<EventSource | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const startPolling = useCallback((id: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current)
    pollingRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_URL}/api/status/${id}`)
        const data: JobStatus = await response.json()
        setJobStatus(data)
        if (data.status === 'completed' || data.status === 'error') {
          if (pollingRef.current) {
            clearInterval(pollingRef.current)
            pollingRef.current = null
          }
        }
      } catch (err) {
        console.error('Polling failed:', err)
      }
    }, 2000)
  }, [])

  const startSSE = useCallback((id: string) => {
    cleanup()
    const eventSource = new EventSource(`${API_URL}/api/clone/${id}/stream`)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data: JobStatus = JSON.parse(event.data)
        if ((event as MessageEvent & { type: string }).type === 'heartbeat') return
        setJobStatus(data)
        if (data.status === 'completed' || data.status === 'error') {
          eventSource.close()
          eventSourceRef.current = null
        }
      } catch (err) {
        console.error('SSE parse error:', err)
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      eventSourceRef.current = null
      startPolling(id)
    }
  }, [cleanup, startPolling])

  // Fetch pages list when job completes for multi-page clones
  useEffect(() => {
    if (jobStatus?.status === 'completed' && crawl && jobId) {
      fetch(`${API_URL}/api/preview/${jobId}/pages`)
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data)) setPages(data)
          else if (data.pages) setPages(data.pages)
        })
        .catch(() => setPages([]))
    }
  }, [jobStatus?.status, crawl, jobId])

  useEffect(() => {
    return cleanup
  }, [cleanup])

  const handleClone = async () => {
    if (!url) {
      setError('Please enter a URL')
      return
    }

    try {
      new URL(url)
    } catch {
      setError('Invalid URL format. Please include http:// or https://')
      return
    }

    setError('')
    setIsLoading(true)
    setJobStatus(null)
    setJobId('')
    setPages([])
    setSelectedPage(0)
    setActiveTab('clone')

    try {
      const response = await fetch(`${API_URL}/api/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          crawl,
          max_pages: maxPages,
          max_depth: 2,
        }),
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

      const data = await response.json()
      setJobId(data.job_id)
      startSSE(data.job_id)
    } catch (err) {
      setError('Failed to start cloning: ' + (err instanceof Error ? err.message : 'Unknown error'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleReset = () => {
    cleanup()
    setUrl('')
    setError('')
    setIsLoading(false)
    setJobId('')
    setJobStatus(null)
    setPages([])
    setSelectedPage(0)
  }

  const isCompleted = jobStatus?.status === 'completed'
  const isError = jobStatus?.status === 'error'
  const isInProgress = jobId && !isCompleted && !isError

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-[800px]">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold tracking-tight mb-2">
            Website Cloner
          </h1>
          <p className="text-white/50 text-lg">
            AI-powered website cloning
          </p>
        </div>

        {/* URL Input Section */}
        <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-6 mb-6">
          <div className="flex gap-3">
            <input
              type="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                if (error) setError('')
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !isLoading && !isInProgress) handleClone()
              }}
              placeholder="Enter website URL to clone..."
              className="flex-1 rounded-lg bg-white/5 border border-white/10 px-4 py-3 text-white placeholder-white/30 outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
            />
            <button
              onClick={handleClone}
              disabled={isLoading || !!isInProgress}
              className="rounded-lg bg-gradient-to-r from-purple-600 to-blue-500 px-6 py-3 font-semibold text-white hover:from-purple-500 hover:to-blue-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 cursor-pointer whitespace-nowrap"
            >
              {isLoading ? 'Starting...' : 'Clone'}
            </button>
          </div>

          {/* Multi-page options */}
          <div className="mt-4 flex items-center gap-6">
            <label className="flex items-center gap-3 cursor-pointer select-none">
              <div className="relative">
                <input
                  type="checkbox"
                  checked={crawl}
                  onChange={(e) => setCrawl(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-10 h-5 rounded-full bg-white/10 peer-checked:bg-purple-600 transition-all duration-300" />
                <div className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-all duration-300 peer-checked:translate-x-5" />
              </div>
              <span className="text-sm text-white/70">Multi-page cloning</span>
            </label>

            {crawl && (
              <div className="flex items-center gap-3 transition-all duration-300">
                <label className="text-sm text-white/50">Max pages:</label>
                <input
                  type="range"
                  min={2}
                  max={10}
                  value={maxPages}
                  onChange={(e) => setMaxPages(Number(e.target.value))}
                  className="w-24 accent-purple-500"
                />
                <span className="text-sm font-mono text-white/70 w-5 text-center">
                  {maxPages}
                </span>
              </div>
            )}
          </div>

          {/* Inline error */}
          {error && (
            <p className="mt-3 text-sm text-red-400">{error}</p>
          )}
        </div>

        {/* Progress Section */}
        {isInProgress && (
          <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-6 mb-6 transition-all duration-300">
            <div className="mb-3">
              <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-purple-600 to-blue-500 transition-all duration-500 ease-out"
                  style={{ width: `${jobStatus?.progress ?? 0}%` }}
                />
              </div>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-white/50">
                {jobStatus?.message || 'Starting clone...'}
              </span>
              <span className="text-white/70 font-mono">
                {jobStatus?.progress ?? 0}%
              </span>
            </div>
            {crawl && jobStatus?.pages_found != null && (
              <p className="mt-2 text-sm text-white/40">
                Page {jobStatus.pages_cloned ?? 0} of {jobStatus.pages_found}
              </p>
            )}
          </div>
        )}

        {/* Error Section */}
        {isError && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 backdrop-blur-sm p-6 mb-6">
            <p className="text-red-400 mb-4">
              {jobStatus?.error || 'An unknown error occurred'}
            </p>
            <button
              onClick={handleReset}
              className="rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-all duration-300 cursor-pointer"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Results Section */}
        {isCompleted && jobId && (
          <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm overflow-hidden">
            {/* Tabs + actions */}
            <div className="flex items-center justify-between border-b border-white/10 px-4">
              <div className="flex">
                <button
                  onClick={() => setActiveTab('clone')}
                  className={`px-4 py-3 text-sm font-medium transition-all duration-300 border-b-2 cursor-pointer ${
                    activeTab === 'clone'
                      ? 'border-purple-500 text-white'
                      : 'border-transparent text-white/40 hover:text-white/70'
                  }`}
                >
                  Clone
                </button>
                <button
                  onClick={() => setActiveTab('compare')}
                  className={`px-4 py-3 text-sm font-medium transition-all duration-300 border-b-2 cursor-pointer ${
                    activeTab === 'compare'
                      ? 'border-purple-500 text-white'
                      : 'border-transparent text-white/40 hover:text-white/70'
                  }`}
                >
                  Compare
                </button>
              </div>

              <div className="flex items-center gap-3">
                {/* Multi-page selector */}
                {crawl && pages.length > 0 && (
                  <select
                    value={selectedPage}
                    onChange={(e) => setSelectedPage(Number(e.target.value))}
                    className="rounded-lg bg-white/5 border border-white/10 px-3 py-1.5 text-sm text-white outline-none focus:ring-2 focus:ring-purple-500/50"
                  >
                    {pages.map((page, i) => (
                      <option key={i} value={i} className="bg-neutral-900">
                        {page.title || page.url || `Page ${i + 1}`}
                      </option>
                    ))}
                  </select>
                )}

                <a
                  href={`${API_URL}/api/preview/${jobId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg bg-white/5 border border-white/10 px-3 py-1.5 text-sm text-white/70 hover:text-white hover:bg-white/10 transition-all duration-300"
                >
                  Open in New Tab
                </a>
              </div>
            </div>

            {/* Tab content */}
            {activeTab === 'clone' && (
              <div className="w-full">
                <iframe
                  src={
                    crawl && pages.length > 0 && pages[selectedPage]?.path
                      ? `${API_URL}${pages[selectedPage].path}`
                      : `${API_URL}/api/preview/${jobId}`
                  }
                  className="w-full h-[600px] border-0 bg-white"
                  title="Cloned website preview"
                />
              </div>
            )}

            {activeTab === 'compare' && (
              <div className="grid grid-cols-2 gap-0">
                {/* Original screenshot */}
                <div className="border-r border-white/10">
                  <div className="px-3 py-2 text-xs text-white/40 border-b border-white/10 text-center">
                    Original
                  </div>
                  <div className="h-[600px] overflow-auto">
                    <img
                      src={`${API_URL}/api/preview/${jobId}/screenshot`}
                      alt="Original website screenshot"
                      className="w-full"
                    />
                  </div>
                </div>
                {/* Cloned preview */}
                <div>
                  <div className="px-3 py-2 text-xs text-white/40 border-b border-white/10 text-center">
                    Clone
                  </div>
                  <iframe
                    src={
                      crawl && pages.length > 0 && pages[selectedPage]?.path
                        ? `${API_URL}${pages[selectedPage].path}`
                        : `${API_URL}/api/preview/${jobId}`
                    }
                    className="w-full h-[600px] border-0 bg-white"
                    title="Cloned website comparison"
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
