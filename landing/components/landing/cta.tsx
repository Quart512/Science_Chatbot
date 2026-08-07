"use client"

import { ArrowRight, Download } from "lucide-react"
import Link from "next/link"
import { useLanguage } from "@/lib/i18n"
import { buttonVariants } from "@/components/ui/button"

export function CtaSection() {
  const { t } = useLanguage()

  return (
    <section className="border-b border-border">
      <div className="mx-auto max-w-6xl px-5 py-20 md:py-28">
        <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-10 md:p-16">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-1 spectrum-bar" aria-hidden="true" />
          <div className="max-w-2xl">
            <h2 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl md:text-5xl">
              {t("cta.title")}
            </h2>
            <p className="mt-5 text-pretty leading-relaxed text-muted-foreground">{t("cta.desc")}</p>
            <Link
              href="/download"
              className={buttonVariants({ size: "lg", className: "group mt-8 rounded-full px-6" })}
            >
              <Download className="size-4" />
              {t("cta.button")}
              <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}
