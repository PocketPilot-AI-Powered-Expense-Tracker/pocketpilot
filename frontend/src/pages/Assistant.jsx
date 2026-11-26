import { Bot, Calculator, Check, MessageCircleQuestion, Send, Sparkles, Wand2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Button, Card, PageHeader, Spinner } from '../components/ui'
import { aiService } from '../services/aiService'
import { getErrorMessage } from '../utils/errors'

const ASK_EXAMPLES = [
  'How much money can I spend today?', 'How much did I spend on food this month?', 'Can I afford a ₹700 purchase?',
  'Why am I spending more this month?', 'How much should I save every week?', 'What is my biggest expense category?',
  'How much money will I have left at the end of the month?',
]
const DO_EXAMPLES = ['Add ₹150 for lunch today.', 'I received ₹2,000 pocket money.', 'Change my Sunday food budget to ₹250.', 'Skip my planned movie expense this week.']

function AnswerBubble({ m }) {
  return (
    <div className="space-y-3">
      <div>
        <span className={`mb-1 inline-flex items-center gap-1 text-[11px] font-semibold ${m.answered_by === 'ai' ? 'text-violet-700' : 'text-slate-600'}`}>
          {m.answered_by === 'ai' ? <><Sparkles className="h-3 w-3" /> AI explanation of verified numbers</> : <><Calculator className="h-3 w-3" /> PocketPilot calculation</>}
        </span>
        <p className="whitespace-pre-line text-sm text-slate-800">{m.answer}</p>
      </div>
      {m.facts.length > 0 && (
        <div className="rounded-lg bg-emerald-50/60 p-3 ring-1 ring-emerald-100">
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-800">Verified numbers</p>
          <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
            {m.facts.map((f) => (
              <div key={f.label} className="flex justify-between gap-3"><dt className="text-slate-600">{f.label}</dt><dd className="font-medium text-slate-900">{f.value}</dd></div>
            ))}
          </dl>
        </div>
      )}
      {m.notice && <p className="text-xs text-slate-500">{m.notice}</p>}
    </div>
  )
}

