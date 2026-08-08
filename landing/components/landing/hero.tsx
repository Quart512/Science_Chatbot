"use client"

import { ArrowRight, Download } from "lucide-react"
import Link from "next/link"
import { useLanguage } from "@/lib/i18n"
import { buttonVariants } from "@/components/ui/button"
import { PrismVisual } from "@/components/landing/prism-visual"

// 08-08 — 3칸에서 2칸으로. "지원 플랫폼"은 다운로드 버튼 바로 위(CTA)로 옮겼다.
const metrics = [
  { labelKey: "hero.metric.1.label", valueKey: "hero.metric.1.value" },
  { labelKey: "hero.metric.2.label", valueKey: "hero.metric.2.value" },
] as const

export function Hero() {
  const { t } = useLanguage()

  return (
    <section className="relative overflow-hidden border-b border-border">
      <div className="pointer-events-none absolute inset-0 grid-graph opacity-40" aria-hidden="true" />
      <div className="relative mx-auto grid max-w-6xl gap-12 px-5 py-20 md:py-28 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
        <div className="flex flex-col items-start">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 font-mono text-xs text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
            {t("hero.status")}
          </span>

          {/* 08-08 — 두 줄이 한 문장("아이작 뉴턴의 1665년을 / 당신의 컴퓨터
              안에서.")이라 아랫줄만 흐리게 두면 문장이 끊겨 읽힌다. 옛 슬로건은
              3동사 + 별도 부제 구조여서 색을 달리한 것이었다. */}
          <h1 className="mt-6 text-balance text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            {t("hero.title.a")}
            <br />
            {t("hero.title.b")}
          </h1>

          <p className="mt-6 max-w-xl text-pretty leading-relaxed text-muted-foreground">
            {t("hero.desc")}
          </p>

          <p className="mt-4 font-mono text-sm text-muted-foreground/80">{t("hero.tagline")}</p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/download"
              className={buttonVariants({ size: "lg", className: "group rounded-full px-5" })}
            >
              <Download className="size-4" />
              {t("hero.cta.primary")}
              <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#orbit"
              className={buttonVariants({ variant: "outline", size: "lg", className: "rounded-full px-5" })}
            >
              {t("hero.cta.secondary")}
            </a>
          </div>

          <dl className="mt-12 grid w-full max-w-lg grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border">
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
          {/* 08-08 ④ — lg 이상에서는 이 자리를 광선 장면의 "골방"이 채운다(BeamScene이
              `data-beam`으로 이 박스를 재서 좌표를 잡는다). 박스는 자리만 잡고 그림은
              래퍼 뒤 SVG 레이어가 그린다 — 그래야 광선이 섹션 경계를 넘어 이어진다.
              lg 미만에서는 장면을 안 그리므로 원래 프리즘 카드를 그대로 쓴다. */}
          <div data-beam="room" className="hidden aspect-[4/5] w-full lg:block" />
          <div className="rounded-xl border border-border bg-card/60 p-4 backdrop-blur-sm lg:hidden">
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
