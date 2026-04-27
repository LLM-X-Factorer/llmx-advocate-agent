import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { api } from '@/api/client'
import type { CreateTaskRequest } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input, Textarea } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Loader2, Upload } from 'lucide-react'

export function NewTaskPage() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [packContent, setPackContent] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: (req: CreateTaskRequest) => api.createTask(req),
    onSuccess: (detail) => {
      navigate(`/tasks/${detail.task.id}`)
    },
  })

  const inferTitle = (content: string): string => {
    const m = content.match(/^title:\s*(.+)$/m) || content.match(/^#\s+(.+)$/m)
    return m ? m[1].trim().replace(/^["']|["']$/g, '') : ''
  }

  const onFileSelected = async (file: File) => {
    if (!file.name.endsWith('.md') && !file.name.endsWith('.markdown')) {
      alert('请上传 .md 文件')
      return
    }
    const text = await file.text()
    setPackContent(text)
    setFileName(file.name)
    if (!title) setTitle(inferTitle(text) || file.name.replace(/\.(md|markdown)$/, ''))
  }

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFileSelected(f)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !packContent.trim()) return
    createMutation.mutate({
      title: title.trim(),
      source: { pack_path: null, pack_content: packContent },
      config: null,
      run_async: false,
    })
  }

  const canSubmit = title.trim() && packContent.trim() && !createMutation.isPending

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">新建任务</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          喂一个 source pack（markdown + YAML frontmatter）
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle>标题</CardTitle>
            <CardDescription>用户可识别的名称，建议从 pack 标题派生</CardDescription>
          </CardHeader>
          <CardContent>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例：DeepSeek-v4 推理范式拆解"
              required
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Source Pack 内容</CardTitle>
            <CardDescription>
              拖入 .md 文件 或 直接粘贴。Schema 见{' '}
              <a
                href="https://github.com/LLM-X-Factorer/llmx-advocate-agent/blob/main/docs/source-pack-schema.md"
                target="_blank"
                rel="noreferrer"
                className="text-violet-600 dark:text-violet-400 underline"
              >
                source-pack-schema.md
              </a>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
              className={cn(
                'rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer',
                isDragging
                  ? 'border-violet-500 bg-violet-50 dark:bg-violet-950/30'
                  : 'border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-600'
              )}
              onClick={() => document.getElementById('pack-file-input')?.click()}
            >
              <input
                id="pack-file-input"
                type="file"
                accept=".md,.markdown,text/markdown"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) onFileSelected(f)
                }}
              />
              <Upload className="h-6 w-6 mx-auto text-zinc-400 mb-2" />
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {fileName ? (
                  <span className="font-mono">{fileName}</span>
                ) : (
                  <>拖入 .md 文件，或 <span className="text-violet-600 dark:text-violet-400">点击选择</span></>
                )}
              </p>
            </div>

            <div className="text-xs text-zinc-500 dark:text-zinc-400">
              或直接粘贴：
            </div>
            <Textarea
              value={packContent}
              onChange={(e) => {
                setPackContent(e.target.value)
                if (!title) {
                  const t = inferTitle(e.target.value)
                  if (t) setTitle(t)
                }
              }}
              placeholder="---&#10;schema_version: &quot;1.0&quot;&#10;pack_id: ...&#10;source:&#10;  ..."
              rows={14}
              required
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {packContent.length.toLocaleString()} 字符
            </p>
          </CardContent>
        </Card>

        {createMutation.isError && (
          <div className="rounded-md border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/30 p-4">
            <p className="text-sm text-red-800 dark:text-red-300">
              提交失败：
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : String(createMutation.error)}
            </p>
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            提交后会同步运行直到 phase 卡住或完成（最多约 3-5 分钟）
          </p>
          <Button type="submit" disabled={!canSubmit}>
            {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            创建并运行
          </Button>
        </div>
      </form>
    </div>
  )
}
