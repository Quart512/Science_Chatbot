"use client"

import { useLanguage } from "@/lib/i18n"
import { Logo } from "@/components/site/logo"
import { LangToggle } from "@/components/site/lang-toggle"

export function SiteFooter() {
  const { t } = useLanguage()

  return (
    <footer className="bg-background">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-5 py-12 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm">
          <Logo />
          <p className="mt-4 text-pretty text-sm leading-relaxed text-muted-foreground">
            {t("footer.tagline")}
          </p>
        </div>
        <div className="flex flex-col items-start gap-4">
          <LangToggle />
          <p className="font-mono text-xs text-muted-foreground">
            © {new Date().getFullYear()} AIsaac — {t("footer.rights")}
          </p>
        </div>
      </div>
    </footer>
  )
}
