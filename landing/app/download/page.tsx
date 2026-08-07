"use client"

import { ArrowRight, Download as DownloadIcon } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { SiteNav } from "@/components/landing/site-nav"
import { SiteFooter } from "@/components/landing/site-footer"
import { buttonVariants } from "@/components/ui/button"
import { useDownloadUrl, useIsLikelyIntelMac, PLATFORMS, RELEASES_PAGE_URL } from "@/lib/download"

// 08-07 신설 — 사용자 요청으로 hero·nav·CTA의 다운로드 버튼이 zip을 바로 받는
// 대신 이 페이지로 먼저 오게 함. 감지된 OS용 버튼을 크게 하나 보여주고, 그 아래
// 4개 플랫폼 전체와 GitHub Releases(이전 버전) 링크를 둔다 — RoadMap "portable
// 파이썬 번들" 항목 실측대로 macOS는 Apple Silicon 전용·Windows/Linux는 x86_64
// 전용이라, 자동 감지가 틀렸을 때(특히 Intel Mac) 안 도는 파일을 주지 않도록
// 정적 안내문 + 최선-노력 Client Hints 경고를 같이 둔다.
const detectedCtaKey = {
  macos: "download.cta.macos",
  windows: "download.cta.windows",
  linux: "download.cta.linux",
} as const

export default function DownloadPage() {
  const { t } = useLanguage()
  const { url: detectedUrl, platform } = useDownloadUrl()
  const isLikelyIntelMac = useIsLikelyIntelMac()

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main>
        <section className="border-b border-border">
          <div className="mx-auto max-w-3xl px-5 py-16 text-center md:py-24">
            <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
              {t("download.title")}
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-pretty leading-relaxed text-muted-foreground">
              {t("download.subtitle")}
            </p>

            <div className="mt-10 flex flex-col items-center gap-3">
              {platform ? (
                <a
                  href={detectedUrl}
                  className={buttonVariants({ size: "lg", className: "group rounded-full px-8 text-base" })}
                >
                  <DownloadIcon className="size-4" />
                  {t(detectedCtaKey[platform])}
                  <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
                </a>
              ) : (
                <p className="font-mono text-sm text-muted-foreground">{t("download.detected.none")}</p>
              )}

              {isLikelyIntelMac && (
                <p className="max-w-md text-pretty text-sm text-destructive">{t("download.intel.warning")}</p>
              )}
            </div>
          </div>
        </section>

        <section className="border-b border-border">
          <div className="mx-auto max-w-4xl px-5 py-16 md:py-20">
            <h2 className="text-center font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {t("download.all.title")}
            </h2>

            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {PLATFORMS.map((p) => (
                <a
                  key={p.id}
                  href={p.url}
                  className="flex flex-col items-start gap-3 rounded-xl border border-border bg-card p-5 transition-colors hover:border-accent"
                >
                  <div className="font-semibold">{t(p.labelKey as Parameters<typeof t>[0])}</div>
                  <div className="font-mono text-xs text-muted-foreground">
                    {t(p.archKey as Parameters<typeof t>[0])}
                  </div>
                  <span className={buttonVariants({ variant: "outline", size: "sm", className: "mt-1 rounded-full" })}>
                    <DownloadIcon className="size-3.5" />
                    {t("download.card.button")}
                  </span>
                </a>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-border">
          <div className="mx-auto max-w-4xl px-5 py-16 md:py-20">
            <h2 className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {t("download.install.title")}
            </h2>
            <ol className="mt-4 space-y-2 text-pretty leading-relaxed text-muted-foreground">
              <li>1. {t("download.install.step1")}</li>
              <li>2. {t("download.install.step2")}</li>
              <li>3. {t("download.install.step3")}</li>
            </ol>
          </div>
        </section>

        <section>
          <div className="mx-auto max-w-4xl px-5 py-16 text-center md:py-20">
            <h2 className="text-xl font-semibold tracking-tight">{t("download.older.title")}</h2>
            <p className="mx-auto mt-3 max-w-md text-pretty leading-relaxed text-muted-foreground">
              {t("download.older.desc")}
            </p>
            <a
              href={RELEASES_PAGE_URL}
              target="_blank"
              rel="noreferrer"
              className={buttonVariants({ variant: "outline", size: "lg", className: "mt-6 rounded-full px-6" })}
            >
              {t("download.older.button")}
            </a>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
