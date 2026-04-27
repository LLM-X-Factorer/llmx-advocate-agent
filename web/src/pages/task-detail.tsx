import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState, useMemo } from 'react'
import { api } from '@/api/client'
import type { PhaseId, PhaseRun, PhaseRunStatus, TaskStatus } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { JsonBlock } from '@/components/json-block'
import { cn, formatDuration, formatTimestamp } from '@/lib/utils'
import { CheckCircle2, XCircle, Circle, Loader2, ExternalLink, ArrowLeft } from 'lucide-react'

const PHASES: PhaseId[] = ['P1', 'P1.5', 'P2', 'P2.5', 'P2.6', 'P3', 'P4', 'P5', 'P6']

const TASK_STATUS_TONE: Record<TaskStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  completed: 'success',
  running: 'info',
  paused_for_human: 'warning',
  failed: 'danger',
}

const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  completed: '已完成',
  running: '运行中',
  paused_for_human: '等待人工',
  failed: '失败',
}

export function TaskDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const [selectedPhase, setSelectedPhase] = useState<PhaseId>('P1')

  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['task', id],
    queryFn: () => api.getTask(id),
    enabled: !!id,
    refetchInterval: (q) => {
      const status = q.state.data?.task.status
      return status === 'running' ? 3000 : false
    },
  })

  const runsByPhase = useMemo(() => {
    const map = new Map<PhaseId, PhaseRun[]>()
    for (const r of data?.runs ?? []) {
      const arr = map.get(r.phase_id) ?? []
      arr.push(r)
      map.set(r.phase_id, arr)
    }
    return map
  }, [data?.runs])

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-8">
        <p className="text-sm text-zinc-500">加载中…</p>
      </div>
    )
  }
  if (isError || !data) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="rounded-md border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-4">
          <p className="text-sm text-red-800 dark:text-red-300">
            加载失败：{error instanceof Error ? error.message : '未知错误'}
          </p>
          <Link to="/" className="mt-3 inline-block">
            <Button variant="outline" size="sm">
              <ArrowLeft className="h-4 w-4" />
              返回列表
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const { task } = data
  const selectedRuns = runsByPhase.get(selectedPhase) ?? []

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="mb-6">
        <Link to="/" className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 inline-flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" />
          返回列表
        </Link>
      </div>

      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight truncate">{task.title}</h1>
          <div className="flex items-center gap-3 mt-2 text-sm flex-wrap">
            <Badge tone={TASK_STATUS_TONE[task.status]}>{TASK_STATUS_LABEL[task.status]}</Badge>
            <span className="text-zinc-500">当前 phase: <span className="font-mono">{task.current_phase}</span></span>
            <span className="text-zinc-500">{formatTimestamp(task.created_at)}</span>
            {isFetching && <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />}
          </div>
          <div className="text-xs text-zinc-400 mt-1.5 font-mono">{task.id}</div>
        </div>
        <Link to={`/tasks/${task.id}/export`}>
          <Button variant="outline">
            <ExternalLink className="h-4 w-4" />
            导出预览
          </Button>
        </Link>
      </div>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <ConfigItem label="Provider" value={task.config.llm_provider ?? '—'} />
          <ConfigItem label="Model" value={task.config.llm_model ?? '—'} mono />
          <ConfigItem label="Opening Style" value={task.config.opening_style} mono />
          <ConfigItem label="Target Tier" value={String(task.config.target_tier)} mono />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        <PhaseTimeline
          runsByPhase={runsByPhase}
          currentPhase={task.current_phase}
          selectedPhase={selectedPhase}
          onSelect={setSelectedPhase}
        />
        <PhaseDetail phase={selectedPhase} runs={selectedRuns} />
      </div>
    </div>
  )
}

function ConfigItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-zinc-500 dark:text-zinc-400 mb-0.5">{label}</div>
      <div className={cn('text-zinc-900 dark:text-zinc-100', mono && 'font-mono')}>{value}</div>
    </div>
  )
}

