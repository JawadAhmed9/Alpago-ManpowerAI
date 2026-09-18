import { motion } from 'framer-motion'
import { ShieldCheck, ShieldAlert } from 'lucide-react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { ErrorBox, GlassPanel, Spinner, fadeUp, fmtDate, stagger } from '../components/ui.jsx'

export default function Conflicts() {
  const conflicts = useAsync(() => api.conflicts(), [])

  return (
    <div className="space-y-6">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-brass-400">Integrity check</div>
        <h1 className="mt-1 font-display text-2xl font-bold text-bone-50">Allocation conflicts</h1>
        <p className="mt-1 max-w-2xl text-sm text-bone-500">
          One employee can never hold two overlapping allocations — the allocator enforces this at
          assignment time. This view exists to catch imported or legacy data that violates it.
        </p>
      </div>

      <ErrorBox error={conflicts.error} onRetry={conflicts.reload} />

      {conflicts.loading ? <Spinner /> : !conflicts.data?.length ? (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <GlassPanel className="flex items-center gap-3 border-emerald-400/20 bg-emerald-500/[0.06] p-4 text-sm text-emerald-200">
            <ShieldCheck className="h-5 w-5 shrink-0" />
            No double-bookings anywhere in the system.
          </GlassPanel>
        </motion.div>
      ) : (
        <GlassPanel className="overflow-hidden">
          <div className="flex items-center gap-2 border-b border-red-400/20 bg-red-500/[0.06] px-4 py-2.5 text-sm font-medium text-red-200">
            <ShieldAlert className="h-4 w-4" /> {conflicts.data.length} conflict(s) found
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-white/[0.06]">
                <tr>
                  <th className="th">Employee</th><th className="th">Allocation A</th>
                  <th className="th">Allocation B</th><th className="th">Overlap</th>
                </tr>
              </thead>
              <motion.tbody variants={stagger} initial="hidden" animate="show" className="divide-y divide-white/[0.05]">
                {conflicts.data.map((conflict, index) => (
                  <motion.tr key={index} variants={fadeUp} className="bg-red-500/[0.03] hover:bg-red-500/[0.06]">
                    <td className="td font-medium text-bone-100">
                      {conflict.employee_name}
                      <span className="ml-1.5 font-mono text-xs text-bone-600">{conflict.employee_code}</span>
                    </td>
                    <td className="td text-sm text-bone-300">{conflict.left}</td>
                    <td className="td text-sm text-bone-300">{conflict.right}</td>
                    <td className="td tabular-nums text-sm text-red-300">
                      {fmtDate(conflict.overlap_from)} → {fmtDate(conflict.overlap_to)}
                    </td>
                  </motion.tr>
                ))}
              </motion.tbody>
            </table>
          </div>
        </GlassPanel>
      )}
    </div>
  )
}
