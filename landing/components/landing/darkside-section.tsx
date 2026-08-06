"use client"

import { useLanguage } from "@/lib/i18n"
import type { TKey } from "@/lib/i18n"

function litPath(cx: number, cy: number, r: number, illum: number) {
  const t = 1 - 2 * illum
  const rx = r * Math.abs(t)
  const sweep = illum > 0.5 ? 1 : 0
  return `M ${cx},${cy - r} A ${r},${r} 0 0 1 ${cx},${cy + r} A ${rx},${r} 0 0 ${sweep} ${cx},${cy - r} Z`
}

function Moon({ illum }: { illum: number }) {
  const r = 26
  const c = 32
  return (
    <svg aria-hidden="true" viewBox="0 0 64 64" className="h-14 w-14">
      <circle cx={c} cy={c} r={r} className="fill-muted stroke-border" strokeWidth="1" />
      <path d={litPath(c, c, r, illum)} fill="currentColor" className="text-foreground" />
    </svg>
  )
}

const phases: { key: TKey; illum: number; index: string }[] = [
  { key: "dark.phase.1", illum: 0.04, index: "◑ 00" },
  { key: "dark.phase.2", illum: 0.32, index: "◑ 33" },
  { key: "dark.phase.3", illum: 0.66, index: "◑ 71" },
  { key: "dark.phase.4", illum: 1, index: "● 100" },
]

export function DarkSideSection() {
  const { t } = useLanguage()

  return (
    <section id="darkside" className="scroll-mt-16 border-b border-border">
      <div className="mx-auto max-w-6xl px-5 py-20 md:py-24">
        <div className="max-w-2xl">
          <p className="font-mono text-xs uppercase tracking-widest text-accent">{t("dark.kicker")}</p>
          <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("dark.title")}
          </h2>
          <p className="mt-5 text-pretty leading-relaxed text-muted-foreground">{t("dark.desc")}</p>
        </div>

        <ol className="mt-12 grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {phases.map((p) => (
            <li key={p.key} className="flex flex-col gap-4 bg-card p-6">
              <Moon illum={p.illum} />
              <div>
                <p className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
                  {p.index}
                </p>
                <p className="mt-1 font-medium">{t(p.key)}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
