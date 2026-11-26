import { Component } from 'react'

/** Catches unexpected rendering errors so one broken widget doesn't blank the whole app. */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('PocketPilot UI error:', error, info?.componentStack)
  }

  componentDidUpdate(prev) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="mx-auto max-w-md py-16 text-center">
        <p className="text-lg font-semibold text-slate-900">Something went wrong on this page</p>
        <p className="mt-2 text-sm text-slate-500">Your data is safe. Try reloading, or go back to the dashboard.</p>
        <div className="mt-5 flex justify-center gap-2">
          <button onClick={() => window.location.reload()} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white">Reload</button>
          <a href="/dashboard" className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-700 ring-1 ring-slate-300">Dashboard</a>
        </div>
      </div>
    )
  }
}
