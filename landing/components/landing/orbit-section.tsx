"use client"

import { useLanguage } from "@/lib/i18n"
import type { TKey } from "@/lib/i18n"

const nodes: { key: TKey; r: number; color: string; dur: string; from: number }[] = [
  { key: "orbit.node.1", r: 52, color: "var(--spectrum-violet)", dur: "12s", from: 0 },
  { key: "orbit.node.2", r: 78, color: "var(--spectrum-blue)", dur: "18s", from: 90 },
  { key: "orbit.node.3", r: 104, color: "var(--spectrum-green)", dur: "24s", from: 200 },
  { key: "orbit.node.4", r: 130, color: "var(--spectrum-orange)", dur: "30s", from: 300 },
]

function OrbitVisual() {
  const c = 160
  return (
    <svg aria-hidden="true" viewBox="0 0 320 320" className="h-full w-full">
      {nodes.map((n) => (
        <circle
          key={`ring-${n.r}`}
          cx={c}
          cy={c}
          r={n.r}
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          className="text-border"
        />
      ))}

      {/* gravity well core */}
      <circle cx={c} cy={c} r="26" fill="var(--card)" stroke="currentColor" strokeWidth="1.25" className="text-foreground" />
      <circle cx={c} cy={c} r="4" fill="var(--accent)">
        <animate attributeName="r" values="3;6;3" dur="2.5s" repeatCount="indefinite" />
      </circle>

      {nodes.map((n) => (
        <g key={`node-${n.r}`}>
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`${n.from} ${c} ${c}`}
            to={`${n.from + 360} ${c} ${c}`}
            dur={n.dur}
            repeatCount="indefinite"
          />
          <circle cx={c + n.r} cy={c} r="5.5" fill={n.color} />
        </g>
      ))}
    </svg>
  )
}

export function OrbitSection() {
  const { t } = useLanguage()

  return (
    <section id="orbit" className="scroll-mt-16 border-b border-border bg-secondary/40">
      <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 md:py-24 lg:grid-cols-2 lg:items-center">
        <div className="relative order-2 lg:order-1">
          <div className="mx-auto aspect-square w-full max-w-md">
            <OrbitVisual />
          </div>
          <ul className="mt-6 grid grid-cols-2 gap-2.5">
            {nodes.map((n) => (
              <li
                key={n.key}
                className="flex items-center gap-2.5 rounded-lg border border-border bg-card px-3 py-2 font-mono text-xs"
              >
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: n.color }} aria-hidden="true" />
                {t(n.key)}
              </li>
            ))}
          </ul>
        </div>

        <div className="order-1 lg:order-2">
          <p className="font-mono text-xs uppercase tracking-widest text-accent">{t("orbit.kicker")}</p>
          <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("orbit.title")}
          </h2>
          <p className="mt-5 max-w-lg text-pretty leading-relaxed text-muted-foreground">
            {t("orbit.desc")}
          </p>
          <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 font-mono text-xs text-muted-foreground">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden="true" />
            {t("orbit.loop")}
          </div>
        </div>
      </div>
    </section>
  )
}
