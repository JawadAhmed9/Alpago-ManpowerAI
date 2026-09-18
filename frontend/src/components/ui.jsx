import { motion, AnimatePresence } from 'framer-motion'
import { createPortal } from 'react-dom'
import { AlertTriangle, Loader2, X } from 'lucide-react'

export function GlassPanel({ children, className = '', strong = false, ...rest }) {
  return (
    <div className={`${strong ? 'glass-strong' : 'glass'} glass-sheen ${className}`} {...rest}>
      {children}
    </div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="flex items-center gap-2.5 p-8 text-sm text-bone-500">
      <Loader2 className="h-4 w-4 animate-spin text-brass-400" />
      {label}
    </div>
  )
}

export function SkeletonBlock({ className = '' }) {
  return <div className={`skeleton ${className}`} />
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl border-red-400/20 bg-red-500/[0.06] p-4 text-sm text-red-200"
    >
      <div className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="h-4 w-4" /> Something went wrong
      </div>
      <div className="mt-1 text-red-300/80">{String(error.message || error)}</div>
      {onRetry && (
        <button className="btn-ghost mt-3" onClick={onRetry}>
          Try again
        </button>
      )}
    </motion.div>
  )
}

export function Empty({ children }) {
  return <div className="p-10 text-center text-sm text-bone-700">{children}</div>
}

const PRIORITY = {
  Urgent: 'bg-red-500/15 text-red-300 ring-1 ring-inset ring-red-500/25',
  High: 'bg-orange-500/15 text-orange-300 ring-1 ring-inset ring-orange-500/25',
  Medium: 'bg-sky-500/15 text-sky-300 ring-1 ring-inset ring-sky-500/25',
  Low: 'bg-white/10 text-bone-300 ring-1 ring-inset ring-white/10',
}
export function PriorityPill({ value }) {
  return <span className={`pill ${PRIORITY[value] || PRIORITY.Low}`}>{value}</span>
}

const SKILL = {
  Senior: 'bg-teal-500/15 text-teal-300 ring-1 ring-inset ring-teal-500/25',
  Mid: 'bg-brass-500/15 text-brass-300 ring-1 ring-inset ring-brass-500/25',
  Junior: 'bg-white/10 text-bone-300 ring-1 ring-inset ring-white/10',
}
export function SkillPill({ value }) {
  return <span className={`pill ${SKILL[value] || SKILL.Junior}`}>{value}</span>
}

const STATUS = {
  Active: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/25',
  Inactive: 'bg-white/10 text-bone-500 ring-1 ring-inset ring-white/10',
}
export function StatusPill({ value }) {
  return <span className={`pill ${STATUS[value] || STATUS.Inactive}`}>{value}</span>
}

export function Stat({ label, value, hint, tone = 'default', icon: Icon }) {
  const tones = {
    default: 'text-bone-50',
    warn: 'text-amber-300',
    bad: 'text-red-300',
    good: 'text-emerald-300',
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="glass glass-sheen rounded-2xl p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-bone-500">{label}</div>
        {Icon && <Icon className="h-3.5 w-3.5 text-bone-700" strokeWidth={2} />}
      </div>
      <div className={`mt-1.5 text-[26px] font-display font-bold tabular-nums leading-none ${tones[tone]}`}>
        {value}
      </div>
      {hint && <div className="mt-1.5 text-xs text-bone-500">{hint}</div>}
    </motion.div>
  )
}

export function Modal({ open, onClose, title, children, width = 'max-w-lg' }) {
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            className={`glass-strong relative w-full ${width} max-h-[86vh] overflow-y-auto rounded-2xl p-5`}
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-bone-50">{title}</h3>
              <button className="icon-btn" onClick={onClose} aria-label="Close">
                <X className="h-4 w-4" />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

export function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtDateShort(iso) {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

export const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
}
export const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] } },
}
