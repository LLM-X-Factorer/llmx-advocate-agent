import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { Task, TaskStatus } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatTimestamp } from '@/lib/utils'
import { Loader2, Plus } from 'lucide-react'

const STATUS_TONE: Record<TaskStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  completed: 'success',
  running: 'info',
  paused_for_human: 'warning',
  failed: 'danger',
}

const STATUS_LABEL: Record<TaskStatus, string> = {
  completed: '已完成',
  running: '运行中',
  paused_for_human: '等待人工',
  failed: '失败',
}

export function TasksPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.listTasks(),
    refetchInterval: 5000,
  })

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">任务</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            每 5 秒自动刷新 · 共 {data?.length ?? 0} 个
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching && (
            <Loader2 className="h-4 w-4 animate-spin text-zinc-400" aria-label="刷新中" />
          )}
          <Link to="/new">
            <Button>
              <Plus className="h-4 w-4" />
              新建任务
            </Button>
          </Link>
        </div>
      </div>

      {isLoading && <p className="text-sm text-zinc-500">加载中…</p>}
      {isError && (
        <div className="rounded-md border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-4">
          <p className="text-sm text-red-800 dark:text-red-300">
            加载失败：{error instanceof Error ? error.message : String(error)}
          </p>
          <Button size="sm" variant="outline" className="mt-3" onClick={() => refetch()}>
            重试
          </Button>
        </div>
      )}

      {data && data.length === 0 && !isLoading && (
        <div className="rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 p-10 text-center">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">还没有任务</p>
          <Link to="/new">
            <Button className="mt-4">
              <Plus className="h-4 w-4" />
              创建第一个任务
            </Button>
          </Link>
        </div>
      )}

      {data && data.length > 0 && <TaskTable tasks={data} />}
    </div>
  )
}

function TaskTable({ tasks }: { tasks: Task[] }) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-zinc-50 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400">
          <tr className="border-b border-zinc-200 dark:border-zinc-800">
            <th className="text-left font-medium px-4 py-3">标题</th>
            <th className="text-left font-medium px-4 py-3 w-36">状态</th>
            <th className="text-left font-medium px-4 py-3 w-28">当前 Phase</th>
            <th className="text-left font-medium px-4 py-3 w-44">创建时间</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr
              key={t.id}
              className="border-b border-zinc-100 dark:border-zinc-800 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors"
            >
              <td className="px-4 py-3">
                <Link
                  to={`/tasks/${t.id}`}
                  className="font-medium text-zinc-900 dark:text-zinc-100 hover:text-violet-600 dark:hover:text-violet-400"
                >
                  {t.title}
                </Link>
                <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5 font-mono">
                  {t.id}
                </div>
              </td>
              <td className="px-4 py-3">
                <Badge tone={STATUS_TONE[t.status]}>{STATUS_LABEL[t.status]}</Badge>
              </td>
              <td className="px-4 py-3 font-mono text-xs text-zinc-600 dark:text-zinc-400">
                {t.current_phase}
              </td>
              <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400 text-xs">
                {formatTimestamp(t.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
