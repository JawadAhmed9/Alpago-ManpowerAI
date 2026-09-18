# Architecture

## Layering

```
React (Vite + Tailwind)
        │  REST /api/v1
FastAPI routers  ── thin: validation, HTTP status, serialisation
        │
Services  ── scheduling_service · allocation_service · report_service · ai/insights
        │      DB ⇄ engine adapters, transactions, persistence
Engine    ── workcalendar · scheduler · allocator
        │      pure Python, no ORM, no I/O, no network
SQLAlchemy models ── PostgreSQL
```

The engine layer is deliberately free of the ORM: it takes dataclasses and returns
dataclasses. That is what makes the PRJ007 regression, the calendar arithmetic and the
allocation scoring testable in milliseconds without a database, and what keeps the
scheduling rules readable as rules.

## The two things the workbook gets wrong

### 1. "(Calendar Days)" is a man-day budget

The Instructions sheet says the Project Master's per-stage numbers are calendar days
from stage start to stage end. The data disagrees:

| Stage | PRJ007 number | Sub-task durations | Grid span |
|---|---|---|---|
| Design | 5 | 3 + 2 | 4 working days (tasks overlap by one) |
| Manufacturing | 48 | 15 + 10 + 11 + 12 | 24-Sep → 24-Oct, ~26 working days |
| Quality Control | 2 | 1 + 1 | 2 days, split across two categories |
| Shipping | 3 | 1 + 2 | 3 days |

All eight stages sum to **74**, which is the sheet's own *Total Man Power Days = 74*.
Manufacturing's 48 cannot be a window length — the four tasks run partly in parallel,
so the stage occupies far fewer than 48 days on the grid.

So `ProjectStage.man_days_budgeted` is the model, and `validate_stage_budgets()`
reports any stage whose task durations do not sum back to it. `split_budget()` uses the
largest-remainder method so a generated breakdown always partitions the budget exactly,
at any project size.

### 2. "Actual Working Days = 51" is off by one

The number in each grid cell is a cumulative working-day counter along the dependency
chain. Reading it back:

```
Concept design    1-3      base 0
CAD detailing     4-5      base 3   (starts on concept's last day, lag -1)
Planning          6-10     base 5
Procurement       11-15    base 10
Sourcing          16-18    base 15
Carpentry         19-33    base 18
CNC cutting       19-28    base 18   (parallel with carpentry -- same base)
Welding           29-39    base 28   (follows CNC)
Finishing         34-45    base 33   (follows carpentry)
QC inspection     45       base 44?? -- should be 45, i.e. numbered 46
```

Every task up to *Finishing & polishing* follows `base = last day-number of the latest
predecessor`. *In-line quality inspection* breaks it: Finishing ends at 45, so
inspection should be 46. The sheet writes 45, and the −1 carries through packing,
dispatch and transport to produce 51 instead of 52.

The engine applies the rule uniformly, so it reports 52. Every *date* in the sheet is
reproduced exactly — see `tests/test_prj007_regression.py`.

Three other stale values in the sheet's text columns are ignored in favour of the grid
cells: Stage 5's header (`19-Sep → 23-Sep, 48 days`), Procurement's start (`13-Sep`, a
Sunday), and Welding/Finishing's end dates (one day early each).

## Scheduling

Every dependency is finish-to-start with a lag in **working days**:

```
successor.start = successor_calendar.advance(predecessor.end, 1 + lag)
```

`lag = 0` starts the successor on the next working day; `lag = -1` starts it on the
predecessor's final day, giving the one-day overlap the Design stage shows. Tasks are
processed in topological order with a stable tie-break on (stage order, task order), so
output is byte-for-byte reproducible. Cycles raise `CyclicDependencyError`.

One subtlety worth naming: `advance()` steps from the predecessor's raw calendar date,
not from a rolled-forward one. Blue-collar QC inspection ends on Saturday 24-Oct;
"one working day later" for the white-collar QA engineer is Monday 26-Oct, not Tuesday
27-Oct. Stepping from a rolled-forward Monday would have lost a day. There is a test
for exactly this.

Calendars come from `CalendarRule` rows (worked ISO weekdays per category) plus the
admin-editable `PublicHoliday` table, which applies to everyone. Changing either
re-plans every project on the next request — no migration, no code change.

## Task breakdown

