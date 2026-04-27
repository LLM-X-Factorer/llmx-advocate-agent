import { cn } from '@/lib/utils'

export function JsonBlock({ data, className }: { data: unknown; className?: string }) {
  return (
    <pre
      className={cn(
        'text-xs leading-relaxed rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 overflow-auto max-h-[60vh]',
        className
      )}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}
