"use client"

import { ArrowRight, Download } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { buttonVariants } from "@/components/ui/button"
import { PrismVisual } from "@/components/landing/prism-visual"
import { useDownloadUrl } from "@/lib/download"

const metrics = [
  { labelKey: "hero.metric.1.label", valueKey: "hero.metric.1.value" },
  { labelKey: "hero.metric.2.label", valueKey: "hero.metric.2.value" },
  { labelKey: "hero.metric.3.label", valueKey: "hero.metric.3.value" },
] as const

export function Hero() {
  const { t } = useLanguage()
  const { url: downloadUrl } = useDownloadUrl()

  return (
    <section className="relative overflow-hidden border-b border-border">
      <div className="pointer-events-none absolute inset-0 grid-graph opacity-40" aria-hidden="true" />
      <div className="relative mx-auto grid max-w-6xl gap-12 px-5 py-20 md:py-28 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
        <div className="flex flex-col items-start">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 font-mono text-xs text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
            {t("hero.status")}
          </span>

          <h1 className="mt-6 text-balance text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            {t("hero.title.a")}
            <br />
            <span className="text-muted-foreground">{t("hero.title.b")}</span>
          </h1>

          <p className="mt-6 max-w-xl text-pretty leading-relaxed text-muted-foreground">
            {t("hero.desc")}
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a
              href={downloadUrl}
              className={buttonVariants({ size: "lg", className: "group rounded-full px-5" })}
            >
              <Download className="size-4" />
              {t("hero.cta.primary")}
              <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
            </a>
            <a
              href="#orbit"
              className={buttonVariants({ variant: "outline", size: "lg", className: "rounded-full px-5" })}
            >
              {t("hero.cta.secondary")}
            </a>
          </div>

          <dl className="mt-12 grid w-full max-w-lg grid-cols-3 gap-px overflow-hidden rounded-lg border border-border bg-border">
            {metrics.map((m) => (
              <div key={m.labelKey} className="bg-card p-4">
                <dt className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
                  {t(m.labelKey)}
                </dt>
                <dd className="mt-1 font-mono text-sm font-semibold">{t(m.valueKey)}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="relative">
          <div className="rounded-xl border border-border bg-card/60 p-4 backdrop-blur-sm">
            <div className="mb-3 flex items-center justify-between font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
              <span>{t("prism.beam.label")}</span>
              <span className="text-accent">λ 380–750nm</span>
            </div>
            <div className="aspect-[8/5] w-full">
              <PrismVisual />
            </div>
            <div className="mt-3 h-1 w-full rounded-full spectrum-bar" aria-hidden="true" />
          </div>
        </div>
      </div>
    </section>
  )
}
