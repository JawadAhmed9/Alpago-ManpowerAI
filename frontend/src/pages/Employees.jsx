import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, Pencil, Trash2, Clock } from 'lucide-react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { Empty, ErrorBox, GlassPanel, Modal, SkillPill, Spinner, StatusPill, fadeUp, fmtDate, stagger } from '../components/ui.jsx'

export default function Employees() {
  const [filters, setFilters] = useState({ search: '', designation_id: '', employee_status: '' })
  const designations = useAsync(() => api.designations(), [])
  const employees = useAsync(
    () => api.employees(filters),
    [filters.search, filters.designation_id, filters.employee_status],
  )
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState(null)
  const [workload, setWorkload] = useState(null)

  const byId = useMemo(() => Object.fromEntries((designations.data || []).map((d) => [d.id, d])), [designations.data])

  async function remove(employee) {
    setError(null)
    try { await api.deleteEmployee(employee.id); employees.reload() }
    catch (err) { setError(err) }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-brass-400">Workforce</div>
          <h1 className="mt-1 font-display text-2xl font-bold text-bone-50">Employees</h1>
        </div>
        <motion.button whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }} className="btn-primary" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> Add employee
        </motion.button>
      </div>

      <GlassPanel className="grid gap-3 p-3.5 md:grid-cols-4">
        <div>
          <label className="label">Search</label>
          <input className="input" placeholder="name or code" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
        </div>
        <div>
          <label className="label">Designation</label>
          <select className="input" value={filters.designation_id} onChange={(e) => setFilters({ ...filters, designation_id: e.target.value })}>
            <option value="">All</option>
            {(designations.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Status</label>
          <select className="input" value={filters.employee_status} onChange={(e) => setFilters({ ...filters, employee_status: e.target.value })}>
            <option value="">All</option><option>Active</option><option>Inactive</option>
          </select>
        </div>
        <div className="flex items-end text-sm text-bone-600">{employees.data ? `${employees.data.length} shown` : ''}</div>
      </GlassPanel>

      <ErrorBox error={error || employees.error} onRetry={employees.reload} />

      {employees.loading ? <Spinner /> : !employees.data?.length ? (
        <Empty>No employees match those filters.</Empty>
      ) : (
        <GlassPanel className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-white/[0.06]">
              <tr>
                <th className="th">Code</th><th className="th">Name</th><th className="th">Designation</th>
                <th className="th">Category</th><th className="th">Skill</th><th className="th">Joined</th>
                <th className="th">Status</th><th className="th" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {employees.data.map((employee) => (
                <tr key={employee.id} className="transition-colors hover:bg-white/[0.03]">
                  <td className="td font-mono text-xs text-bone-500">{employee.employee_code}</td>
                  <td className="td font-medium text-bone-100">{employee.name}</td>
                  <td className="td text-bone-300">{byId[employee.designation_id]?.name || employee.designation?.name}</td>
                  <td className="td text-bone-500">{employee.designation?.category}</td>
                  <td className="td"><SkillPill value={employee.skill_level} /></td>
                  <td className="td tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(employee.date_of_joining)}</td>
                  <td className="td"><StatusPill value={employee.status} /></td>
                  <td className="td">
                    <div className="flex justify-end gap-1">
                      <button className="icon-btn" onClick={async () => setWorkload(await api.workload(employee.id))} aria-label="Workload"><Clock className="h-3.5 w-3.5" /></button>
                      <button className="icon-btn" onClick={() => setEditing(employee)} aria-label="Edit"><Pencil className="h-3.5 w-3.5" /></button>
                      <button className="icon-btn text-red-300" onClick={() => remove(employee)} aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassPanel>
      )}

      <Modal open={creating} onClose={() => setCreating(false)} title="Add employee">
        <EmployeeForm designations={designations.data || []} onDone={() => { setCreating(false); employees.reload() }} />
      </Modal>

      <Modal open={!!editing} onClose={() => setEditing(null)} title={`Edit ${editing?.name ?? ''}`}>
        {editing && (
          <EmployeeForm
            designations={designations.data || []}
            employee={editing}
            onDone={() => { setEditing(null); employees.reload() }}
          />
        )}
      </Modal>

      <Modal open={!!workload} onClose={() => setWorkload(null)} title="Workload" width="max-w-2xl">
        {workload && (
          <div>
            <div className="mb-3 text-sm text-bone-400">
              <span className="font-display text-lg font-bold text-bone-50">{workload.total_allocated_days}</span> allocated day(s)
            </div>
            {!workload.allocations.length ? (
              <div className="text-sm text-bone-600">No allocations.</div>
            ) : (
              <table className="w-full">
                <thead><tr>
                  <th className="th">Project</th><th className="th">Task</th>
                  <th className="th">Start</th><th className="th">End</th><th className="th text-right">Days</th>
                </tr></thead>
                <tbody className="divide-y divide-white/[0.05]">
                  {workload.allocations.map((a) => (
                    <tr key={a.allocation_id}>
                      <td className="td font-mono text-xs text-bone-500">{a.project_code}</td>
                      <td className="td text-bone-200">{a.task}</td>
                      <td className="td tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(a.start)}</td>
                      <td className="td tabular-nums text-bone-500 whitespace-nowrap">{fmtDate(a.end)}</td>
                      <td className="td text-right tabular-nums">{a.working_days}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}

function EmployeeForm({ designations, employee, onDone }) {
  const isEdit = !!employee
  const [form, setForm] = useState({
    employee_code: employee?.employee_code ?? '',
    name: employee?.name ?? '',
    designation_id: employee?.designation_id ?? designations[0]?.id ?? '',
    skill_level: employee?.skill_level ?? 'Mid',
    date_of_joining: employee?.date_of_joining ?? new Date().toISOString().slice(0, 10),
    status: employee?.status ?? 'Active',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(null)
    try {
      if (isEdit) {
        await api.updateEmployee(employee.id, {
          name: form.name,
          designation_id: Number(form.designation_id),
          skill_level: form.skill_level,
          date_of_joining: form.date_of_joining,
          status: form.status,
        })
      } else {
        await api.createEmployee({ ...form, designation_id: Number(form.designation_id) })
      }
      onDone()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <form className="space-y-3" onSubmit={submit}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label">Code</label>
          <input required disabled={isEdit} className="input disabled:opacity-50" value={form.employee_code} onChange={set('employee_code')} placeholder="EMP057" />
        </div>
        <div><label className="label">Name</label><input required className="input" value={form.name} onChange={set('name')} /></div>
        <div className="sm:col-span-2">
          <label className="label">Designation</label>
          <select required className="input" value={form.designation_id} onChange={set('designation_id')}>
            {designations.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Skill level</label>
          <select className="input" value={form.skill_level} onChange={set('skill_level')}>
            {['Junior', 'Mid', 'Senior'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div><label className="label">Date of joining</label><input type="date" required className="input" value={form.date_of_joining} onChange={set('date_of_joining')} /></div>
        {isEdit && (
          <div className="sm:col-span-2">
            <label className="label">Status</label>
            <select className="input" value={form.status} onChange={set('status')}>
              <option>Active</option><option>Inactive</option>
            </select>
          </div>
        )}
      </div>
      <ErrorBox error={error} />
      <button className="btn-primary w-full" disabled={busy}>{busy ? 'Saving…' : isEdit ? 'Save changes' : 'Add employee'}</button>
    </form>
  )
}
