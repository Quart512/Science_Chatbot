"use client"

import { useState } from "react"
import { ArrowRight, Check, Copy } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { SiteNav } from "@/components/landing/site-nav"
import { SiteFooter } from "@/components/landing/site-footer"
import { buttonVariants } from "@/components/ui/button"

// 08-09 재구성 — 터미널 설치(curl)가 파일 직접 다운로드보다 먼저 보여야 한다는
// 지적(사용자) 반영. 예전엔 이 페이지 최상단이 "OS별 큰 다운로드 버튼"이라 파일
// 직접 받기가 권장 경로처럼 보였다 — 실제 권장은 반대다(macOS 보안 경고가 curl
// 경로에선 아예 안 뜬다, scripts/install.sh 참고). 그래서 이 페이지는 터미널
// 설치 하나만 다루고, 파일 직접 받기 + OS별 보안 경고 넘기는 법은 /download/manual로
// 분리했다(lib/i18n.tsx의 같은 날짜 주석 참고).
const INSTALL_COMMAND =
  "curl -fsSL https://raw.githubusercontent.com/Quart512/AIsaac/main/scripts/install.sh | bash"
const INSTALL_SCRIPT_URL = "https://github.com/Quart512/AIsaac/blob/main/scripts/install.sh"

function InstallCommand() {
  const { t } = useLanguage()
  const [copied, setCopied] = useState(false)

  // navigator.clipboard(Clipboard API)는 "보안 컨텍스트"(HTTPS 또는 localhost)에서만
  // 존재한다 — 랜딩이 아직 도메인이 없어 HTTPS 없이 순수 HTTP로 서빙되는 동안은(08-06
  // RoadMap "도메인 사기" 항목, 무기한 연기) 실사용자에게 `navigator.clipboard` 자체가
  // undefined다. 그래서 버튼을 눌러도 조용히 아무 일도 안 일어났다(08-09 실사용자 보고
  // — .catch가 그 실패를 삼키고 있었다). HTTPS가 생길 때까지는 인프라를 바꾸는 대신,
  // 보안 컨텍스트 제약이 없는 옛 방식(document.execCommand)을 폴백으로 둔다 — deprecated
  // API지만 Chrome 등 주요 브라우저가 여전히 지원하고, HTTP 사이트의 복사 버튼에 흔히
  // 쓰이는 표준 우회다.
  const copyWithExecCommand = () => {
    const textarea = document.createElement("textarea")
    textarea.value = INSTALL_COMMAND
    textarea.style.position = "fixed" // 스크롤 위치가 안 튀도록 뷰포트 밖으로 안 밀어냄
    textarea.style.opacity = "0"
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const ok = document.execCommand("copy")
    document.body.removeChild(textarea)
    return ok
  }

  const copy = async () => {
    let ok = false
    try {
      await navigator.clipboard.writeText(INSTALL_COMMAND)
      ok = true
    } catch {
      ok = copyWithExecCommand()
    }
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
    // 둘 다 실패하면(아주 오래된 브라우저 등) 조용히 넘어간다 — 명령어 자체가 화면에
    // 그대로 보이므로 직접 선택해 복사하면 된다.
  }

  return (
    <div className="rounded-xl border border-border bg-card p-6 text-left">
      {/* 가로 스크롤은 코드에만 건다 — 바깥 flex에 걸면 복사 버튼까지 같이 밀려나가
          화면 밖으로 사라진다(08-09 실기 확인). min-w-0이 있어야 flex 자식이 실제로
          줄어들어 스크롤이 생긴다(기본값 min-width:auto는 내용 폭만큼 버틴다). */}
      <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
        <div className="min-w-0 flex-1 overflow-x-auto">
          <code className="whitespace-nowrap font-mono text-xs sm:text-sm">{INSTALL_COMMAND}</code>
        </div>
        <button
          type="button"
          onClick={copy}
          className={buttonVariants({ variant: "outline", size: "sm", className: "shrink-0 rounded-full" })}
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? t("download.cli.copied") : t("download.cli.copy")}
        </button>
      </div>

      <ul className="mt-5 space-y-2 text-pretty text-sm leading-relaxed text-muted-foreground">
        <li>· {t("download.cli.note1")}</li>
        <li>· {t("download.cli.note2")}</li>
        <li>· {t("download.cli.note3")}</li>
      </ul>

      <a
        href={INSTALL_SCRIPT_URL}
        target="_blank"
        rel="noreferrer noopener"
        className="mt-4 inline-block text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
      >
        {t("download.cli.inspect")} →
      </a>
    </div>
  )
}

export default function DownloadPage() {
  const { t } = useLanguage()

  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main>
        <section className="border-b border-border">
          <div className="mx-auto max-w-2xl px-5 py-16 text-center md:py-24">
            <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
              {t("download.title")}
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-pretty leading-relaxed text-muted-foreground">
              {t("download.subtitle")}
            </p>
          </div>
        </section>

        <section className="border-b border-border">
          <div className="mx-auto max-w-2xl px-5 py-12">
            <InstallCommand />
          </div>
        </section>

        <section>
          <div className="mx-auto max-w-2xl px-5 py-16 text-center md:py-20">
            <h2 className="text-xl font-semibold tracking-tight">{t("download.fallback.title")}</h2>
            <p className="mx-auto mt-3 max-w-md text-pretty leading-relaxed text-muted-foreground">
              {t("download.fallback.desc")}
            </p>
            <a
              href="/download/manual"
              className={buttonVariants({ variant: "outline", size: "lg", className: "group mt-6 rounded-full px-6" })}
            >
              {t("download.fallback.button")}
              <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
            </a>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
