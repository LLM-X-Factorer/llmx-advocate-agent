import type { components, paths } from './schema'

export type Task = components['schemas']['Task']
export type TaskDetail = components['schemas']['TaskDetail']
export type TaskConfig = components['schemas']['TaskConfig']
export type SourceInput = components['schemas']['SourceInput']
export type PhaseRun = components['schemas']['PhaseRun']
export type PhaseRunStatus = components['schemas']['PhaseRunStatus']
export type TaskStatus = components['schemas']['TaskStatus']
export type QAResult = components['schemas']['QAResult']
export type TaskExport = components['schemas']['TaskExport']
export type CreateTaskRequest = components['schemas']['CreateTaskRequest']
export type PhaseId = components['schemas']['PhaseId']

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api'

class ApiError extends Error {
  status: number
  body: string
  constructor(status: number, body: string) {
    super(`API ${status}: ${body.slice(0, 200)}`)
    this.status = status
    this.body = body
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, text)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  listTasks: (status?: TaskStatus) =>
    request<Task[]>('GET', `/tasks${status ? `?status=${status}` : ''}`),
  getTask: (id: string) => request<TaskDetail>('GET', `/tasks/${id}`),
  createTask: (req: CreateTaskRequest) => request<TaskDetail>('POST', '/tasks', req),
  runTask: (id: string) => request<TaskDetail>('POST', `/tasks/${id}/actions/run`),
  pauseTask: (id: string) => request<{ task_id: string; status: string }>(
    'POST',
    `/tasks/${id}/actions/pause`
  ),
  exportTask: (id: string) => request<TaskExport>('GET', `/tasks/${id}/export`),
  rerunQA: (id: string, phase: PhaseId) =>
    request<PhaseRun>('POST', `/tasks/${id}/phases/${phase}/qa`),
}

export type ApiPaths = paths
export { ApiError }
