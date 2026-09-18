import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, Pencil, Check, X, Link2, Blocks } from 'lucide-react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { ErrorBox, GlassPanel, Modal, Spinner, fadeUp, stagger } from '../components/ui.jsx'

/**
 * Closes the "no screen for stages/designations" gap: create stages, create
 * designations, edit either, and link which designations belong to which stage.
 * Deleting stages/designations is intentionally left out — they're referenced
 * everywhere (employees, tasks, allocations) and a bad delete would orphan data;
 * that's a decision worth a human, not a button.
 */
export default function Masters() {
  const stages = useAsync(() => api.stages(), [])
  const designations = useAsync(() => api.designations(), [])
  const [view, setView] = useState('stages')
  const [error, setError] = useState(null)

  function reload() { stages.reload(); designations.reload() }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-brass-400">Master data</div>
        <h1 className="mt-1 font-display text-2xl font-bold text-bone-50">Stages &amp; roles</h1>
        <p className="mt-1 text-sm text-bone-500">
          The production stages, the roles allowed in each, and which category calendar each role follows.
        </p>
      </div>

      <ErrorBox error={error} onRetry={() => setError(null)} />

      <div className="flex gap-1 border-b border-white/[0.06]">
        {[['stages', 'Stages'], ['designations', 'Designations']].map(([key, label]) => (
          <button key={key} onClick={() => setView(key)}
            className={`relative px-3 py-2.5 text-sm font-medium transition-colors ${view === key ? 'text-bone-50' : 'text-bone-600 hover:text-bone-300'}`}>
            {label}
            {view === key && <motion.div layoutId="masters-tab" className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brass-400" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
          </button>
        ))}
      </div>

      {view === 'stages' ? (
        <StagesView stages={stages} designations={designations} onError={setError} onChanged={reload} />
      ) : (
        <DesignationsView designations={designations} onError={setError} onChanged={reload} />
      )}
    </div>
  )
}

function StagesView({ stages, designations, onError, onChanged }) {
  const [adding, setAdding] = useState(false)
  const [linkingStage, setLinkingStage] = useState(null)

  if (stages.loading) return <Spinner />
  if (stages.error) return <ErrorBox error={stages.error} onRetry={stages.reload} />

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button className="btn-ghost text-xs" onClick={() => setAdding((v) => !v)}>
          {adding ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {adding ? 'Cancel' : 'New stage'}
        </button>
      </div>

      {adding && (
        <NewStageForm nextSeq={(stages.data?.length || 0) + 1} onDone={() => { setAdding(false); onChanged() }} onError={onError} />
      )}

      <motion.div variants={stagger} initial="hidden" animate="show" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(stages.data || []).map((stage) => (
          <motion.div key={stage.id} variants={fadeUp}>
            <GlassPanel className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[11px] text-bone-600">Stage {stage.sequence_order}</div>
                  <div className="font-display text-base font-semibold text-bone-50">{stage.name}</div>
                </div>
                <Blocks className="h-4 w-4 text-bone-700" />
              </div>
              <button className="btn-ghost mt-3 w-full text-xs" onClick={() => setLinkingStage(stage)}>
                <Link2 className="h-3.5 w-3.5" /> Manage roles
              </button>
            </GlassPanel>
          </motion.div>
        ))}
      </motion.div>

      <Modal open={!!linkingStage} onClose={() => setLinkingStage(null)} title={`Roles in ${linkingStage?.name ?? ''}`} width="max-w-xl">
        {linkingStage && (
          <StageDesignationLinker stage={linkingStage} allDesignations={designations.data || []} onError={onError} />
        )}
      </Modal>
    </div>
  )
}

function NewStageForm({ nextSeq, onDone, onError }) {
  const [form, setForm] = useState({ name: '', sequence_order: nextSeq })
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault(); setBusy(true); onError(null)
    try {
      await api.createStage({ name: form.name, sequence_order: Number(form.sequence_order) })
      onDone()
    } catch (err) { onError(err) } finally { setBusy(false) }
  }

  return (
    <GlassPanel strong className="flex flex-wrap items-end gap-3 p-4">
      <form onSubmit={submit} className="flex flex-1 flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1"><label className="label">Stage name</label>
          <input required className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Installation" /></div>
        <div className="w-32"><label className="label">Order</label>
          <input type="number" min="1" required className="input" value={form.sequence_order} onChange={(e) => setForm({ ...form, sequence_order: e.target.value })} /></div>
        <button className="btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create stage'}</button>
      </form>
    </GlassPanel>
  )
}

function StageDesignationLinker({ stage, allDesignations, onError }) {
  const linked = useAsync(() => api.stageDesignations(stage.id), [stage.id])
  const [busyId, setBusyId] = useState(null)

  const linkedIds = new Set((linked.data || []).map((d) => d.id));

  async function link(designationId) {
    setBusyId(designationId); onError(null)
    try { await api.linkDesignation(stage.id, designationId); linked.reload() }
    catch (err) { onError(err) } finally { setBusyId(null) }
  }

  if (linked.loading) return <Spinner />

  return (
    <div className="space-y-3">
      <div>
        <div className="label">Already in this stage</div>
        {!linked.data?.length ? (
          <div className="text-sm text-bone-600">No roles linked yet.</div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {linked.data.map((d) => (
              <span key={d.id} className="pill bg-teal-500/15 text-teal-300 ring-1 ring-inset ring-teal-500/25">{d.name}</span>
            ))}
          </div>
        )}
      </div>
      <div>
        <div className="label">Add a role</div>
        <div className="flex flex-wrap gap-1.5">
          {allDesignations.filter((d) => !linkedIds.has(d.id)).map((d) => (
            <button key={d.id} disabled={busyId === d.id} onClick={() => link(d.id)}
              className="rounded-full border border-white/10 bg-white/[0.02] px-2.5 py-1 text-xs text-bone-400 transition hover:border-brass-500/40 hover:text-brass-300 disabled:opacity-40">
              <Plus className="mr-1 inline h-3 w-3" />{d.name}
            </button>
          ))}
          {allDesignations.every((d) => linkedIds.has(d.id)) && (
            <span className="text-xs text-bone-700">Every designation is already linked.</span>
          )}
        </div>
      </div>
    </div>
  )
}

