import { BellRing, ChevronDown, FlaskConical, Repeat2, Send } from 'lucide-react'
import { useState } from 'react'
import { pendingService } from '../services/pendingService'
import { getErrorMessage } from '../utils/errors'
import { formatINR } from '../utils/money'
import { SAMPLE_NOTIFICATIONS, SOURCE_APPS, randomRef } from '../utils/upiSamples'
import { Alert, Button, Card, Field, Select } from './ui'

/** Testing tool: sends a sample notification through the same parser the Android app will use. */
export default function NotificationSimulator({ onCreated }) {
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState({ source_app: 'phonepe', title: 'Payment Successful', text: '' })
  const [last, setLast] = useState(null)
  const [result, setResult] = useState(null) // { type: 'success'|'error', text }
  const [busy, setBusy] = useState(false)

  const send = async (payload) => {
    setBusy(true)
    setResult(null)
    try {
      const res = await pendingService.simulate(payload)
      setLast(payload)
      const t = res.transaction
      setResult(res.duplicate
        ? { type: 'success', text: `Duplicate detected: this notification was already received (${formatINR(t.amount_paise)}). Nothing new was created.` }
        : { type: 'success', text: `Detected ${formatINR(t.amount_paise)}${t.counterparty ? ` to ${t.counterparty}` : ''}. It is waiting for your review.` })
      onCreated?.(res)
    } catch (err) {
      setLast(payload)
      setResult({ type: 'error', text: getErrorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  const sendSample = (s) => send({ source_app: s.source_app, title: s.title, text: s.text.replace('{ref}', randomRef()), posted_at: new Date().toISOString() })

  return (
    <Card className="border border-dashed border-slate-300 ring-0">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-3 text-left" aria-expanded={open}>
        <span className="flex items-center gap-2">
          <FlaskConical className="h-5 w-5 text-slate-500" />
          <span>
            <span className="block font-medium text-slate-900">Notification simulator</span>
            <span className="block text-xs text-slate-500">For testing: pretend a UPI app sent a notification.</span>
          </span>
        </span>
        <ChevronDown className={`h-5 w-5 text-slate-400 transition ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            A website can't read your phone's notifications. A future Android companion app will do that (with your permission)
            and send detected payments here. Until then, use these samples. Credits, requests and failed payments are ignored on purpose.
          </p>
          <div className="flex flex-wrap gap-1.5">
            {SAMPLE_NOTIFICATIONS.map((s) => (
              <button key={s.label} disabled={busy} onClick={() => sendSample(s)}
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-50">
                <BellRing className="h-3 w-3" /> {s.label}
              </button>
            ))}
          </div>

          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (custom.text.trim()) send({ ...custom, posted_at: new Date().toISOString() }) }}>
            <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
              <Select id="sim-app" label="App" value={custom.source_app} onChange={(e) => setCustom({ ...custom, source_app: e.target.value })}>
                {SOURCE_APPS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
              </Select>
              <Field id="sim-title" label="Title" value={custom.title} maxLength={120} onChange={(e) => setCustom({ ...custom, title: e.target.value })} />
            </div>
            <Field id="sim-text" label="Notification text" placeholder="₹75 paid to Canteen. UPI Ref No. 123456789012" maxLength={400}
              value={custom.text} onChange={(e) => setCustom({ ...custom, text: e.target.value })} />
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="secondary" loading={busy} disabled={!custom.text.trim()}><Send className="h-4 w-4" /> Send custom</Button>
              {last && (
                <Button type="button" variant="secondary" disabled={busy} onClick={() => send(last)} title="Re-send the exact same notification to test duplicate prevention">
                  <Repeat2 className="h-4 w-4" /> Send same again
                </Button>
              )}
            </div>
          </form>
          {result && <Alert type={result.type}>{result.text}</Alert>}
        </div>
      )}
    </Card>
  )
}
