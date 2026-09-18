import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { FolderKanban, Users, Link2, TriangleAlert, Plus, ArrowUpRight, X } from 'lucide-react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { Empty, ErrorBox, GlassPanel, PriorityPill, Spinner, Stat, fadeUp, fmtDate, stagger } from '../components/ui.jsx'

const STAGE_ORDER = [
  'Design', 'Planning', 'Procurement', 'Sourcing',
  'Manufacturing', 'Quality Control', 'Packing', 'Shipping',
]

const CHART_TOKENS = {
  grid: 'rgba(255,255,255,0.06)',
  axis: '#5a5548',
  brass: '#dcae5e',
  teal: '#5fd4c4',
  bone: '#c9c2b3',
}
const PRIORITY_COLOR = { Low: '#8f887a', Medium: '#5fd4c4', High: '#dcae5e', Urgent: '#f87171' }
const SKILL_COLOR = { Junior: '#5a5548', Mid: '#dcae5e', Senior: '#5fd4c4' }

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-strong rounded-lg px-3 py-2 text-xs">
      {label && <div className="mb-1 font-semibold text-bone-100">{label}</div>}
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-1.5 text-bone-300">
          <span className="h-2 w-2 rounded-full" style={{ background: p.fill || p.color }} />
          {p.name}: <span className="font-semibold text-bone-50">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function Projects() {
  const projects = useAsync(() => api.projects(), [])
  const dashboard = useAsync(() => api.dashboard(), [])
  const employees = useAsync(() => api.employees({ limit: 2000 }), [])
  const [creating, setCreating] = useState(false)

  const priorityData = useMemo(() => {
    const counts = { Low: 0, Medium: 0, High: 0, Urgent: 0 }
    for (const p of projects.data || []) counts[p.priority] = (counts[p.priority] || 0) + 1
    return Object.entries(counts).map(([name, value]) => ({ name, value }))
  }, [projects.data])

  const categoryData = useMemo(() => {
    const rows = { 'White Collar': { name: 'White Collar', Active: 0, Inactive: 0 }, 'Blue Collar': { name: 'Blue Collar', Active: 0, Inactive: 0 } }
    for (const e of employees.data || []) {
      const cat = e.designation?.category
      if (!rows[cat]) continue
      rows[cat][e.status] = (rows[cat][e.status] || 0) + 1
    }
    return Object.values(rows)
  }, [employees.data])

  const skillData = useMemo(() => {
    const counts = { Junior: 0, Mid: 0, Senior: 0 }
    for (const e of employees.data || []) counts[e.skill_level] = (counts[e.skill_level] || 0) + 1
    return Object.entries(counts).map(([name, value]) => ({ name, value }))
  }, [employees.data])

  const loading = projects.loading || dashboard.loading
  const err = projects.error || dashboard.error

  function reloadAll() {
    projects.reload(); dashboard.reload(); employees.reload()
  }

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-brass-400">Operations overview</div>
          <h1 className="mt-1 font-display text-2xl font-bold text-bone-50">Manpower dashboard</h1>
          <p className="mt-1 text-sm text-bone-500">
            Live counts from the database — nothing here is simulated.
          </p>
        </div>
        <motion.button
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.97 }}
          className="btn-primary"
          onClick={() => setCreating((v) => !v)}
        >
          {creating ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {creating ? 'Cancel' : 'New project'}
        </motion.button>
      </div>

      <ErrorBox error={err} onRetry={reloadAll} />

      <motion.div
        variants={stagger} initial="hidden" animate="show"
        className="grid grid-cols-2 gap-4 lg:grid-cols-4"
      >
        <motion.div variants={fadeUp}><Stat icon={FolderKanban} label="Projects" value={dashboard.data?.projects ?? '—'} hint="across all stages" /></motion.div>
        <motion.div variants={fadeUp}><Stat icon={Users} label="Active employees" value={dashboard.data?.employees_active ?? '—'} hint="eligible for allocation" /></motion.div>
        <motion.div variants={fadeUp}><Stat icon={Link2} label="Allocations" value={dashboard.data?.allocations ?? '—'} hint="tasks with a person assigned" /></motion.div>
        <motion.div variants={fadeUp}>
          <Stat
            icon={TriangleAlert}
            label="Open shortages"
            value={dashboard.data?.shortages ?? '—'}
            tone={dashboard.data?.shortages ? 'warn' : 'good'}
            hint={dashboard.data?.shortages ? 'need attention' : 'all roles covered'}
          />
        </motion.div>
      </motion.div>

      {creating && (
        <NewProjectForm
          onCreated={() => { setCreating(false); reloadAll() }}
        />
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard title="Projects by priority" subtitle="how the current pipeline is weighted">
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={priorityData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={CHART_TOKENS.grid} />
              <XAxis dataKey="name" tick={{ fill: CHART_TOKENS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fill: CHART_TOKENS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
              <Bar dataKey="value" name="Projects" radius={[6, 6, 0, 0]} maxBarSize={44}>
                {priorityData.map((d) => <Cell key={d.name} fill={PRIORITY_COLOR[d.name]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Workforce by category" subtitle="active vs inactive, white vs blue collar">
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={categoryData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={CHART_TOKENS.grid} />
              <XAxis dataKey="name" tick={{ fill: CHART_TOKENS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fill: CHART_TOKENS.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
              <Bar dataKey="Active" stackId="s" fill={CHART_TOKENS.teal} radius={[0, 0, 0, 0]} maxBarSize={44} />
              <Bar dataKey="Inactive" stackId="s" fill="rgba(255,255,255,0.12)" radius={[6, 6, 0, 0]} maxBarSize={44} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Skill mix" subtitle="junior / mid / senior across active roster">
          <ResponsiveContainer width="100%" height={190}>
            <PieChart>
              <Tooltip content={<ChartTooltip />} />
              <Pie data={skillData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={3} strokeWidth={0}>
                {skillData.map((d) => <Cell key={d.name} fill={SKILL_COLOR[d.name]} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-1 flex flex-wrap justify-center gap-3">
            {skillData.map((d) => (
              <div key={d.name} className="flex items-center gap-1.5 text-xs text-bone-500">
                <span className="h-2 w-2 rounded-full" style={{ background: SKILL_COLOR[d.name] }} />
                {d.name} <span className="font-semibold text-bone-200">{d.value}</span>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>

      <div>
        <div className="mb-3 flex items-end justify-between">
          <h2 className="font-display text-lg font-semibold text-bone-50">Projects</h2>
          <span className="text-xs text-bone-600">{projects.data?.length ?? 0} total</span>
        </div>

        {loading ? (
          <Spinner label="Loading projects…" />
        ) : !projects.data?.length ? (
          <Empty>No projects yet — create one above.</Empty>
        ) : (
          <motion.div variants={stagger} initial="hidden" animate="show" className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {projects.data.map((project) => (
              <motion.div key={project.id} variants={fadeUp}>
                <ProjectCard project={project} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    </div>
  )
}

function ChartCard({ title, subtitle, children }) {
  return (
    <GlassPanel className="p-4">
      <div className="mb-1 text-sm font-semibold text-bone-100">{title}</div>
      <div className="mb-2 text-[11px] text-bone-600">{subtitle}</div>
      {children}
    </GlassPanel>
  )
}

function ProjectCard({ project }) {
  return (
    <Link to={`/projects/${project.id}`} className="group block">
      <GlassPanel className="relative overflow-hidden p-4 transition-transform duration-300 group-hover:-translate-y-1 group-hover:border-brass-500/30">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="font-mono text-[11px] text-bone-600">{project.project_code}</div>
            <div className="mt-0.5 font-display text-[15px] font-semibold leading-snug text-bone-50">
              {project.name}
            </div>
          </div>
          <PriorityPill value={project.priority} />
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-bone-500">
          <span>{project.client || 'No client set'}</span>
          <span>·</span>
          <span>{project.location || 'No location'}</span>
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-white/[0.06] pt-3 text-xs">
          <span className="text-bone-600">
            {fmtDate(project.start_date)} → {fmtDate(project.target_end_date)}
          </span>
          <span className="flex items-center gap-1 font-medium text-brass-400 opacity-0 transition-opacity group-hover:opacity-100">
            Open plan <ArrowUpRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </GlassPanel>
    </Link>
  )
}

function NewProjectForm({ onCreated }) {
  const [form, setForm] = useState({
    project_code: '',
    name: '',
    client: '',
    location: '',
    priority: 'Medium',
    start_date: new Date().toISOString().slice(0, 10),
    target_end_date: '',
  })
  const [budgets, setBudgets] = useState(Object.fromEntries(STAGE_ORDER.map((s) => [s, ''])))
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  async function submit(event) {
    event.preventDefault()
    setBusy(true); setError(null)
    try {
      const stage_budgets = Object.fromEntries(
        Object.entries(budgets).filter(([, v]) => v !== '' && Number(v) > 0).map(([k, v]) => [k, Number(v)]),
      )
      await api.createProject({
        ...form,
        client: form.client || null,
        location: form.location || null,
        target_end_date: form.target_end_date || null,
        stage_budgets,
      })
      onCreated()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <motion.form
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden"
    >
      <GlassPanel strong className="space-y-4 p-5">
        <div className="grid gap-3 md:grid-cols-4">
          <div><label className="label">Project code</label><input required className="input" value={form.project_code} onChange={set('project_code')} placeholder="PRJ008" /></div>
          <div className="md:col-span-2"><label className="label">Name</label><input required className="input" value={form.name} onChange={set('name')} /></div>
          <div><label className="label">Priority</label>
            <select className="input" value={form.priority} onChange={set('priority')}>
              {['Low', 'Medium', 'High', 'Urgent'].map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div><label className="label">Client</label><input className="input" value={form.client} onChange={set('client')} /></div>
          <div><label className="label">Location</label><input className="input" value={form.location} onChange={set('location')} /></div>
          <div><label className="label">Start date</label><input type="date" required className="input" value={form.start_date} onChange={set('start_date')} /></div>
          <div><label className="label">Target end date</label><input type="date" className="input" value={form.target_end_date} onChange={set('target_end_date')} /></div>
        </div>

        <div>
          <div className="label">Stage budgets (man-days)</div>
          <p className="mb-2 text-xs text-bone-600">
            Leave a stage blank to skip it. Default sub-tasks are generated automatically and can be edited from the project page.
          </p>
          <div className="grid gap-2 sm:grid-cols-4 lg:grid-cols-8">
            {STAGE_ORDER.map((stage) => (
              <div key={stage}>
                <label className="mb-1 block text-[11px] text-bone-600">{stage}</label>
                <input type="number" min="0" className="input" value={budgets[stage]}
                  onChange={(e) => setBudgets({ ...budgets, [stage]: e.target.value })} />
              </div>
            ))}
          </div>
        </div>

        <ErrorBox error={error} />
        <motion.button whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }} className="btn-primary" disabled={busy}>
          {busy ? 'Creating…' : 'Create project'}
        </motion.button>
      </GlassPanel>
    </motion.form>
  )
}