function PhaseTimeline({
  runsByPhase,
  currentPhase,
  selectedPhase,
  onSelect,
}: {
  runsByPhase: Map<PhaseId, PhaseRun[]>
  currentPhase: PhaseId
  selectedPhase: PhaseId
  onSelect: (p: PhaseId) => void
}) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 text-xs font-medium text-zinc-600 dark:text-zinc-400 uppercase tracking-wide">
        Phase 进度
      </div>
      <ul>
        {PHASES.map((p) => {
          const runs = runsByPhase.get(p) ?? []
          const last = runs[runs.length - 1]
          const isCurrent = p === currentPhase
          const isSelected = p === selectedPhase
          return (
            <li key={p}>
              <button
                onClick={() => onSelect(p)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-3 text-left text-sm border-l-2 transition-colors',
                  isSelected
                    ? 'border-violet-500 bg-violet-50 dark:bg-violet-950/30'
                    : 'border-transparent hover:bg-zinc-50 dark:hover:bg-zinc-900'
                )}
              >
                <PhaseStatusIcon status={last?.status} hasRuns={runs.length > 0} isCurrent={isCurrent} />
                <span className="font-mono font-medium text-zinc-900 dark:text-zinc-100">{p}</span>
                <span className="ml-auto text-xs text-zinc-500">
                  {runs.length > 0 ? `${runs.length} attempts` : '—'}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function PhaseStatusIcon({
  status,
  hasRuns,
  isCurrent,
}: {
  status?: PhaseRunStatus
  hasRuns: boolean
  isCurrent: boolean
}) {
  if (!hasRuns) {
    return isCurrent ? (
      <Loader2 className="h-4 w-4 animate-spin text-violet-500" />
    ) : (
      <Circle className="h-4 w-4 text-zinc-300 dark:text-zinc-700" />
    )
  }
  if (status === 'passed') return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
  if (status === 'qa_failed' || status === 'qa_failed_terminal' || status === 'error')
    return <XCircle className="h-4 w-4 text-red-500" />
  return <Circle className="h-4 w-4 text-zinc-400" />
}

function PhaseDetail({ phase, runs }: { phase: PhaseId; runs: PhaseRun[] }) {
  const [selectedRunIdx, setSelectedRunIdx] = useState(runs.length - 1)
  // Reset selection when phase changes
  useMemo(() => {
    setSelectedRunIdx(runs.length - 1)
  }, [phase, runs.length])

  if (runs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 p-8 text-center">
        <p className="text-sm text-zinc-500">
          <span className="font-mono">{phase}</span> 还没有运行记录
        </p>
      </div>
    )
  }

  const current = runs[Math.max(0, Math.min(selectedRunIdx, runs.length - 1))]

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
        <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <h2 className="text-sm font-medium">
            <span className="font-mono">{phase}</span> · attempts ({runs.length})
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900 text-xs text-zinc-600 dark:text-zinc-400">
            <tr>
              <th className="text-left font-medium px-4 py-2 w-14">#</th>
              <th className="text-left font-medium px-4 py-2 w-32">状态</th>
              <th className="text-left font-medium px-4 py-2">Model</th>
              <th className="text-left font-medium px-4 py-2 w-20">耗时</th>
              <th className="text-left font-medium px-4 py-2 w-32">触发</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r, i) => (
              <tr
                key={r.id}
                onClick={() => setSelectedRunIdx(i)}
                className={cn(
                  'border-t border-zinc-100 dark:border-zinc-800 cursor-pointer transition-colors',
                  i === selectedRunIdx
                    ? 'bg-violet-50 dark:bg-violet-950/30'
                    : 'hover:bg-zinc-50 dark:hover:bg-zinc-900'
                )}
              >
                <td className="px-4 py-2 font-mono text-zinc-500">{r.attempt}</td>
                <td className="px-4 py-2">
                  <RunStatusBadge status={r.status} editedByHuman={r.edited_by_human} />
                </td>
                <td className="px-4 py-2 font-mono text-xs text-zinc-600 dark:text-zinc-400 truncate max-w-[280px]">
                  {r.llm_model}
                </td>
                <td className="px-4 py-2 text-xs text-zinc-500">{formatDuration(r.duration_ms)}</td>
                <td className="px-4 py-2 text-xs text-zinc-500">{r.trigger}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {current.qa_result && <QAGatesPanel result={current.qa_result} />}

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 text-sm font-medium">
          输出
        </div>
        <div className="p-4">
          <JsonBlock data={current.output} />
        </div>
      </div>
    </div>
  )
}

function RunStatusBadge({
  status,
  editedByHuman,
}: {
  status: PhaseRunStatus
  editedByHuman: boolean
}) {
  const map: Record<PhaseRunStatus, { tone: 'success' | 'warning' | 'danger' | 'neutral'; label: string }> = {
    passed: { tone: 'success', label: 'passed' },
    qa_failed: { tone: 'warning', label: 'qa failed' },
    qa_failed_terminal: { tone: 'danger', label: 'qa terminal' },
    error: { tone: 'danger', label: 'error' },
  }
  const cfg = map[status]
  return (
    <div className="flex items-center gap-1.5">
      <Badge tone={cfg.tone}>{cfg.label}</Badge>
      {editedByHuman && <Badge tone="info">edited</Badge>}
    </div>
  )
}

function QAGatesPanel({ result }: { result: NonNullable<PhaseRun['qa_result']> }) {
  const passed = result.gates.filter((g) => g.passed).length
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
      <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
        <h3 className="text-sm font-medium">QA Gates</h3>
        <span className="text-xs text-zinc-500">
          {passed}/{result.gates.length} 通过
        </span>
      </div>
      <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {result.gates.map((g) => (
          <li key={g.gate_id} className="px-4 py-3">
            <div className="flex items-start gap-2">
              {g.passed ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs text-zinc-700 dark:text-zinc-300">
                    {g.gate_id}
                  </span>
                  <span className="text-xs text-zinc-500">{g.name}</span>
                </div>
                <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-1 leading-relaxed">
                  {g.rationale}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