function ProposalBubble({ m, onUpdate }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const act = async (fn) => {
    setBusy(true)
    setError('')
    try {
      onUpdate(await fn(m.id))
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  if (m.status === 'unsupported') {
    return <p className="text-sm text-slate-700">{m.message}</p>
  }
  return (
    <div className={`rounded-xl p-3 ring-1 ${m.status === 'executed' ? 'bg-emerald-50 ring-emerald-200' : m.status === 'cancelled' ? 'bg-slate-50 ring-slate-200' : 'border-2 border-dashed border-amber-300 bg-amber-50/50 ring-0'}`}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {m.status === 'proposed' ? 'Proposed change · nothing saved yet' : m.status === 'executed' ? 'Done' : 'Cancelled'}
      </p>
      <p className="mt-0.5 font-medium text-slate-900">{m.title}</p>
      <dl className="mt-2 space-y-1 text-sm">
        {m.lines.map((l) => <div key={l.label} className="flex justify-between gap-4"><dt className="text-slate-600">{l.label}</dt><dd className="text-right font-medium text-slate-900">{l.value}</dd></div>)}
      </dl>
      {error && <div className="mt-2"><Alert>{error}</Alert></div>}
      {m.status === 'proposed' && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={() => act(aiService.confirm)} loading={busy}><Check className="h-4 w-4" /> Confirm</Button>
          <Button variant="secondary" onClick={() => act(aiService.cancel)} disabled={busy}><X className="h-4 w-4" /> Cancel</Button>
        </div>
      )}
      {m.status === 'executed' && <p className="mt-2 flex items-center gap-1 text-sm text-emerald-800"><Check className="h-4 w-4" /> {m.message}</p>}
      <p className="mt-2 text-[11px] text-slate-500">{m.interpreted_by === 'ai' ? 'Understood by AI, checked by PocketPilot.' : 'Understood by PocketPilot (AI not used).'}</p>
    </div>
  )
}

export default function Assistant() {
  const [mode, setMode] = useState('ask')
  const [text, setText] = useState('')
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)
  const endRef = useRef(null)

  useEffect(() => { aiService.status().then(setStatus).catch(() => {}) }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages])

  const send = async (value = text, m = mode) => {
    const q = value.trim()
    if (q.length < 2 || busy) return
    setText('')
    const id = Date.now()
    setMessages((list) => [...list, { id, role: 'user', text: q, mode: m }])
    setBusy(true)
    try {
      const res = m === 'ask' ? await aiService.ask(q) : await aiService.propose(q)
      setMessages((list) => [...list, { id: id + 1, role: 'bot', kind: m === 'ask' ? 'answer' : 'proposal', data: res }])
    } catch (err) {
      setMessages((list) => [...list, { id: id + 1, role: 'bot', kind: 'error', text: getErrorMessage(err) }])
    } finally {
      setBusy(false)
    }
  }

  const updateProposal = (msgId, data) => setMessages((list) => list.map((x) => (x.id === msgId ? { ...x, data } : x)))
  const examples = mode === 'ask' ? ASK_EXAMPLES : DO_EXAMPLES

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="AI assistant"
        subtitle="Ask about your money, or describe a change. PocketPilot calculates every number; AI only explains it. Changes always need your confirmation." />
      {status && !status.ai_available && (
        <div className="mb-4"><Alert type="success">AI isn't configured yet (no API key on the server), so answers use PocketPilot's built-in rules. Everything still works.</Alert></div>
      )}

      <Card className="flex min-h-[60vh] flex-col p-0">
        <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
          {messages.length === 0 && (
            <div className="py-6 text-center">
              <Bot className="mx-auto h-10 w-10 text-brand-600" />
              <p className="mt-2 font-medium text-slate-800">{mode === 'ask' ? 'What would you like to know?' : 'What should I add or change?'}</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {examples.map((e) => (
                  <button key={e} onClick={() => send(e)} className="rounded-full bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100">{e}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => m.role === 'user' ? (
            <div key={m.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2 text-sm text-white">{m.text}</div>
            </div>
          ) : (
            <div key={m.id} className="flex gap-2">
              <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700"><Bot className="h-4 w-4" /></span>
              <div className="min-w-0 max-w-[90%] flex-1 rounded-2xl rounded-tl-sm bg-white p-3 ring-1 ring-slate-200">
                {m.kind === 'answer' && <AnswerBubble m={m.data} />}
                {m.kind === 'proposal' && <ProposalBubble m={m.data} onUpdate={(d) => updateProposal(m.id, d)} />}
                {m.kind === 'error' && <Alert>{m.text}</Alert>}
              </div>
            </div>
          ))}
          {busy && <div className="flex items-center gap-2 text-sm text-slate-500"><Spinner className="h-4 w-4" /> Thinking…</div>}
          <div ref={endRef} />
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send() }} className="border-t border-slate-100 p-3">
          <div className="mb-2 inline-flex rounded-lg bg-slate-100 p-1 text-xs" role="radiogroup" aria-label="Mode">
            <button type="button" role="radio" aria-checked={mode === 'ask'} onClick={() => setMode('ask')}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 font-medium ${mode === 'ask' ? 'bg-white shadow-sm' : 'text-slate-600'}`}>
              <MessageCircleQuestion className="h-3.5 w-3.5" /> Ask a question
            </button>
            <button type="button" role="radio" aria-checked={mode === 'do'} onClick={() => setMode('do')}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 font-medium ${mode === 'do' ? 'bg-white shadow-sm' : 'text-slate-600'}`}>
              <Wand2 className="h-3.5 w-3.5" /> Make a change
            </button>
          </div>
          <div className="flex gap-2">
            <input value={text} onChange={(e) => setText(e.target.value)} maxLength={300} aria-label="Message"
              placeholder={mode === 'ask' ? 'e.g. Can I afford a ₹700 purchase?' : 'e.g. Add ₹150 for lunch today'}
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100" />
            <Button type="submit" loading={busy} disabled={text.trim().length < 2} aria-label="Send"><Send className="h-4 w-4" /></Button>
          </div>
          {messages.length > 0 && (
            <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1">
              {examples.slice(0, 4).map((e) => <button type="button" key={e} onClick={() => send(e)} className="shrink-0 rounded-full px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50">{e}</button>)}
            </div>
          )}
        </form>
      </Card>
      <p className="mt-3 text-center text-xs text-slate-500">Want the full picture? See your <Link to="/report" className="text-brand-700 underline">monthly report</Link>.</p>
    </div>
  )
}
