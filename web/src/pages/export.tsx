import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { JsonBlock } from '@/components/json-block'
import { ArrowLeft, Download, Copy } from 'lucide-react'
import { useState } from 'react'

interface Scene {
  scene_type?: string
  title?: string
  subtitle?: string
  main_text?: string
  sub_text?: string
  cards?: string[]
  bullets?: string[]
  chapter_number?: number
  chapter_title?: string
  duration_seconds?: number
  tts_text?: string
  visual?: { type?: string; [k: string]: unknown }
  [k: string]: unknown
}

interface VideoJSON {
  export_formats?: string[]
  scenes?: Scene[]
  [k: string]: unknown
}

interface PublishingPayload {
  titles?: { text: string; formula_id?: string | null; rationale?: string | null }[]
  description?: string
  pinned_comment?: string | null
  [k: string]: unknown
}

export function ExportPage() {
  const { id = '' } = useParams<{ id: string }>()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['task-export', id],
    queryFn: () => api.exportTask(id),
    enabled: !!id,
  })

  if (isLoading) {
    return <div className="max-w-4xl mx-auto px-6 py-8 text-sm text-zinc-500">加载中…</div>
  }
  if (isError || !data) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <p className="text-sm text-red-600">
          加载失败：{error instanceof Error ? error.message : '未知错误'}
        </p>
      </div>
    )
  }

  const video = data.video_json as VideoJSON | null
  const publishing = data.publishing as PublishingPayload | null
  const totalDuration =
    video?.scenes?.reduce((s, sc) => s + (sc.duration_seconds ?? 0), 0) ?? 0

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-6">
        <Link
          to={`/tasks/${id}`}
          className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回任务详情
        </Link>
      </div>

      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>
          <div className="flex items-center gap-3 mt-2 text-sm">
            <Badge tone={data.status === 'completed' ? 'success' : 'warning'}>{data.status}</Badge>
            {data.tier && <span className="text-zinc-500">tier: <span className="font-mono">{data.tier}</span></span>}
            {video?.scenes && (
              <span className="text-zinc-500">
                {video.scenes.length} scenes · {Math.round(totalDuration)}s
              </span>
            )}
          </div>
        </div>
        <DownloadButton data={data} />
      </div>

      {data.judgment && (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>核心判断（P2.5）</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-zinc-900 dark:text-zinc-100 leading-relaxed">{data.judgment}</p>
            {data.theme && data.theme !== data.judgment && (
              <p className="text-sm text-zinc-500 mt-2">主题（P2.6）：{data.theme}</p>
            )}
          </CardContent>
        </Card>
      )}

      {publishing?.titles && publishing.titles.length > 0 && (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>标题候选</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {publishing.titles.map((t, i) => (
              <div key={i} className="rounded-md border border-zinc-200 dark:border-zinc-800 p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-zinc-900 dark:text-zinc-100 font-medium leading-snug">
                    {t.text}
                  </p>
                  <CopyIcon text={t.text} />
                </div>
                <div className="text-xs text-zinc-500 mt-1.5 flex items-center gap-3">
                  {t.formula_id && (
                    <span className="font-mono">公式 {t.formula_id}</span>
                  )}
                  <span>{t.text.length} 字</span>
                </div>
                {t.rationale && (
                  <p className="text-xs text-zinc-500 mt-1.5">{t.rationale}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {publishing?.description && (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>简介</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans text-zinc-900 dark:text-zinc-100">
              {publishing.description}
            </pre>
          </CardContent>
        </Card>
      )}

      {publishing?.pinned_comment && (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>置顶评论（章节时间戳）</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm leading-relaxed font-mono text-zinc-900 dark:text-zinc-100">
              {publishing.pinned_comment}
            </pre>
          </CardContent>
        </Card>
      )}

      {video?.scenes && (
        <Card>
          <CardHeader>
            <CardTitle>Video JSON · {video.scenes.length} scenes</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {video.scenes.map((sc, i) => (
                <SceneItem key={i} idx={i} scene={sc} />
              ))}
            </ul>
            <details className="mt-4">
              <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-700 dark:hover:text-zinc-300">
                查看原始 JSON
              </summary>
              <div className="mt-2">
                <JsonBlock data={video} />
              </div>
            </details>
          </CardContent>
        </Card>
      )}

      {!video && !publishing && (
        <div className="rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 p-10 text-center">
          <p className="text-sm text-zinc-500">
            P4（video）和 P6（publishing）都还没产出
          </p>
        </div>
      )}
    </div>
  )
}

function SceneItem({ idx, scene }: { idx: number; scene: Scene }) {
  const ttsLen = scene.tts_text?.length ?? 0
  return (
    <li className="rounded-md border border-zinc-200 dark:border-zinc-800 p-3">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-xs font-mono text-zinc-400 w-6 shrink-0">#{idx + 1}</span>
        <Badge tone="neutral">{scene.scene_type || 'unknown'}</Badge>
        {scene.duration_seconds != null && (
          <span className="text-xs text-zinc-500">{scene.duration_seconds}s</span>
        )}
        {scene.tts_text && (
          <span className="text-xs text-zinc-400">tts {ttsLen} 字</span>
        )}
        {scene.chapter_number != null && (
          <Badge tone="info">第 {scene.chapter_number} 章 · {scene.chapter_title}</Badge>
        )}
      </div>
      {(scene.title || scene.subtitle || scene.main_text || scene.sub_text) && (
        <div className="space-y-1 mb-2">
          {scene.title && <p className="font-medium text-sm">{scene.title}</p>}
          {scene.subtitle && <p className="text-xs text-zinc-500">{scene.subtitle}</p>}
          {scene.main_text && <p className="text-sm text-zinc-800 dark:text-zinc-200">{scene.main_text}</p>}
          {scene.sub_text && <p className="text-xs text-zinc-500">{scene.sub_text}</p>}
        </div>
      )}
      {(scene.bullets || scene.cards) && (
        <ul className="text-xs text-zinc-700 dark:text-zinc-300 space-y-0.5 mb-2 list-disc list-inside">
          {(scene.bullets ?? scene.cards ?? []).map((b, j) => (
            <li key={j}>{b}</li>
          ))}
        </ul>
      )}
      {scene.tts_text && (
        <div className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-900 rounded p-2 border-l-2 border-zinc-300 dark:border-zinc-700">
          <span className="text-zinc-400 mr-1">🎤</span>
          {scene.tts_text}
        </div>
      )}
    </li>
  )
}

function DownloadButton({ data }: { data: { task_id: string; [k: string]: unknown } }) {
  const onClick = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.task_id}-export.json`
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <Button variant="outline" onClick={onClick}>
      <Download className="h-4 w-4" />
      下载 JSON
    </Button>
  )
}

function CopyIcon({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable; nothing else we can do */
    }
  }
  return (
    <button
      onClick={onClick}
      className="text-xs text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300 inline-flex items-center gap-1 shrink-0"
      title="复制"
    >
      <Copy className="h-3.5 w-3.5" />
      {copied ? '已复制' : '复制'}
    </button>
  )
}
