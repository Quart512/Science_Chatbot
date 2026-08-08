"use client"

import { useLanguage } from "@/lib/i18n"
import type { TKey } from "@/lib/i18n"

// 08-08 — 지어낸 4단계(자료 수집·분석·정리·검증)를 실제 연구 워크플로우 5단계로
// 교체. 링 반지름은 5개가 들어가도록 26씩 좁혔다.
// 08-08 후속(사용자 지적) — 색을 "빨주노초파"(무지개 순서)로 바꿨다. 원래
// 보라→파랑→초록→노랑→주황이었는데(스펙트럼 파장순으로는 맞지만 빨강에서
// 시작하는 익숙한 무지개 읽기와 반대 방향이라 헷갈렸다) 목록이 2열이던 시절엔
// 순서가 눈에 안 들어와 괜찮았지만, 한 줄로 펼치니 바로 티가 났다.
// `beam-scene.tsx`의 `STAGE_COLORS`도 같은 5단계를 궤도 위에 점으로 찍으므로
// 반드시 같은 순서로 맞춰야 한다 — 둘이 다른 색이면 랜딩과 광선 장면이 서로
// 다른 걸 그리는 것처럼 보인다.
const nodes: { key: TKey; r: number; color: string; dur: string; from: number }[] = [
  { key: "orbit.node.1", r: 46, color: "var(--spectrum-red)", dur: "12s", from: 0 },
  { key: "orbit.node.2", r: 67, color: "var(--spectrum-orange)", dur: "16s", from: 72 },
  { key: "orbit.node.3", r: 88, color: "var(--spectrum-yellow)", dur: "20s", from: 144 },
  { key: "orbit.node.4", r: 109, color: "var(--spectrum-green)", dur: "25s", from: 216 },
  { key: "orbit.node.5", r: 130, color: "var(--spectrum-blue)", dur: "30s", from: 288 },
]

function OrbitVisual() {
  const c = 160
  return (
    <svg aria-hidden="true" viewBox="0 0 320 320" className="h-full w-full">
      {nodes.map((n) => (
        <circle
          key={`ring-${n.r}`}
          cx={c}
          cy={c}
          r={n.r}
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          className="text-border"
        />
      ))}

      {/* gravity well core */}
      <circle cx={c} cy={c} r="26" fill="var(--card)" stroke="currentColor" strokeWidth="1.25" className="text-foreground" />
      <circle cx={c} cy={c} r="4" fill="var(--accent)">
        <animate attributeName="r" values="3;6;3" dur="2.5s" repeatCount="indefinite" />
      </circle>

      {nodes.map((n) => (
        <g key={`node-${n.r}`}>
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`${n.from} ${c} ${c}`}
            to={`${n.from + 360} ${c} ${c}`}
            dur={n.dur}
            repeatCount="indefinite"
          />
          <circle cx={c + n.r} cy={c} r="5.5" fill={n.color} />
        </g>
      ))}
    </svg>
  )
}

export function OrbitSection() {
  const { t } = useLanguage()

  return (
    // 08-08 ④ — `bg-secondary/40`을 뺐다. 광선 장면이 래퍼 뒤 한 장으로 깔리는데
    // 섹션에만 반투명 배경이 있으면 그 구간에서 광선이 뿌옇게 뜬다. 히어로부터
    // 궤도까지 한 무대(딥 블랙)여야 "끊기지 않는 한 줄기"가 성립한다.
    <section id="orbit" className="scroll-mt-16 border-b border-border">
      <div className="relative mx-auto grid max-w-6xl gap-12 px-5 py-20 md:py-24 lg:grid-cols-2 lg:items-center">
        {/* min-w-0 — 노드 목록을 한 줄로 편 뒤 겪은 버그: 이게 없으면 그리드 칸의
            최소 폭이 flex 목록의 min-content(안 접히는 한 줄 전체 폭)로 잡혀서
            페이지 전체가 가로로 늘어난다 — screens-section.tsx와 같은 원인. */}
        <div className="relative order-2 min-w-0 lg:order-1">
          {/* lg 이상에서는 이 자리를 대포·탄도·닫힌 궤도가 채운다. */}
          <div data-beam="orbit" className="mx-auto hidden aspect-square w-full max-w-md lg:block" />
          <div className="mx-auto aspect-square w-full max-w-md lg:hidden">
            <OrbitVisual />
          </div>
          {/* 08-08 후속(사용자 지적) — 2열 그리드는 5개가 안 맞아떨어져 마지막 한 줄이
              혼자 남았다. 세로 공간이 없으니 한 줄로: `overflow-x-auto`는 화면이
              좁을 때만 스크롤이 생기는 안전장치고(화면 섹션의 탭 줄과 같은 처리),
              보통 폭에서는 5개가 그냥 한 줄에 다 들어간다. */}
          <ul className="mt-6 flex gap-2 overflow-x-auto pb-1">
            {nodes.map((n) => (
              <li
                key={n.key}
                className="flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-border bg-card px-3 py-2 font-mono text-xs"
              >
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: n.color }} aria-hidden="true" />
                {t(n.key)}
              </li>
            ))}
          </ul>
        </div>

        <div className="order-1 lg:order-2">
          {/* 08-08 후속(사용자 지적) — 프리즘과 같은 이유로 "궤도"·"연구 워크플로우"
              배지를 kicker 줄로 끌어올렸다. */}
          <div className="flex flex-wrap items-center gap-3">
            <p className="font-mono text-xs uppercase tracking-widest text-accent">{t("orbit.kicker")}</p>
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 font-mono text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden="true" />
              {t("orbit.loop")}
            </span>
          </div>
          <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("orbit.title")}
          </h2>
          <p className="mt-5 max-w-lg text-pretty leading-relaxed text-muted-foreground">
            {t("orbit.desc")}
          </p>
        </div>
      </div>
    </section>
  )
}
