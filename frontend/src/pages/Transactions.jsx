import { ArrowDownLeft, Pencil, Plus, Receipt, Search, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { CategoryBadge, CategoryIcon } from '../components/CategoryBadge'
import { ConfirmDialog } from '../components/Modal'
import { Alert, Button, Card, EmptyState, Field, FullPageLoader, PageHeader, Select } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { expenseService, incomeService } from '../services/transactionService'
import { CATEGORIES, paymentLabel } from '../utils/constants'
import { relativeDay } from '../utils/dates'
import { getErrorMessage } from '../utils/errors'
import { formatINR } from '../utils/money'

const PAGE = 30

export default function Transactions() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'income' ? 'income' : 'expenses'
  const location = useLocation()
  const navigate = useNavigate()
  const [flash, setFlash] = useState(location.state?.flash || '')
  const [filters, setFilters] = useState({ from: '', to: '', category: '', q: '' })
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE)
  const [toDelete, setToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [actionError, setActionError] = useState('')

  // Clear one-time flash message from history state.
  useEffect(() => {
    if (location.state?.flash) navigate(location.pathname + location.search, { replace: true, state: null })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounce search typing.
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: query })), 300)
    return () => clearTimeout(t)
  }, [query])

  const service = tab === 'income' ? incomeService : expenseService
  const { data, error, loading, reload } = useAsync(
    () => service.list({ ...filters, category: tab === 'income' ? '' : filters.category, limit }),
    [tab, filters, limit],
  )

  const switchTab = (t) => { setParams({ tab: t }); setLimit(PAGE) }
  const hasFilters = filters.from || filters.to || filters.q || (tab === 'expenses' && filters.category)
  const clearFilters = () => { setFilters({ from: '', to: '', category: '', q: '' }); setQuery('') }

  const confirmDelete = async () => {
    setDeleting(true)
    setActionError('')
    try {
      await service.remove(toDelete.id)
      setFlash(tab === 'income' ? 'Income deleted.' : 'Expense deleted.')
      setToDelete(null)
      reload({ silent: true })
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Transactions"
        subtitle="Your confirmed expenses and income."
        actions={
          <>
            <Link to="/income/new"><Button variant="secondary"><ArrowDownLeft className="h-4 w-4" /> Add income</Button></Link>
            <Link to="/expenses/new"><Button><Plus className="h-4 w-4" /> Add expense</Button></Link>
          </>
        }
      />

      <div className="mb-4 inline-flex rounded-lg bg-slate-100 p-1" role="tablist">
        {['expenses', 'income'].map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => switchTab(t)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize transition ${tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'}`}>
            {t}
          </button>
        ))}
      </div>

      <Card className="mb-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-[1fr_10rem_10rem_11rem_auto] lg:items-end">
          <div className="relative col-span-2 lg:col-span-1">
            <Field id="q" label="Search" placeholder={tab === 'income' ? 'Source or description' : 'Description or notes'}
              value={query} onChange={(e) => setQuery(e.target.value)} prefix={<Search className="h-4 w-4" />} />
          </div>
          <Field id="from" label="From" type="date" value={filters.from} onChange={(e) => setFilters({ ...filters, from: e.target.value })} />
          <Field id="to" label="To" type="date" value={filters.to} onChange={(e) => setFilters({ ...filters, to: e.target.value })} />
          {tab === 'expenses' ? (
            <div className="col-span-2 lg:col-span-1"><Select id="category" label="Category" value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })}>
              <option value="">All categories</option>
              {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </Select></div>
          ) : <div className="hidden lg:block" />}
          {hasFilters ? (
            <Button variant="secondary" className="col-span-2 lg:col-span-1" onClick={clearFilters}><X className="h-4 w-4" /> Clear</Button>
          ) : <div className="hidden lg:block" />}
        </div>
      </Card>

      <div className="mb-3 space-y-2">
        <Alert type="success">{flash}</Alert>
        <Alert>{actionError}</Alert>
      </div>

      {loading && !data ? (
        <FullPageLoader />
      ) : error ? (
        <div className="space-y-3"><Alert>{error}</Alert><Button variant="secondary" onClick={() => reload()}>Try again</Button></div>
      ) : data.items.length === 0 ? (
        <Card>
          <EmptyState icon={Receipt} title={hasFilters ? 'Nothing matches these filters' : `No ${tab} yet`}
            action={hasFilters ? <Button variant="secondary" onClick={clearFilters}>Clear filters</Button>
              : <Link to={tab === 'income' ? '/income/new' : '/expenses/new'}><Button><Plus className="h-4 w-4" /> Add {tab === 'income' ? 'income' : 'an expense'}</Button></Link>}>
            {hasFilters ? 'Try a different date range, category or search.' : tab === 'income'
              ? 'Log pocket money, scholarships or part-time earnings here.'
              : 'Every rupee you log makes your safe-to-spend number more accurate.'}
          </EmptyState>
        </Card>
      ) : (
        <Card className="p-0">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3 text-sm">
            <span className="text-slate-500">{data.total} {data.total === 1 ? 'record' : 'records'}</span>
            <span className="font-semibold text-slate-800">Total {formatINR(data.total_amount_paise)}</span>
          </div>
          <ul className="divide-y divide-slate-100">
            {data.items.map((t) => (
              <li key={t.id} className="flex items-center gap-3 px-5 py-3">
                {tab === 'expenses' ? <CategoryIcon category={t.category} /> : (
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><ArrowDownLeft className="h-4 w-4" /></span>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-800">{tab === 'expenses' ? t.description : t.source}</p>
                  <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                    <span>{relativeDay(t.date)}</span>
                    {tab === 'expenses' ? (
                      <>
                        <CategoryBadge category={t.category} />
                        <span>{paymentLabel(t.payment_method)}</span>
                        {t.source === 'routine' && (t.auto_deducted
                          ? <span className="rounded-full bg-violet-50 px-2 py-0.5 text-violet-700">Auto-deducted</span>
                          : <span className="rounded-full bg-sky-50 px-2 py-0.5 text-sky-700">Recurring</span>)}
                        {t.source === 'upi_review' && <span className="rounded-full bg-violet-50 px-2 py-0.5 text-violet-700">From UPI review</span>}
                      </>
                    ) : (
                      <>
                        {t.description && <span className="truncate">{t.description}</span>}
                        <span className={`rounded-full px-2 py-0.5 ${t.counts_as_planned ? 'bg-slate-100 text-slate-600' : 'bg-emerald-50 text-emerald-700'}`}>
                          {t.counts_as_planned ? 'In monthly budget' : 'Extra income'}
                        </span>
                      </>
                    )}
                  </p>
                  {t.notes && <p className="mt-0.5 truncate text-xs text-slate-400">{t.notes}</p>}
                </div>
                <span className={`shrink-0 text-sm font-semibold ${tab === 'income' ? 'text-emerald-700' : 'text-slate-900'}`}>
                  {tab === 'income' ? '+' : '−'}{formatINR(t.amount_paise)}
                </span>
                <div className="flex shrink-0">
                  <Link to={tab === 'income' ? `/income/${t.id}/edit` : `/expenses/${t.id}/edit`}
                    className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Edit"><Pencil className="h-4 w-4" /></Link>
                  <button onClick={() => setToDelete(t)} className="rounded-lg p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-600" aria-label="Delete">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {data.items.length < data.total && (
            <div className="border-t border-slate-100 p-3 text-center">
              <Button variant="secondary" loading={loading} onClick={() => setLimit((l) => Math.min(l + PAGE, 100))} disabled={limit >= 100}>
                {limit >= 100 ? 'Use filters to see older records' : 'Load more'}
              </Button>
            </div>
          )}
        </Card>
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title={tab === 'income' ? 'Delete income?' : 'Delete expense?'}
        message={toDelete && `${tab === 'income' ? toDelete.source : toDelete.description} · ${formatINR(toDelete.amount_paise)}. ${
          toDelete.source === 'routine' ? (toDelete.auto_deducted
            ? 'This date will be marked as skipped so it is not deducted again. You can restore it on the Planned page.'
            : 'The planned date it came from will go back to your calendar.')
            : toDelete.source === 'upi_review' ? 'The detected payment will go back to "Awaiting review".' : 'This cannot be undone.'}`}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
        loading={deleting}
      />
    </div>
  )
}
