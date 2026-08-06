"use client"

import { useLanguage } from "@/lib/i18n"
import type { TKey } from "@/lib/i18n"

const bands: { key: TKey; color: string; visible: boolean }[] = [
  { key: "prism.band.violet", color: "var(--spectrum-violet)", visible: false },
  { key: "prism.band.blue", color: "var(--spectrum-blue)", visible: true },
  { key: "prism.band.green", color: "var(--spectrum-green)", visible: true },
  { key: "prism.band.yellow", color: "var(--spectrum-yellow)", visible: true },
  { key: "prism.band.red", color: "var(--spectrum-red)", visible: false },
]

export function PrismSection() {
  const { t, lang } = useLanguage()

  return (
    <section id="prism" className="scroll-mt-16 border-b border-border">
      <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 md:py-24 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-accent">{t("prism.kicker")}</p>
          <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("prism.title")}
          </h2>
          <p className="mt-5 max-w-lg text-pretty leading-relaxed text-muted-foreground">
            {t("prism.desc")}
          </p>
        </div>

        <div className="flex flex-col gap-2.5">
          {bands.map((b) => (
            <div
              key={b.key}
              className="group flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:border-accent/40"
            >
              <span
                className="h-9 w-1 shrink-0 rounded-full"
                style={{ backgroundColor: b.color }}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{t(b.key)}</p>
                <p className="font-mono text-[0.7rem] uppercase tracking-widest text-muted-foreground">
                  {b.visible
                    ? lang === "ko"
                      ? "가시광선 대역"
                      : "Visible band"
                    : lang === "ko"
                      ? "비가시 대역 · 자율 포착"
                      : "Invisible band · auto-captured"}
                </p>
              </div>
              {!b.visible && (
                <span className="shrink-0 rounded-full bg-accent/10 px-2 py-1 font-mono text-[0.6rem] uppercase tracking-widest text-accent">
                  {lang === "ko" ? "발견" : "Discovered"}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
