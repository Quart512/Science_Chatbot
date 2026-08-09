"use client"

import { ArrowLeft, ArrowRight, Download as DownloadIcon } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { SiteNav } from "@/components/landing/site-nav"
import { SiteFooter } from "@/components/landing/site-footer"
import { buttonVariants } from "@/components/ui/button"
import { useDownloadUrl, useIsLikelyIntelMac, PLATFORMS, RELEASES_PAGE_URL } from "@/lib/download"

// 08-09 신설 — /download가 터미널 설치 전용으로 좁혀지면서(lib/i18n.tsx의 같은 날짜
// 주석 참고) 파일 직접 받기가 여기로 옮겨왔다. 이전엔 이 내용이 /download 최상단이라
// "권장 경로"처럼 보였는데, 실제 권장(macOS 보안 경고가 아예 안 뜨는 터미널 설치)보다
// 앞에 있던 게 문제였다 — 이제는 "터미널이 안 될 때 쓰는 대안"이라는 위치가 명확하다.
const detectedCtaKey = {
  macos: "download.cta.macos",
  windows: "download.cta.windows",
  linux: "download.cta.linux",
} as const

export default function ManualDownloadPage() {
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
              {t("download.manual.title")}
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-pretty leading-relaxed text-muted-foreground">
              {t("download.manual.subtitle")}
            </p>

            {/* Mac·Linux 사용자가 검색이나 직접 링크로 여기 바로 왔을 경우를 위한
                되돌아가기 안내 — Windows 사용자에겐 해당 없는 내용이라 강하게 안 밀고
                작은 링크로만 둔다. */}
            <a
              href="/download"
              className="mt-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
            >
              <ArrowLeft className="size-3.5" />
              {t("download.manual.backToCli")}
            </a>

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

        {/* 08-09 신설 — README.md "처음 실행할 때 뜨는 보안 경고 넘기기" 절의 요약.
            정본은 README/번들 안 README.txt이고, 여기는 "무엇을 왜 눌러야 하는지"만
            짧게 — 전체 스크린샷 단위 절차는 그쪽에 있다. */}
        <section className="border-b border-border">
          <div className="mx-auto max-w-4xl px-5 py-16 md:py-20">
            <h2 className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {t("download.caveats.title")}
            </h2>
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="font-semibold">{t("download.caveats.macos.title")}</h3>
                <p className="mt-2 text-pretty text-sm leading-relaxed text-muted-foreground">
                  {t("download.caveats.macos.body")}
                </p>
                <p className="mt-3 text-pretty text-sm leading-relaxed text-destructive">
                  {t("download.caveats.macos.warning")}
                </p>
              </div>
              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="font-semibold">{t("download.caveats.windows.title")}</h3>
                <p className="mt-2 text-pretty text-sm leading-relaxed text-muted-foreground">
                  {t("download.caveats.windows.body")}
                </p>
              </div>
              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="font-semibold">{t("download.caveats.linux.title")}</h3>
                <p className="mt-2 text-pretty text-sm leading-relaxed text-muted-foreground">
                  {t("download.caveats.linux.body")}
                </p>
              </div>
            </div>
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
