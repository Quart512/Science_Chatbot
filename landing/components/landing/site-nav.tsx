"use client"

import Link from "next/link"
import { useLanguage } from "@/lib/i18n"
import { Logo } from "@/components/site/logo"
import { LangToggle } from "@/components/site/lang-toggle"
import { buttonVariants } from "@/components/ui/button"
import { REPO_URL } from "@/lib/download"

// lucide-react 1.17이 브랜드 로고 아이콘(GitHub 등)을 안 갖고 있어(트리쉐이킹
// 가능한 순수 도형 세트로 재편되며 빠진 듯) 직접 그린다 — 표준 GitHub 마크
// 한 경로(single path)뿐이라 별도 파일로 안 뽑고 여기 지역 컴포넌트로 둔다.
function GithubIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.09 3.29 9.4 7.86 10.93.58.11.79-.25.79-.56 0-.27-.01-1.17-.02-2.12-3.2.7-3.87-1.36-3.87-1.36-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.51-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.12 3.05.74.81 1.18 1.83 1.18 3.09 0 4.41-2.69 5.39-5.25 5.67.41.36.78 1.06.78 2.14 0 1.55-.01 2.79-.01 3.17 0 .31.21.68.8.56A10.99 10.99 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z" />
    </svg>
  )
}

export function SiteNav() {
  const { t } = useLanguage()

  // 08-07 — "/#prism" 형태로 홈 경로를 앞에 붙인다. 이 네비가 이제 /download에서도
  // 재사용되는데, 거기서 "#prism"만 쓰면 그 페이지 안에서 없는 id를 찾다가
  // 아무 일도 안 일어난다(같은 페이지 내 스크롤로만 해석되므로) — 항상 홈으로
  // 이동한 뒤 앵커로 스크롤하게 한다.
  const links: { key: Parameters<typeof t>[0]; href: string }[] = [
    { key: "nav.prism", href: "/#prism" },
    { key: "nav.orbit", href: "/#orbit" },
    { key: "nav.screens", href: "/#screens" },
  ]

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
        <Link href="/" aria-label="AIsaac home">
          <Logo />
        </Link>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="font-mono text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
            >
              {t(l.key)}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="GitHub"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <GithubIcon className="size-5" />
          </a>
          <LangToggle />
          <Link href="/download" className={buttonVariants({ size: "sm", className: "rounded-full" })}>
            {t("nav.launch")}
          </Link>
        </div>
      </div>
    </header>
  )
}
