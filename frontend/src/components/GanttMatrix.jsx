import { useMemo } from 'react'
import { fmtDate } from './ui.jsx'

const COL = 30 // px per calendar day column

export default function GanttMatrix({ gantt }) {
  const { columns, rows } = gantt

  const monthSpans = useMemo(() => {
    const spans = []
    columns.forEach((col) => {
      const last = spans[spans.length - 1]
      if (last && last.month === col.month) last.span += 1
      else spans.push({ month: col.month, span: 1 })
    })
    return spans
  }, [columns])

  const todayIndex = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10)
    return columns.findIndex((c) => c.date === today)
  }, [columns])

  return (
    <div className="glass overflow-hidden rounded-2xl">
      <div className="overflow-x-auto">
        <table className="border-collapse text-sm" style={{ minWidth: 'max-content' }}>
          <thead>
            <tr>
              <StickyHead className="w-10" rowSpan={3}>Ref</StickyHead>
              <StickyHead className="w-72" left={40} rowSpan={3}>Tasks</StickyHead>
              <StickyHead className="w-72" left={328} rowSpan={3}>Role &amp; Employee</StickyHead>
              <th className="th border-b border-l border-white/[0.06] bg-ink-800/80 text-right" rowSpan={3}>Days</th>
              <th className="th border-b border-l border-white/[0.06] bg-ink-800/80" rowSpan={3}>Start</th>
              <th className="th border-b border-white/[0.06] bg-ink-800/80" rowSpan={3}>End</th>
              {monthSpans.map((m) => (
                <th key={m.month} colSpan={m.span}
                  className="border-b border-l border-white/[0.08] bg-ink-700/60 px-2 py-1 text-center text-xs font-semibold text-bone-300">
                  {m.month}
                </th>
              ))}
            </tr>
            <tr>
              {columns.map((col) => (
                <th key={`d-${col.date}`}
                  className={`border-b border-l border-white/[0.06] px-0 py-1 text-center text-[11px] font-medium tabular-nums ${cellTone(col)}`}
                  style={{ width: COL, minWidth: COL }}>
                  {col.day}
                </th>
              ))}
            </tr>
            <tr>
              {columns.map((col) => (
                <th key={`w-${col.date}`}
                  className={`border-b border-l border-white/[0.06] px-0 pb-1 text-center text-[10px] font-normal text-bone-600 ${cellTone(col)}`}>
                  {col.weekday}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) =>
              row.kind === 'stage' ? (
                <StageRow key={`s-${index}`} row={row} columns={columns} />
              ) : (
                <TaskRow key={`t-${row.task_id}`} row={row} columns={columns} todayIndex={todayIndex} />
              ),
            )}
          </tbody>
        </table>
      </div>
      <Legend />
    </div>
  )
}

function StickyHead({ children, className = '', left = 0, rowSpan }) {
  return (
    <th rowSpan={rowSpan}
      className={`th sticky z-20 border-b border-r border-white/[0.08] bg-ink-800/95 backdrop-blur ${className}`}
      style={{ left }}>
      {children}
    </th>
  )
}

function cellTone(col) {
  if (col.is_holiday) return 'bg-teal-500/[0.07]'
  if (col.is_weekend_blue) return 'bg-white/[0.035]'
  if (col.is_weekend_white) return 'bg-white/[0.02]'
  return ''
}

function StageRow({ row, columns }) {
  return (
    <tr className="bg-white/[0.03] font-semibold">
      <td className="sticky left-0 z-10 border-b border-r border-white/[0.08] bg-ink-800 px-2 py-1.5" />
      <td className="sticky z-10 border-b border-white/[0.08] bg-ink-800 px-3 py-1.5 text-sm text-bone-100" style={{ left: 40 }}>
        {row.label}
      </td>
      <td className="sticky z-10 border-b border-r border-white/[0.08] bg-ink-800 px-3 py-1.5 text-xs text-bone-500" style={{ left: 328 }}>
        {row.resource}
      </td>
      <td className="border-b border-l border-white/[0.06] px-3 py-1.5 text-right tabular-nums text-bone-300">{row.days}</td>
      <td className="border-b border-l border-white/[0.06] px-3 py-1.5 text-xs tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(row.start)}</td>
      <td className="border-b border-white/[0.06] px-3 py-1.5 text-xs tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(row.end)}</td>
      {columns.map((col) => {
        const label = row.cells[col.date]
        return (
          <td key={col.date} className={`border-b border-l border-white/[0.06] px-0 py-1.5 ${cellTone(col)}`} style={{ width: COL, minWidth: COL }}>
            {label && (
              <span className="whitespace-nowrap rounded bg-gradient-to-r from-brass-400 to-brass-600 px-1.5 py-0.5 text-[10px] font-semibold text-ink-950">
                {label}
              </span>
            )}
          </td>
        )
      })}
    </tr>
  )
}

function TaskRow({ row, columns, todayIndex }) {
  const unassigned = !row.employee
  return (
    <tr className="transition-colors hover:bg-brass-500/[0.04]">
      <td className="sticky left-0 z-10 border-b border-r border-white/[0.08] bg-ink-900 px-2 py-1 text-center text-xs tabular-nums text-bone-600">
        {row.ref}
      </td>
      <td className="sticky z-10 border-b border-white/[0.06] bg-ink-900 px-3 py-1 text-sm text-bone-100" style={{ left: 40 }}>
        {row.label}
      </td>
      <td
        className={`sticky z-10 border-b border-r border-white/[0.08] bg-ink-900 px-3 py-1 text-xs ${unassigned ? 'font-semibold text-red-300' : 'text-bone-500'}`}
        style={{ left: 328 }} title={row.shortage?.reason || ''}>
        {row.resource}
      </td>
      <td className="border-b border-l border-white/[0.06] px-3 py-1 text-right tabular-nums text-bone-300">{row.days}</td>
      <td className="border-b border-l border-white/[0.06] px-3 py-1 text-xs tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(row.start)}</td>
      <td className="border-b border-white/[0.06] px-3 py-1 text-xs tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(row.end)}</td>
      {columns.map((col, index) => {
        const value = row.cells[col.date]
        return (
          <td key={col.date}
            className={`border-b border-l border-white/[0.06] px-0 py-1 text-center text-[11px] tabular-nums ${cellTone(col)} ${
              index === todayIndex ? 'shadow-[inset_2px_0_0_0_theme(colors.brass.400)]' : ''
            }`}
            style={{ width: COL, minWidth: COL }}
            title={value ? `${row.label} — day ${value}` : ''}>
            {value != null && (
              <span className={`inline-block w-full py-0.5 font-medium ${
                unassigned ? 'bg-red-500/20 text-red-200' : 'bg-teal-500/[0.18] text-teal-200'
              }`}>
                {value}
              </span>
            )}
          </td>
        )
      })}
    </tr>
  )
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-4 border-t border-white/[0.06] bg-ink-800/60 px-4 py-2.5 text-xs text-bone-500">
      <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded bg-teal-500/[0.18]" /> allocated working day</span>
      <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded bg-red-500/20" /> unallocated (shortage)</span>
      <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded bg-white/[0.02]" /> Sat — White Collar off</span>
      <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded bg-white/[0.035]" /> Sun — everyone off</span>
      <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded bg-teal-500/[0.07] ring-1 ring-inset ring-teal-500/20" /> public holiday</span>
      <span>Cell number = cumulative working day of the project timeline.</span>
    </div>
  )
}
