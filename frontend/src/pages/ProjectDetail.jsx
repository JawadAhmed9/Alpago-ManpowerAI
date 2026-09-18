import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft, Sparkles, PlayCircle, TriangleAlert, LayoutList,
  ListTree, Bot, Loader2, CheckCircle2,
} from 'lucide-react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import GanttMatrix from '../components/GanttMatrix.jsx'
import TaskEditor from '../components/TaskEditor.jsx'
import { ErrorBox, GlassPanel, PriorityPill, Spinner, Stat, fmtDate } from '../components/ui.jsx'

const TABS = [
  { key: 'gantt', label: 'Manpower plan', icon: LayoutList },
  { key: 'stages', label: 'Stage breakdown', icon: ListTree },
  { key: 'tasks', label: 'Tasks', icon: ListTree },
  { key: 'shortages', label: 'Shortages', icon: TriangleAlert },
  { key: 'ai', label: 'AI insights', icon: Bot },
]

export default function ProjectDetail() {
  const { id } = useParams()
  const gantt = useAsync(() => api.gantt(id), [id])
  const detail = useAsync(() => api.project(id), [id])
  const designations = useAsync(() => api.designations(), [])
  const insights = useAsync(() => api.readInsights(id), [id])
  const aiStatus = useAsync(() => api.aiStatus(), [])
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('gantt')

  function reloadAll() {
    gantt.reload(); detail.reload()
  }

  async function allocate() {
    setBusy('allocate'); setError(null)
    try { await api.allocate(id); reloadAll(); insights.reload() }
    catch (err) { setError(err) } finally { setBusy(null) }
  }

  async function generate() {
    setBusy('ai'); setError(null)
    try { insights.setData(await api.generateInsights(id, true)) }
    catch (err) { setError(err) } finally { setBusy(null) }
  }

  if (gantt.loading) return <Spinner label="Building the plan…" />
  if (gantt.error) return <ErrorBox error={gantt.error} onRetry={gantt.reload} />

  const { project, summary, stage_breakdown: stages, warnings, rows } = gantt.data
  const shortageRows = rows.filter((r) => r.shortage)
  const coverage = summary.allocated_tasks + summary.unallocated_tasks
    ? Math.round((summary.allocated_tasks / (summary.allocated_tasks + summary.unallocated_tasks)) * 100)
    : 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/" className="inline-flex items-center gap-1 text-xs text-bone-600 hover:text-bone-300">
            <ArrowLeft className="h-3.5 w-3.5" /> All projects
          </Link>
          <h1 className="mt-1.5 font-display text-2xl font-bold text-bone-50">
            <span className="mr-2 font-mono text-base font-normal text-bone-600">{project.code}</span>
            {project.name}
          </h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-3 text-sm text-bone-500">
            <PriorityPill value={project.priority} />
            <span>{project.client || '—'}</span>
            <span>{project.location || '—'}</span>
            <span>PM: {project.project_manager || '—'}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <motion.button whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }} className="btn-ghost" onClick={generate} disabled={busy === 'ai'}>
            {busy === 'ai' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Generate AI Insights
          </motion.button>
          <motion.button whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }} className="btn-primary" onClick={allocate} disabled={busy === 'allocate'}>
            {busy === 'allocate' ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            Run allocation
          </motion.button>
        </div>
      </div>

      <ErrorBox error={error} />

      {warnings?.length > 0 && (
        <GlassPanel className="border-amber-400/20 bg-amber-500/[0.06] p-3.5 text-sm text-amber-200">
          <div className="flex items-center gap-2 font-semibold"><TriangleAlert className="h-4 w-4" /> Budget warnings</div>
          <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-amber-200/80">
            {warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </GlassPanel>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Stat label="Total man-days" value={summary.total_man_days} hint="sum of each employee's own days" />
        <Stat label="Actual working days" value={summary.actual_working_days} hint="cumulative project timeline" />
        <Stat label="Calendar span" value={`${summary.calendar_span_days} d`} />
        <Stat label="Start" value={fmtDate(summary.project_start_date)} />
        <Stat label="Expected completion" value={fmtDate(summary.expected_completion_date)} />
        <Stat
          label="Coverage"
          value={`${coverage}%`}
          tone={summary.shortages ? 'warn' : 'good'}
          hint={`${summary.allocated_tasks} of ${summary.allocated_tasks + summary.unallocated_tasks} tasks allocated`}
        />
      </div>

      <div className="relative flex gap-1 overflow-x-auto border-b border-white/[0.06]">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`relative flex items-center gap-1.5 whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors ${
              tab === key ? 'text-bone-50' : 'text-bone-600 hover:text-bone-300'
            }`}>
            <Icon className="h-3.5 w-3.5" />
            {label}
            {key === 'shortages' && shortageRows.length > 0 && (
              <span className="ml-0.5 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-red-300">{shortageRows.length}</span>
            )}
            {tab === key && (
              <motion.div layoutId="tab-underline" className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brass-400"
                transition={{ type: 'spring', stiffness: 420, damping: 34 }} />
            )}
          </button>
        ))}
      </div>

      <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
        {tab === 'gantt' && <GanttMatrix gantt={gantt.data} />}

        {tab === 'stages' && (
          <GlassPanel className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-white/[0.06]">
                  <tr>
                    <th className="th">#</th><th className="th">Stage</th>
                    <th className="th text-right">Budgeted man-days</th>
                    <th className="th text-right">Planned man-days</th>
                    <th className="th">Start</th><th className="th">End</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.05]">
                  {stages.map((s) => (
                    <tr key={s.stage}>
                      <td className="td text-bone-600">{s.sequence}</td>
                      <td className="td font-medium text-bone-100">{s.stage}</td>
                      <td className="td text-right tabular-nums">{s.man_days_budgeted}</td>
                      <td className={`td text-right tabular-nums ${s.man_days_planned !== s.man_days_budgeted ? 'font-semibold text-amber-300' : ''}`}>
                        {s.man_days_planned}
                      </td>
                      <td className="td tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(s.start)}</td>
                      <td className="td tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(s.end)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassPanel>
        )}

        {tab === 'tasks' && (
          detail.loading || designations.loading ? <Spinner label="Loading tasks…" /> :
          detail.error ? <ErrorBox error={detail.error} onRetry={detail.reload} /> :
          <TaskEditor project={detail.data} designations={designations.data || []} onChanged={reloadAll} />
        )}

        {tab === 'shortages' && (
          <GlassPanel className="p-4">
            {shortageRows.length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-emerald-300">
                <CheckCircle2 className="h-4 w-4" /> No shortages — every task has an eligible, available employee.
              </div>
            ) : (
              <ul className="space-y-3">
                {shortageRows.map((row) => (
                  <li key={row.task_id} className="rounded-xl border border-red-400/20 bg-red-500/[0.06] p-3.5">
                    <div className="text-sm font-semibold text-red-200">
                      {row.label} <span className="font-normal text-red-300/70">· {row.designation}</span>
                    </div>
                    <div className="mt-0.5 text-xs text-red-300/70">{fmtDate(row.start)} → {fmtDate(row.end)}</div>
                    <div className="mt-1.5 text-sm text-red-200/90">{row.shortage.reason}</div>
                  </li>
                ))}
              </ul>
            )}
          </GlassPanel>
        )}

        {tab === 'ai' && (
          <GlassPanel className="p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-bone-600">
              <span>
                Provider: {aiStatus.data?.provider ?? '—'} · model {aiStatus.data?.model ?? '—'} ·{' '}
                {aiStatus.data?.configured ? 'configured' : 'not configured'}
              </span>
              <span>· generated on demand and cached; page loads never call the provider.</span>
            </div>
            {insights.data?.note && (
              <div className="mb-3 rounded-lg border border-amber-400/20 bg-amber-500/[0.06] p-2.5 text-sm text-amber-200">
                {insights.data.note}
              </div>
            )}
            {!insights.data?.insights?.length ? (
              <div className="text-sm text-bone-600">Nothing generated yet — use "Generate AI Insights".</div>
            ) : (
              <ul className="space-y-2">
                {insights.data.insights.map((insight) => (
                  <li key={insight.id} className="flex gap-3 border-b border-white/[0.05] pb-2.5 text-sm last:border-0">
                    <span className={`pill h-fit shrink-0 ${
                      insight.related_type === 'shortage' ? 'bg-red-500/15 text-red-300' : 'bg-teal-500/15 text-teal-300'
                    }`}>{insight.related_type}</span>
                    <span className="text-bone-200">{insight.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </GlassPanel>
        )}
      </motion.div>
    </div>
  )
}
