"use client"

import { useState } from "react"
import { Sparkles, ChevronRight, Eye, EyeOff } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { bands, stages } from "@/lib/prism-data"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function Workspace() {
  const { t } = useLanguage()
  const [value, setValue] = useState("")
  const [subject, setSubject] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)

  function run() {
    const trimmed = value.trim()
    if (!trimmed || processing) return
    setProcessing(true)
    setSubject(null)
    // Simulate the prism refraction pass.
    setTimeout(() => {
      setSubject(trimmed)
      setProcessing(false)
    }, 1100)
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1.5fr_1fr]">
      {/* Left column: input + spectrum */}
      <div className="flex flex-col gap-6">
        {/* White beam input */}
        <section className="rounded-2xl border border-border bg-card p-5">
          <div className="mb-3 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-foreground" aria-hidden="true" />
            <h2 className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {t("console.input.title")}
            </h2>
          </div>
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing && e.keyCode !== 229) {
                e.preventDefault()
                run()
              }
            }}
            rows={3}
            placeholder={t("console.input.placeholder")}
            className="w-full resize-none rounded-xl border border-border bg-background p-3 text-sm leading-relaxed outline-none ring-accent/40 transition focus:ring-2"
          />
          <div className="mt-3 flex justify-end">
            <Button onClick={run} disabled={!value.trim() || processing} className="rounded-full">
              <Sparkles className="h-4 w-4" />
              {processing ? t("console.input.processing") : t("console.input.button")}
            </Button>
          </div>
        </section>

        {/* Spectrum output */}
        <section className="rounded-2xl border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {t("console.spectrum.title")}
            </h2>
            {subject && (
              <span className="max-w-[55%] truncate font-mono text-xs text-muted-foreground">
                {t("console.spectrum.subject")}: {subject}
              </span>
            )}
          </div>

          {/* spectrum bar */}
          <div className="mb-5 flex h-2 overflow-hidden rounded-full" aria-hidden="true">
            {bands.map((b) => (
              <span
                key={b.key}
                className={cn("flex-1 transition-opacity duration-700", subject ? "opacity-100" : "opacity-25")}
                style={{ background: b.colorVar }}
              />
            ))}
          </div>

          {!subject && !processing && (
            <p className="py-8 text-center text-sm text-muted-foreground">{t("console.spectrum.empty")}</p>
          )}

          {processing && (
            <div className="space-y-2 py-2" aria-hidden="true">
              {bands.map((b) => (
                <div key={b.key} className="h-14 animate-pulse rounded-xl bg-muted" />
              ))}
            </div>
          )}

          {subject && !processing && (
            <ul className="space-y-2">
              {bands.map((b, i) => (
                <li
                  key={b.key}
                  className="flex items-start gap-3 rounded-xl border border-border bg-background p-3"
                  style={{ animation: `fadein .4s ease ${i * 80}ms both` }}
                >
                  <span
                    className="mt-1 h-8 w-1 shrink-0 rounded-full"
                    style={{ background: b.colorVar }}
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold">{t(b.labelKey)}</p>
                      {b.hidden && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 font-mono text-[0.6rem] uppercase tracking-widest text-accent">
                          <EyeOff className="h-3 w-3" />
                          {t("band.hidden")}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t(b.descKey)}</p>
                    <div className="mt-2 flex items-center gap-2">
                      <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                        <span
                          className="block h-full rounded-full"
                          style={{ width: `${b.confidence}%`, background: b.colorVar }}
                        />
                      </div>
                      <span className="font-mono text-[0.65rem] text-muted-foreground">
                        {t("console.spectrum.confidence")} {b.confidence}%
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* Right column: orbit status */}
      <aside className="flex flex-col gap-6">
        <section className="rounded-2xl border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {t("console.orbit.title")}
            </h2>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[0.65rem] uppercase tracking-widest",
                processing || subject ? "bg-accent/10 text-accent" : "bg-muted text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  processing || subject ? "animate-pulse bg-accent" : "bg-muted-foreground",
                )}
              />
              {processing || subject ? t("console.orbit.running") : t("console.orbit.idle")}
            </span>
          </div>

          <ol className="relative ml-3 border-l border-border">
            {stages.map((s) => {
              const active = s.status === "active"
              const done = s.status === "done"
              return (
                <li key={s.key} className="relative py-3 pl-6">
                  <span
                    className={cn(
                      "absolute -left-[7px] top-4 h-3 w-3 rounded-full border-2 border-background",
                      done && "bg-spectrum-green",
                      active && "animate-pulse bg-accent",
                      s.status === "queued" && "bg-muted",
                    )}
                    style={done ? { background: "var(--spectrum-green)" } : undefined}
                    aria-hidden="true"
                  />
                  <div className="flex items-center justify-between">
                    <span className={cn("text-sm", active ? "font-semibold" : "text-muted-foreground")}>
                      {t(s.labelKey)}
                    </span>
                    <span className="font-mono text-[0.6rem] uppercase tracking-widest text-muted-foreground">
                      {done ? t("stage.done") : active ? t("stage.active") : t("stage.queued")}
                    </span>
                  </div>
                </li>
              )
            })}
          </ol>

          <div className="mt-4 flex items-center gap-2 rounded-xl bg-muted/60 p-3 text-xs text-muted-foreground">
            <Eye className="h-4 w-4 shrink-0 text-accent" />
            <p className="leading-relaxed">{t("orbit.loop")}</p>
          </div>
        </section>

        <a
          href="/console/archive"
          className="group flex items-center justify-between rounded-2xl border border-border bg-card p-5 transition-colors hover:border-accent/50"
        >
          <div>
            <p className="text-sm font-semibold">{t("app.nav.archive")}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t("console.archive.desc")}</p>
          </div>
          <ChevronRight className="h-5 w-5 text-muted-foreground transition-transform group-hover:translate-x-1" />
        </a>
      </aside>
    </div>
  )
}