function DesignationsView({ designations, onError, onChanged }) {
  const [adding, setAdding] = useState(false)

  if (designations.loading) return <Spinner />
  if (designations.error) return <ErrorBox error={designations.error} onRetry={designations.reload} />

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button className="btn-ghost text-xs" onClick={() => setAdding((v) => !v)}>
          {adding ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {adding ? 'Cancel' : 'New designation'}
        </button>
      </div>

      {adding && <NewDesignationForm onDone={() => { setAdding(false); onChanged() }} onError={onError} />}

      <GlassPanel className="overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-white/[0.06]">
            <tr>
              <th className="th">Name</th><th className="th">Category</th>
              <th className="th text-right">Shift (hrs)</th><th className="th">Overtime</th>
              <th className="th">Allocatable</th><th className="th" />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05]">
            {(designations.data || []).map((d) => (
              <DesignationRow key={d.id} designation={d} onError={onError} onChanged={onChanged} />
            ))}
          </tbody>
        </table>
      </GlassPanel>
    </div>
  )
}

function DesignationRow({ designation, onError, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    category: designation.category,
    standard_shift_hrs: designation.standard_shift_hrs,
    overtime_applicable: designation.overtime_applicable,
    allocatable: designation.allocatable,
  })
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true); onError(null)
    try {
      await api.updateDesignation(designation.id, {
        category: form.category,
        standard_shift_hrs: Number(form.standard_shift_hrs),
        overtime_applicable: form.overtime_applicable,
        allocatable: form.allocatable,
      })
      setEditing(false); onChanged()
    } catch (err) { onError(err) } finally { setBusy(false) }
  }

  if (editing) {
    return (
      <tr className="bg-brass-500/[0.05]">
        <td className="td font-medium text-bone-100">{designation.name}</td>
        <td className="td">
          <select className="input py-1 text-xs" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            <option>White Collar</option><option>Blue Collar</option>
          </select>
        </td>
        <td className="td text-right">
          <input type="number" step="0.5" className="input w-16 py-1 text-right text-xs" value={form.standard_shift_hrs}
            onChange={(e) => setForm({ ...form, standard_shift_hrs: e.target.value })} />
        </td>
        <td className="td">
          <input type="checkbox" checked={form.overtime_applicable} onChange={(e) => setForm({ ...form, overtime_applicable: e.target.checked })} />
        </td>
        <td className="td">
          <input type="checkbox" checked={form.allocatable} onChange={(e) => setForm({ ...form, allocatable: e.target.checked })} />
        </td>
        <td className="td">
          <div className="flex justify-end gap-1">
            <button className="icon-btn text-emerald-300" disabled={busy} onClick={save}><Check className="h-3.5 w-3.5" /></button>
            <button className="icon-btn" onClick={() => setEditing(false)}><X className="h-3.5 w-3.5" /></button>
          </div>
        </td>
      </tr>
    )
  }

  return (
    <tr className="transition-colors hover:bg-white/[0.03]">
      <td className="td font-medium text-bone-100">{designation.name}</td>
      <td className="td text-bone-400">{designation.category}</td>
      <td className="td text-right tabular-nums text-bone-400">{designation.standard_shift_hrs}</td>
      <td className="td text-bone-500">{designation.overtime_applicable ? 'Yes' : 'No'}</td>
      <td className="td text-bone-500">{designation.allocatable ? 'Yes' : 'Manager-only'}</td>
      <td className="td text-right"><button className="icon-btn" onClick={() => setEditing(true)} aria-label="Edit"><Pencil className="h-3.5 w-3.5" /></button></td>
    </tr>
  )
}

function NewDesignationForm({ onDone, onError }) {
  const [form, setForm] = useState({ name: '', category: 'White Collar', standard_shift_hrs: 8, overtime_applicable: false, allocatable: true })
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault(); setBusy(true); onError(null)
    try {
      await api.createDesignation({ ...form, standard_shift_hrs: Number(form.standard_shift_hrs) })
      onDone()
    } catch (err) { onError(err) } finally { setBusy(false) }
  }

  return (
    <GlassPanel strong className="p-4">
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-5">
        <input required placeholder="Role name" className="input sm:col-span-2" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
          <option>White Collar</option><option>Blue Collar</option>
        </select>
        <input type="number" step="0.5" className="input" value={form.standard_shift_hrs} onChange={(e) => setForm({ ...form, standard_shift_hrs: e.target.value })} placeholder="Shift hrs" />
        <button className="btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create'}</button>
        <label className="flex items-center gap-2 text-xs text-bone-400 sm:col-span-2">
          <input type="checkbox" checked={form.overtime_applicable} onChange={(e) => setForm({ ...form, overtime_applicable: e.target.checked })} /> Overtime applicable
        </label>
        <label className="flex items-center gap-2 text-xs text-bone-400 sm:col-span-2">
          <input type="checkbox" checked={form.allocatable} onChange={(e) => setForm({ ...form, allocatable: e.target.checked })} /> Allocatable production role
        </label>
      </form>
    </GlassPanel>
  )
}
