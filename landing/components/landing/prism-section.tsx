"use client"

import { useLanguage } from "@/lib/i18n"
import type { TKey } from "@/lib/i18n"

// 08-08 — 밴드마다 달려 있던 "가시광선 대역"/"비가시 대역 · 자율 포착"/"발견"
// 부제를 없앴다. 다섯 갈래가 `PaperExtraction` 실제 필드로 바뀐 뒤로는 "핵심 주장이
// 가시광선 대역"이라는 말이 아무 뜻도 없고, "자율 포착"은 이번에 걷어내기로 한
// 자율 주장 그 자체다. 색 순서는 스펙트럼 순(빨강→보라)으로 맞춘다.
const bands: { key: TKey; color: string }[] = [
  { key: "prism.band.red", color: "var(--spectrum-red)" },
  { key: "prism.band.yellow", color: "var(--spectrum-yellow)" },
  { key: "prism.band.green", color: "var(--spectrum-green)" },
  { key: "prism.band.blue", color: "var(--spectrum-blue)" },
  { key: "prism.band.violet", color: "var(--spectrum-violet)" },
]

export function PrismSection() {
  const { t } = useLanguage()

  return (
    <section id="prism" className="scroll-mt-16 border-b border-border">
      <div className="relative mx-auto grid max-w-6xl gap-12 px-5 py-20 md:py-24 lg:grid-cols-2 lg:items-center">
        <div>
          {/* 08-08 후속(사용자 지적) — "프리즘"(컨셉)과 "논문 추출기"(실제 기능) 배지가
              서로 멀리 떨어져 있었다(배지가 desc 아래, kicker와 두 문단 거리). 둘이
              같은 것을 가리킨다는 게 한눈에 안 읽혀서 kicker 줄로 끌어올렸다 —
              히어로의 "골방 · 1665"처럼 컨셉 옆에 실체가 바로 붙는다. */}
          <div className="flex flex-wrap items-center gap-3">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">{t("prism.kicker")}</p>
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 font-mono text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
              {t("prism.feature")}
            </span>
          </div>
          <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("prism.title")}
          </h2>
          <p className="mt-5 max-w-lg text-pretty leading-relaxed text-muted-foreground">
            {t("prism.desc.a")}
            <br />
            {t("prism.desc.b")}
          </p>

          {/* 08-08 ④ — 이 목록은 오른쪽 칼럼에 있었는데, 거기가 재합성된 광선이
              궤도로 내려가는 길이라 **카드 사이 틈으로 광선이 토막토막 비쳤다**.
              스케치에서도 범례는 광선에서 떨어진 별도 칼럼이었다 — 텍스트 아래로 옮긴다.
              lg 이상에서는 다섯 갈래에 색으로 대응하는 범례가 되고(띠 옆에 글자를
              붙이면 서로 겹친다), lg 미만에서는 이게 이 섹션의 유일한 비주얼이다. */}
          <div className="mt-8 flex flex-col gap-2.5">
            {bands.map((b) => (
              <div
                key={b.key}
                className="group flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:border-accent/40"
              >
                <span
                  className="h-9 w-1 shrink-0 rounded-full"
                  style={{ backgroundColor: b.color }}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{t(b.key)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* lg 이상에서는 이 자리에 프리즘 두 개와 다섯 갈래가 그려진다(BeamScene). */}
        <div data-beam="prism" className="hidden aspect-[10/13] w-full lg:block" />
      </div>
    </section>
  )
}
