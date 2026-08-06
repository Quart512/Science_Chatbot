"use client"

import Link from "next/link"
import { useLanguage } from "@/lib/i18n"
import { Logo } from "@/components/site/logo"
import { LangToggle } from "@/components/site/lang-toggle"
import { buttonVariants } from "@/components/ui/button"
import { useDownloadUrl } from "@/lib/download"

export function SiteNav() {
  const { t } = useLanguage()
  const { url: downloadUrl } = useDownloadUrl()

  const links: { key: Parameters<typeof t>[0]; href: string }[] = [
    { key: "nav.prism", href: "#prism" },
    { key: "nav.orbit", href: "#orbit" },
    { key: "nav.darkside", href: "#darkside" },
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
          <LangToggle />
          <a href={downloadUrl} className={buttonVariants({ size: "sm", className: "rounded-full" })}>
            {t("nav.launch")}
          </a>
        </div>
      </div>
    </header>
  )
}
