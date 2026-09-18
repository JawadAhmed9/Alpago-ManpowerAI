import { useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, Clock3, Sun } from 'lucide-react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { Empty, ErrorBox, GlassPanel, Spinner, fadeUp, fmtDate, stagger } from '../components/ui.jsx'

const DAY_NAMES = { 1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun' }

export default function Calendar() {
  const rules = useAsync(() => api.calendarRules(), [])
  const holidays = useAsync(() => api.holidays(), [])
  const [form, setForm] = useState({ holiday_date: '', label: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function add(event) {
    event.preventDefault(); setError(null); setBusy(true)
    try {
      await api.createHoliday(form)
      setForm({ holiday_date: '', label: '' })
      holidays.reload()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  async function remove(id) {
    setError(null)
    try { await api.deleteHoliday(id); holidays.reload() }
    catch (err) { setError(err) }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-brass-400">Working rules</div>
        <h1 className="mt-1 font-display text-2xl font-bold text-bone-50">Calendar &amp; holidays</h1>
        <p className="mt-1 max-w-2xl text-sm text-bone-500">
          The two workforce categories run different weekly patterns. Every public holiday added here
          feeds directly into the scheduling engine — it re-derives working-day math for every project.
        </p>
      </div>

      {rules.loading ? <Spinner /> : (
        <motion.div variants={stagger} initial="hidden" animate="show" className="grid gap-4 md:grid-cols-2">
          {(rules.data || []).map((rule) => (
            <motion.div key={rule.id} variants={fadeUp}>
              <GlassPanel className="p-4">
                <div className="flex items-center gap-2">
                  <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brass-400 to-brass-600 text-ink-950">
                    <Clock3 className="h-4 w-4" />
                  </span>
                  <div className="font-display text-sm font-bold text-bone-50">{rule.category}</div>
                </div>
                <dl className="mt-3 space-y-1.5 text-sm">
                  <Row label="Works">{rule.workdays.split(',').map((d) => DAY_NAMES[Number(d)]).join(', ')}</Row>
                  <Row label="Weekly off">{rule.weekly_off_days.split(',').map((d) => DAY_NAMES[Number(d)]).join(', ')}</Row>
                  <Row label="Standard shift">{rule.standard_shift_hrs} hrs/day</Row>
                  <Row label="Overtime">{rule.overtime_allowed ? 'Allowed' : 'Not applicable'}</Row>
                </dl>
                {rule.notes && <p className="mt-3 border-t border-white/[0.06] pt-2.5 text-xs text-bone-600">{rule.notes}</p>}
              </GlassPanel>
            </motion.div>
          ))}
        </motion.div>
      )}

      <GlassPanel className="p-4">
        <div className="flex items-center gap-2">
          <Sun className="h-4 w-4 text-brass-400" />
          <h2 className="font-display text-sm font-bold text-bone-50">Public holidays</h2>
        </div>
        <p className="mt-1 text-xs text-bone-600">
          Applies to every category on top of the weekly off pattern. Adding one re-plans every project.
        </p>
        <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={add}>
          <div>
            <label className="label">Date</label>
            <input type="date" required className="input" value={form.holiday_date}
              onChange={(e) => setForm({ ...form, holiday_date: e.target.value })} />
          </div>
          <div className="min-w-56 flex-1">
            <label className="label">Label</label>
            <input required className="input" value={form.label} placeholder="UAE National Day"
              onChange={(e) => setForm({ ...form, label: e.target.value })} />
          </div>
          <motion.button whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }} className="btn-primary" disabled={busy}>
            <Plus className="h-4 w-4" /> {busy ? 'Adding…' : 'Add holiday'}
          </motion.button>
        </form>

        <ErrorBox error={error} />

        <div className="mt-4">
          {holidays.loading ? <Spinner /> : !holidays.data?.length ? (
            <Empty>No public holidays configured.</Empty>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
              <table className="w-full">
                <thead className="border-b border-white/[0.06]">
                  <tr><th className="th">Date</th><th className="th">Label</th><th className="th" /></tr>
                </thead>
                <tbody className="divide-y divide-white/[0.05]">
                  {holidays.data.map((holiday) => (
                    <tr key={holiday.id} className="transition-colors hover:bg-white/[0.03]">
                      <td className="td tabular-nums text-bone-300 whitespace-nowrap">{fmtDate(holiday.holiday_date)}</td>
                      <td className="td text-bone-100">{holiday.label}</td>
                      <td className="td text-right">
                        <button className="icon-btn text-red-300" onClick={() => remove(holiday.id)} aria-label="Remove holiday">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </GlassPanel>
    </div>
  )
}

function Row({ label, children }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-bone-600">{label}</span>
      <span className="text-right text-bone-200">{children}</span>
    </div>
  )
}
