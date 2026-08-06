"use client"

import { useLanguage } from "@/lib/i18n"
import { cn } from "@/lib/utils"

export function LangToggle({ className }: { className?: string }) {
  const { lang, setLang } = useLanguage()
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-border bg-card p-0.5 font-mono text-xs",
        className,
      )}
      role="group"
      aria-label="Language"
    >
      {(["ko", "en"] as const).map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => setLang(code)}
          aria-pressed={lang === code}
          className={cn(
            "rounded-full px-2.5 py-1 uppercase tracking-widest transition-colors",
            lang === code
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {code}
        </button>
      ))}
    </div>
  )
}