The sub-task breakdown exists nowhere in the workbook's master data; it appears once,
inside the PRJ007 worked example. Two possible readings: hardcode that example, or treat
it as data. It is data here — `Task` rows a project manager creates, edits and deletes
through the API, with `TaskDependency` edges — and `app/seed/templates.py` ships default
templates so a new project is immediately usable. The templates reproduce PRJ007's
breakdown exactly and scale to any budget.

`StageTemplate.exit_task_indices` deserves a note. Packing follows the *in-line
inspection*, not the *QA sign-off* that runs in parallel with it, so Quality Control
declares task 0 as its exit rather than defaulting to its terminal task. That one field
is what makes packing land on 26-Oct, matching the sheet.

## Allocation

```
filter: designation matches, status == Active, designation.allocatable
filter: zero overlapping allocations in [start, end]  -- across ALL projects
rank:   skill weight  −  workload_penalty × days already booked  −  tenure ε
assign: top candidate; if none survive the availability filter, raise a Shortage
```

Weights are settings, not constants, so the scoring policy is tunable per deployment.
The tenure term is scaled to ~1e-7 so it can only ever break an exact tie.

**The hard constraint.** `BookingIndex` holds every existing allocation plus the ones
made earlier in the same run, so a task can never be given someone the previous task
just took. `Allocation` carries a composite index on
`(employee_id, actual_start_date, actual_end_date)` and a unique constraint on
`task_id`. Re-running allocation for a project deletes that project's own allocations
first and excludes them from the booking index, so the operation is idempotent rather
than self-colliding.

**Shortages are first-class.** When nobody is free, the system records who is blocking,
their headcount, and the earliest date any of them frees up — computed deterministically.
Downstream tasks still get scheduled and still appear in the Gantt, marked unassigned in
red. Nothing fails silently.

**Conflicts stay queryable** even though the allocator cannot create one, because
imported or legacy rows can violate the rule. `detect_conflicts` sorts each employee's
bookings and breaks out of the inner loop as soon as a booking starts after the current
one ends.

## Why the AI layer is thin

The brief asks for AI-assisted recommendations. Scheduling maths and resource
assignment are exactly the kind of work an LLM does unreliably and unaccountably — and
a planner cannot act on a schedule they cannot audit. So the deterministic engine
produces both the decision *and* its own plain-language justification
(`AllocationDecision.reason()`, `ShortageFinding.reason()`), and the LLM's only job is
to rewrite those into prose.

Operational consequences: one batched provider call per allocation run, not one per
task; capped by `AI_MAX_ITEMS_PER_RUN`; results cached in `ai_insights` and re-served
on page load; and every failure path — no key, bad key, quota exhausted, timeout,
malformed response — falls back to the deterministic sentence and marks the row
`model = "deterministic"`. There is a test asserting the app behaves correctly with no
API key at all.

## Scale

Nothing is hardcoded to the sample's 56 employees, 7 projects, 8 stages or 23
designations. Stages, designations and their valid pairings are rows; adding a stage is
a `POST`. `split_budget` works for any budget and any number of tasks. Employee queries
are filtered, indexed and paginated.

The current allocator holds bookings in memory for the run, which is right for
interactive use at this scale (thousands of allocations). The natural next step, if the
horizon grows to tens of thousands, is a Postgres `daterange` column with a GiST
exclusion constraint on `(employee_id, window)` — that pushes the no-overlap rule into
the database itself and lets the availability filter become an index scan. The service
boundary is already drawn so that swap touches `BookingIndex` and nothing else.

## Things deliberately left out

- **Overtime is modelled but not scheduled against.** `CalendarRule.overtime_allowed`
  and `Designation.overtime_applicable` are carried through from the workbook, and
  blue-collar Sunday work is the obvious lever a planner reaches for when a shortage
  appears. Compressing a task by authorising OT is a scheduling policy the brief does
  not specify, so the system surfaces the shortage and its earliest-free date instead of
  guessing. The hook is `Task.duration_working_days` plus an OT factor.
- **No auth.** Out of scope for the assessment. The obvious shape is an
  `Authorization` dependency on the router layer plus role checks (planner vs viewer);
  no service-layer code would change.
- **Resource levelling.** The allocator is greedy in topological order, which matches
  the brief ("assign the best available match"). It does not shuffle earlier
  assignments to resolve a later shortage. That is a solver problem, and a greedy pass
  with visible shortages is more useful to a planner than an opaque optimum.
