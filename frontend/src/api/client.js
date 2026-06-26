const BASE = import.meta.env.VITE_API_URL ?? ''

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw Object.assign(new Error(err.detail ?? res.statusText), { status: res.status })
  }
  return res.json()
}

export const getJobs = (params = {}) => {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  )
  return req(`/jobs${q.size ? '?' + q : ''}`)
}

export const getJob = (id) => req(`/jobs/${id}`)

export const getRuns = () => req('/runs')

export const getRunSummary = (id) => req(`/runs/${id}/summary`)

export const getApplications = () => req('/applications')

export const createApplication = (job_id) =>
  req('/applications', { method: 'POST', body: JSON.stringify({ job_id }) })

export const updateApplication = (id, patch) =>
  req(`/applications/${id}`, { method: 'PATCH', body: JSON.stringify(patch) })
