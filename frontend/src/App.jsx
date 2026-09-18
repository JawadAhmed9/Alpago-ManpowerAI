import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  LayoutGrid,
  Users,
  CalendarDays,
  ShieldAlert,
  Blocks,
  Hammer,
} from 'lucide-react'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutGrid, end: true },
  { to: '/employees', label: 'Employees', icon: Users },
  { to: '/masters', label: 'Stages & Roles', icon: Blocks },
  { to: '/calendar', label: 'Calendar', icon: CalendarDays },
  { to: '/conflicts', label: 'Conflicts', icon: ShieldAlert },
]

export default function App() {
  const location = useLocation()

  return (
    <div className="relative z-[1] flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 flex-none flex-col gap-1 border-r border-white/[0.06] p-4 lg:flex">
        <div className="mb-6 flex items-center gap-2.5 px-2 pt-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brass-300 to-brass-600 shadow-glow">
            <Hammer className="h-4.5 w-4.5 text-ink-950" strokeWidth={2.4} />
          </div>
          <div>
            <div className="font-display text-[15px] font-bold leading-tight text-bone-50">Alpago</div>
            <div className="text-[11px] leading-tight text-bone-600">Manpower Engine</div>
          </div>
        </div>

        <nav className="flex flex-col gap-1">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className="relative block">
              {({ isActive }) => (
                <div
                  className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive ? 'text-ink-950' : 'text-bone-300 hover:text-bone-50'
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-xl bg-gradient-to-r from-brass-300 to-brass-500"
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                    />
                  )}
                  {!isActive && (
                    <div className="absolute inset-0 rounded-xl bg-white/0 transition-colors group-hover:bg-white/[0.04]" />
                  )}
                  <link.icon className="relative z-[1] h-4 w-4" strokeWidth={2} />
                  <span className="relative z-[1]">{link.label}</span>
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[11px] leading-relaxed text-bone-600">
          Scheduling &amp; allocation run on deterministic rules — the AI layer only
          explains decisions already made.
        </div>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-white/[0.06] bg-ink-950/70 px-5 py-3.5 backdrop-blur-xl lg:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brass-300 to-brass-600">
              <Hammer className="h-3.5 w-3.5 text-ink-950" />
            </div>
            <span className="font-display text-sm font-bold">Alpago</span>
          </div>
          <nav className="flex gap-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  `rounded-lg p-2 ${isActive ? 'bg-brass-500/20 text-brass-300' : 'text-bone-500'}`
                }
              >
                <link.icon className="h-4 w-4" />
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-5 py-6 lg:px-8 lg:py-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
