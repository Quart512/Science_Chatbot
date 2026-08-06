"use client"

import { Languages, SunMoon, Check } from "lucide-react"
import { useLanguage, type Lang } from "@/lib/i18n"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"

function OptionRow({
  selected,
  label,
  hint,
  onClick,
}: {
  selected: boolean
  label: string
  hint?: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "flex items-center justify-between rounded-xl border px-4 py-3 text-left transition-colors",
        selected ? "border-accent bg-accent/10" : "border-border bg-background hover:bg-muted",
      )}
    >
      <span>
        <span className="text-sm font-medium">{label}</span>
        {hint && <span className="ml-2 font-mono text-xs text-muted-foreground">{hint}</span>}
      </span>
      {selected && <Check className="h-4 w-4 text-accent" />}
    </button>
  )
}

export function SettingsView() {
  const { t, lang, setLang } = useLanguage()
  const { theme, setTheme } = useTheme()

  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-8">
        <h1 className="text-xl font-semibold tracking-tight">{t("settings.title")}</h1>
      </header>

      <div className="flex flex-col gap-8">
        {/* Language */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <Languages className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold">{t("settings.language.title")}</h2>
          </div>
          <p className="mb-3 text-sm text-muted-foreground">{t("settings.language.desc")}</p>
          <div className="grid grid-cols-2 gap-3">
            {(
              [
                { code: "ko" as Lang, label: "한국어", hint: "KO" },
                { code: "en" as Lang, label: "English", hint: "EN" },
              ]
            ).map((o) => (
              <OptionRow
                key={o.code}
                selected={lang === o.code}
                label={o.label}
                hint={o.hint}
                onClick={() => setLang(o.code)}
              />
            ))}
          </div>
        </section>

        {/* Theme */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <SunMoon className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold">{t("settings.theme.title")}</h2>
          </div>
          <p className="mb-3 text-sm text-muted-foreground">{t("settings.theme.desc")}</p>
          <div className="grid grid-cols-2 gap-3">
            <OptionRow
              selected={theme === "light"}
              label={t("settings.theme.light")}
              onClick={() => setTheme("light")}
            />
            <OptionRow
              selected={theme === "dark"}
              label={t("settings.theme.dark")}
              onClick={() => setTheme("dark")}
            />
          </div>
        </section>
      </div>
    </div>
  )
}
