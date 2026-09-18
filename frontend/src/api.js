const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (response.status === 204) return null
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.detail
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail ?? response.statusText))
  }
  return payload
}

export const api = {
  dashboard: () => request('/dashboard'),
  stages: () => request('/stages'),
  createStage: (body) => request('/stages', { method: 'POST', body }),
  updateStage: (id, body) => request(`/stages/${id}`, { method: 'PATCH', body }),
  stageDesignations: (id) => request(`/stages/${id}/designations`),
  linkDesignation: (stageId, designationId) =>
    request(`/stages/${stageId}/designations`, { method: 'POST', body: { designation_id: designationId } }),

  designations: () => request('/designations'),
  createDesignation: (body) => request('/designations', { method: 'POST', body }),
  updateDesignation: (id, body) => request(`/designations/${id}`, { method: 'PATCH', body }),

  calendarRules: () => request('/calendar-rules'),

  holidays: () => request('/holidays'),
  createHoliday: (body) => request('/holidays', { method: 'POST', body }),
  deleteHoliday: (id) => request(`/holidays/${id}`, { method: 'DELETE' }),

  employees: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null))
    return request(`/employees${qs.toString() ? `?${qs}` : ''}`)
  },
  createEmployee: (body) => request('/employees', { method: 'POST', body }),
  updateEmployee: (id, body) => request(`/employees/${id}`, { method: 'PATCH', body }),
  deleteEmployee: (id) => request(`/employees/${id}`, { method: 'DELETE' }),
  workload: (id) => request(`/employees/${id}/workload`),

  projects: () => request('/projects'),
  project: (id) => request(`/projects/${id}`),
  createProject: (body) => request('/projects', { method: 'POST', body }),
  updateProject: (id, body) => request(`/projects/${id}`, { method: 'PATCH', body }),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),
  validate: (id) => request(`/projects/${id}/validate`),

  allocate: (id) => request(`/projects/${id}/allocate`, { method: 'POST' }),
  gantt: (id) => request(`/projects/${id}/gantt`),
  shortages: (id) => request(`/projects/${id}/shortages`),
  conflicts: () => request('/conflicts'),

  tasks: (projectId) => request(`/projects/${projectId}/tasks`),
  createTask: (projectId, stageId, body) =>
    request(`/projects/${projectId}/stages/${stageId}/tasks`, { method: 'POST', body }),
  updateTask: (projectId, taskId, body) =>
    request(`/projects/${projectId}/tasks/${taskId}`, { method: 'PATCH', body }),
  deleteTask: (projectId, taskId) =>
    request(`/projects/${projectId}/tasks/${taskId}`, { method: 'DELETE' }),

  aiStatus: () => request('/ai/status'),
  readInsights: (id) => request(`/projects/${id}/insights`),
  generateInsights: (id, force = false) =>
    request(`/projects/${id}/insights?force=${force}`, { method: 'POST' }),
}
