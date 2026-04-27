import { Link, NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'

export function AppShell() {
  return (
    <div className="min-h-screen flex flex-col bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            llmx-advocate
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <NavItem to="/">任务</NavItem>
            <NavItem to="/new">新建</NavItem>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          'px-3 py-1.5 rounded-md transition-colors',
          isActive
            ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100'
            : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
        )
      }
    >
      {children}
    </NavLink>
  )
}
