import { Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CHART, categoryMeta } from '../utils/constants'
import { fmtDate } from '../utils/dates'
import { formatINR } from '../utils/money'

const compactINR = (paise) => {
  const r = paise / 100
  if (r >= 100000) return `₹${(r / 100000).toFixed(r % 100000 ? 1 : 0)}L`
  if (r >= 1000) return `₹${(r / 1000).toFixed(r % 1000 ? 1 : 0)}k`
  return `₹${Math.round(r)}`
}

const axisProps = { stroke: CHART.axis, fontSize: 12, tickLine: false, axisLine: false }

function TooltipBox({ title, rows }) {
  return (
    <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">
      <p className="mb-1 font-medium text-slate-800">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2 text-slate-600">
          {r.color && <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />}
          {r.label}: <span className="font-semibold text-slate-900">{r.value}</span>
        </p>
      ))}
    </div>
  )
}

/** Sorted horizontal bars, one hue (magnitude per category). */
export function CategoryBars({ data }) {
  const rows = data.map((d) => ({ ...d, label: categoryMeta(d.category).label }))
  return (
    <ResponsiveContainer width="100%" height={Math.max(140, rows.length * 38)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 0 }} barCategoryGap={8}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="label" width={104} {...axisProps} />
        <Tooltip cursor={{ fill: '#f1f5f9' }}
          content={({ active, payload }) => active && payload?.length ? (
            <TooltipBox title={payload[0].payload.label} rows={[{ label: 'Spent', value: `${formatINR(payload[0].payload.amount_paise)} (${payload[0].payload.pct}%)` }]} />
          ) : null} />
        <Bar dataKey="amount_paise" fill={CHART.series1} radius={[0, 4, 4, 0]} maxBarSize={22}>
          <LabelList dataKey="amount_paise" position="right" formatter={formatINR} style={{ fill: '#334155', fontSize: 12 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Cumulative spending vs. the even pace for this period. */
export function PaceChart({ data }) {
  const rows = data.map((d) => ({ ...d, label: fmtDate(d.date) }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="label" {...axisProps} minTickGap={24} />
        <YAxis tickFormatter={compactINR} {...axisProps} width={52} />
        <Tooltip cursor={{ stroke: CHART.axis, strokeDasharray: '3 3' }}
          content={({ active, payload }) => active && payload?.length ? (
            <TooltipBox title={payload[0].payload.label} rows={[
              { label: 'Spent so far', value: formatINR(payload[0].payload.cumulative_paise), color: CHART.series1 },
              { label: 'Even pace', value: formatINR(payload[0].payload.pace_paise), color: CHART.series2 },
              { label: 'Spent that day', value: formatINR(payload[0].payload.spent_paise) },
            ]} />
          ) : null} />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
        <Line name="Spent so far" dataKey="cumulative_paise" stroke={CHART.series1} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        <Line name="Even pace" dataKey="pace_paise" stroke={CHART.series2} strokeWidth={2} strokeDasharray="5 4" dot={false} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Income vs. expenses per budget period. */
export function MonthlyTrendChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barGap={2} barCategoryGap="28%">
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="label" {...axisProps} />
        <YAxis tickFormatter={compactINR} {...axisProps} width={52} />
        <Tooltip cursor={{ fill: '#f1f5f9' }}
          content={({ active, payload }) => active && payload?.length ? (
            <TooltipBox title={payload[0].payload.label} rows={[
              { label: 'Income', value: formatINR(payload[0].payload.income_paise), color: CHART.series1 },
              { label: 'Expenses', value: formatINR(payload[0].payload.expenses_paise), color: CHART.series2 },
            ]} />
          ) : null} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar name="Income" dataKey="income_paise" fill={CHART.series1} radius={[4, 4, 0, 0]} maxBarSize={28} />
        <Bar name="Expenses" dataKey="expenses_paise" fill={CHART.series2} radius={[4, 4, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  )
}
