import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, Pencil, Check, X, GitBranch } from 'lucide-react'
import { api } from '../api.js'
import { ErrorBox, GlassPanel, fadeUp, stagger } from './ui.jsx'

/**
 * Fixes the "no UI for editing a stage's tasks" gap. Backed 1:1 by the Task CRUD
 * endpoints — duration, designation, name, and sequence are all editable; task
 * dependencies (predecessors + lag) can only be set at creation, because that's
 * what the API currently supports, so we don't pretend otherwise in the UI.
 */
export default function TaskEditor({ project, designations, onChanged }) {
  const [error, setError] = useState(null)
  const designationById = useMemo(
    () => Object.fromEntries((designations || []).map((d) => [d.id, d])),
    [designations],
  )

  async function reload() {
    onChanged()
  }

  return (
    <div className="space-y-5">
      <ErrorBox error={error} onRetry={() => setError(null)} />
      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-4">
        {project.stages.map((stage) => (
          <motion.div key={stage.id} variants={fadeUp}>
            <StageTaskGroup
              project={project}
              stage={stage}
              designations={designations}
              designationById={designationById}
              onError={setError}
              onChanged={reload}
            />
          </motion.div>
        ))}
      </motion.div>
    </div>
  )
}

function StageTaskGroup({ project, stage, designations, designationById, onError, onChanged }) {
  const [adding, setAdding] = useState(false)
  const budgetUsed = stage.tasks.reduce((sum, t) => sum + t.duration_working_days, 0)
  const overBudget = budgetUsed !== stage.man_days_budgeted

  return (
    <GlassPanel className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-bone-50">
            Stage {stage.sequence_order}: {stage.stage.name}
          </div>
          <div className={`mt-0.5 text-xs ${overBudget ? 'font-semibold text-amber-300' : 'text-bone-600'}`}>
            {budgetUsed} / {stage.man_days_budgeted} man-days assigned to tasks
            {overBudget && ' — re-run allocation only works once these match'}
          </div>
        </div>
        <button className="btn-ghost text-xs" onClick={() => setAdding((v) => !v)}>
          {adding ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {adding ? 'Cancel' : 'Add task'}
        </button>
      </div>

      <div className="space-y-2">
        {stage.tasks.map((task) => (
          <TaskRow
            key={task.id}
            project={project}
            task={task}
            designations={designations}
            designationName={designationById[task.designation_id]?.name}
            onError={onError}
            onChanged={onChanged}
          />
        ))}
        {!stage.tasks.length && !adding && (
          <div className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-center text-xs text-bone-600">
            No tasks yet — add one to break this stage down.
          </div>
        )}
      </div>

      {adding && (
        <NewTaskForm
          project={project}
          stage={stage}
          designations={designations}
          onDone={() => { setAdding(false); onChanged() }}
          onError={onError}
        />
      )}
    </GlassPanel>
  )
}

function TaskRow({ project, task, designations, designationName, onError, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    name: task.name,
    designation_id: task.designation_id,
    duration_working_days: task.duration_working_days,
  })
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true); onError(null)
    try {
      await api.updateTask(project.id, task.id, {
        name: form.name,
        designation_id: Number(form.designation_id),
        duration_working_days: Number(form.duration_working_days),
      })
      setEditing(false)
      onChanged()
    } catch (err) { onError(err) } finally { setBusy(false) }
  }

  async function remove() {
    onError(null)
    try { await api.deleteTask(project.id, task.id); onChanged() }
    catch (err) { onError(err) }
  }

  if (editing) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-brass-500/30 bg-brass-500/[0.06] p-2.5">
        <input className="input flex-1 basis-48" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <select className="input basis-44" value={form.designation_id} onChange={(e) => setForm({ ...form, designation_id: e.target.value })}>
          {designations.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <input type="number" min="1" className="input w-24" value={form.duration_working_days}
          onChange={(e) => setForm({ ...form, duration_working_days: e.target.value })} />
        <button className="icon-btn text-emerald-300" disabled={busy} onClick={save}><Check className="h-4 w-4" /></button>
        <button className="icon-btn" onClick={() => setEditing(false)}><X className="h-4 w-4" /></button>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 transition hover:bg-white/[0.04]">
      <div className="min-w-0">
        <div className="truncate text-sm text-bone-100">{task.name}</div>
        <div className="text-xs text-bone-600">{designationName || '—'} · {task.duration_working_days} man-day(s)</div>
      </div>
      <div className="flex flex-none gap-1">
        <button className="icon-btn" onClick={() => setEditing(true)} aria-label="Edit task"><Pencil className="h-3.5 w-3.5" /></button>
        <button className="icon-btn text-red-300" onClick={remove} aria-label="Delete task"><Trash2 className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  )
}

function NewTaskForm({ project, stage, designations, onDone, onError }) {
  const [form, setForm] = useState({
    name: '', designation_id: designations[0]?.id ?? '', duration_working_days: 1,
    predecessor_ids: [], lag_days: 0,
  })
  const [busy, setBusy] = useState(false)

  const otherTasks = project.stages.flatMap((s) => s.tasks.map((t) => ({ ...t, stageName: s.stage.name })))

  function toggle(id) {
    setForm((f) => ({
      ...f,
      predecessor_ids: f.predecessor_ids.includes(id)
        ? f.predecessor_ids.filter((x) => x !== id)
        : [...f.predecessor_ids, id],
    }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true); onError(null)
    try {
      await api.createTask(project.id, stage.id, {
        name: form.name,
        designation_id: Number(form.designation_id),
        duration_working_days: Number(form.duration_working_days),
        sequence_order: stage.tasks.length,
        predecessor_ids: form.predecessor_ids,
        lag_days: Number(form.lag_days),
      })
      onDone()
    } catch (err) { onError(err) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-lg border border-white/10 bg-black/20 p-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <input required placeholder="Task name" className="input sm:col-span-3"
          value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <select className="input" value={form.designation_id} onChange={(e) => setForm({ ...form, designation_id: e.target.value })}>
          {designations.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <input type="number" min="1" placeholder="Duration (days)" className="input"
          value={form.duration_working_days} onChange={(e) => setForm({ ...form, duration_working_days: e.target.value })} />
        <input type="number" placeholder="Lag (days, -1 = overlap)" className="input"
          value={form.lag_days} onChange={(e) => setForm({ ...form, lag_days: e.target.value })} />
      </div>

      {otherTasks.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-bone-500">
            <GitBranch className="h-3 w-3" /> Waits on (optional)
          </div>
          <div className="flex flex-wrap gap-1.5">
            {otherTasks.map((t) => (
              <button type="button" key={t.id} onClick={() => toggle(t.id)}
                className={`rounded-full border px-2.5 py-1 text-xs transition ${
                  form.predecessor_ids.includes(t.id)
                    ? 'border-brass-500/50 bg-brass-500/15 text-brass-300'
                    : 'border-white/10 bg-white/[0.02] text-bone-500 hover:text-bone-200'
                }`}>
                {t.name} <span className="text-bone-700">· {t.stageName}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button className="btn-primary text-xs" disabled={busy}>{busy ? 'Adding…' : 'Add task'}</button>
      </div>
    </form>
  )
}
