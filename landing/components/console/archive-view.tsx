"use client"

import { Moon } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { archive } from "@/lib/prism-data"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

// A waxing moon glyph representing paper completeness (phase 1..4 → full moon).
function MoonPhase({ phase }: { phase: 1 | 2 | 3 | 4 }) {
  const fill = (phase / 4) * 100
  return (
    <span className="relative inline-flex h-9 w-9 items-center justify-center" aria-hidden="true">
      <span className="absolute inset-0 rounded-full border border-border" />
      <span
        className="absolute inset-0 rounded-full"
        style={{
          background: "var(--accent)",
          clipPath: `inset(0 ${100 - fill}% 0 0)`,
          opacity: 0.85,
        }}
      />
      <Moon className="relative h-4 w-4 text-background mix-blend-difference" />
    </span>
  )
}

export function ArchiveView() {
  const { t, lang } = useLanguage()

  const phaseLabel = (phase: 1 | 2 | 3 | 4) => {
    const map: Record<number, string> = {
      1: t("dark.phase.1"),
      2: t("dark.phase.2"),
      3: t("dark.phase.3"),
      4: t("dark.phase.4"),
    }
    return map[phase]
  }

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">{t("console.archive.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("console.archive.desc")}</p>
      </header>

      <ul className="flex flex-col gap-3">
        {archive.map((item) => (
          <li
            key={item.id}
            className="flex items-center gap-4 rounded-2xl border border-border bg-card p-4 transition-colors hover:border-accent/50"
          >
            <MoonPhase phase={item.phase} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
                  {item.id}
                </span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 font-mono text-[0.6rem] uppercase tracking-widest",
                    item.phase === 4 ? "bg-accent/10 text-accent" : "bg-muted text-muted-foreground",
                  )}
                >
                  {phaseLabel(item.phase)}
                </span>
              </div>
              <p className="mt-1 truncate text-sm font-medium">{lang === "ko" ? item.titleKo : item.titleEn}</p>
              <p className="mt-0.5 font-mono text-[0.65rem] text-muted-foreground">
                {t("console.archive.updated")} {item.updated}
              </p>
            </div>
            <span className={buttonVariants({ variant: "outline", size: "sm", className: "rounded-full" })}>
              {t("console.archive.open")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
