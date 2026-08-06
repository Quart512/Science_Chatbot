"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { FlaskConical, Orbit, Archive, Settings, ArrowLeft } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import type { TKey } from "@/lib/i18n"
import { cn } from "@/lib/utils"
import { Logo } from "@/components/site/logo"
import { LangToggle } from "@/components/site/lang-toggle"
import { ThemeToggle } from "@/components/console/theme-toggle"

const items: { key: TKey; href: string; icon: typeof FlaskConical }[] = [
  { key: "app.nav.workspace", href: "/console", icon: FlaskConical },
  { key: "app.nav.archive", href: "/console/archive", icon: Archive },
  { key: "app.nav.settings", href: "/console/settings", icon: Settings },
]

export function ConsoleShell({ children }: { children: ReactNode }) {
  const { t } = useLanguage()
  const pathname = usePathname()

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-sidebar md:flex">
        <div className="flex h-16 items-center border-b border-border px-5">
          <Link href="/">
            <Logo />
          </Link>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Console">
          {items.map((item) => {
            const active = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {t(item.key)}
              </Link>
            )
          })}
        </nav>

        <div className="border-t border-border p-3">
          <Link
            href="/"
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("app.back")}
          </Link>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between gap-4 border-b border-border bg-background/80 px-5 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <Orbit className="hidden h-5 w-5 text-accent sm:block" />
            <div>
              <h1 className="text-sm font-semibold leading-none">{t("app.header.title")}</h1>
              <p className="mt-1 hidden font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground sm:block">
                {t("app.header.subtitle")}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <LangToggle />
          </div>
        </header>

        {/* mobile nav */}
        <nav className="flex gap-1 overflow-x-auto border-b border-border bg-background p-2 md:hidden" aria-label="Console mobile">
          {items.map((item) => {
            const active = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs transition-colors",
                  active ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {t(item.key)}
              </Link>
            )
          })}
        </nav>

        <main className="flex-1 p-5 md:p-8">{children}</main>
      </div>
    </div>
  )
}
