"use client"

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { buildScene, type Box, type Scene } from "@/lib/beam-geometry"

// 08-08 ④ — 스크롤이 곧 빛의 경로. 히어로(골방) → 프리즘 → 궤도를 한 줄기가 가로지른다.
// 카드 셋으로 끊기지 않는 한 줄기라 "3 컨셉과 3 서비스가 안 이어진다"를 시각 층위에서
// 직접 해소하는 게 목적이다(RoadMap "08-08 결론").
//
// 좌표는 각 섹션이 비워둔 앵커 박스(`data-beam="room|prism|orbit"`)를 런타임에 재서
// `lib/beam-geometry.ts`가 계산한다 — 스케치 좌표를 베끼면 KO/EN 카피 길이 차와
// 창 너비 변화에 바로 깨진다. 계산은 순수 함수로 빼두고 여기서는 측정과 그리기만 한다.
//
// lg 미만에서는 아예 안 그린다. 장면이 세로로 길어 좁은 화면에서는 도형이 뭉개지고,
// 각 섹션이 원래 갖고 있던 작은 비주얼이 그 자리를 대신한다.
const LG = 1024

// 스크롤 진행도(0~1) 구간 — 스케치의 배분을 그대로 옮겼다.
// [시작, 끝, 완료 후 흐려지는지]
const SEGMENTS: Record<string, [number, number, boolean]> = {
  beam: [0.0, 0.18, false],
  band0: [0.18, 0.4, false],
  band1: [0.18, 0.4, false],
  band2: [0.18, 0.4, false],
  band3: [0.18, 0.4, false],
  band4: [0.18, 0.4, false],
  descend: [0.4, 0.62, false],
  shot0: [0.62, 0.71, true],
  shot1: [0.71, 0.8, true],
  shot2: [0.8, 0.89, true],
  closed: [0.89, 1.0, false],
}

// 밴드 색은 프리즘 섹션의 범례와 같은 토큰을 쓴다 — 둘이 다른 색이면 범례가 범례가 아니다.
const BAND_COLORS = [
  "var(--spectrum-red)",
  "var(--spectrum-yellow)",
  "var(--spectrum-green)",
  "var(--spectrum-blue)",
  "var(--spectrum-violet)",
]

// 궤도 위 5단계 노드 색 = 궤도 섹션 목록의 점 색과 같은 순서(가설 수립 → 논문 초안).
// 08-08 후속 — orbit-section.tsx의 nodes와 같은 이유로 빨주노초파 순서로 맞췄다.
const STAGE_COLORS = [
  "var(--spectrum-red)",
  "var(--spectrum-orange)",
  "var(--spectrum-yellow)",
  "var(--spectrum-green)",
  "var(--spectrum-blue)",
]

const clamp = (v: number) => Math.max(0, Math.min(1, v))

function readBox(wrap: HTMLElement, name: string): Box | null {
  const el = wrap.querySelector<HTMLElement>(`[data-beam="${name}"]`)
  if (!el) return null
  const w = wrap.getBoundingClientRect()
  const r = el.getBoundingClientRect()
  return { x: r.left - w.left, y: r.top - w.top, w: r.width, h: r.height }
}

export function BeamScene({ wrapRef }: { wrapRef: React.RefObject<HTMLDivElement | null> }) {
  const [scene, setScene] = useState<Scene | null>(null)
  // path 하나당 전체 길이를 재둔다. stroke-dasharray를 길이만큼 주고 dashoffset을
  // 그 길이에서 0으로 줄이면 선이 그려지는 것처럼 보인다 — SVG의 표준 관용구다.
  const paths = useRef(new Map<string, SVGPathElement>())
  const lengths = useRef(new Map<string, number>())
  const stagesRef = useRef<SVGGElement | null>(null)

  const measure = useCallback(() => {
    const wrap = wrapRef.current
    if (!wrap) return
    if (window.innerWidth < LG) {
      setScene(null)
      return
    }
    const room = readBox(wrap, "room")
    const prism = readBox(wrap, "prism")
    const orbit = readBox(wrap, "orbit")
    if (!room || !prism || !orbit) return
    const r = wrap.getBoundingClientRect()
    setScene(buildScene(r.width, r.height, { room, prism, orbit }))
  }, [wrapRef])

  // `useLayoutEffect`가 아니라 `useEffect`여야 한다. React는 ref를 **자식부터** 붙이는데
  // `wrapRef`가 가리키는 div는 이 컴포넌트의 부모라, layout effect 시점엔 아직
  // `wrapRef.current`가 null이다 — 그러면 여기서 그냥 return해버려 ResizeObserver도
  // 영영 안 붙고 장면이 끝까지 안 그려진다(실제로 이 버그를 겪었다). passive effect는
  // 커밋이 다 끝난 뒤에 돌아서 부모 ref가 이미 붙어 있다.
  useEffect(() => {
    measure()
    const wrap = wrapRef.current
    if (!wrap) return
    // 카피 길이(KO/EN 전환)·폰트 로딩처럼 **내용 때문에** 높이가 바뀌는 건 ResizeObserver가,
    // 창 크기 변경은 resize 이벤트가 잡는다. 둘 다 건 이유: 검증 중에 이 브라우저 패널에서
    // 뷰포트를 줄였을 때 RO가 한 번도 안 불린 걸 확인했다(언어 전환에는 정상 동작).
    // 일반 브라우저면 RO만으로 충분하지만, 확인 못 한 경로에 장면 좌표를 걸어두지 않는다.
    const ro = new ResizeObserver(measure)
    ro.observe(wrap)
    window.addEventListener("resize", measure)
    return () => {
      ro.disconnect()
      window.removeEventListener("resize", measure)
    }
  }, [measure, wrapRef])

  // 진행도를 적용한다. 리렌더 없이 style만 건드린다 — 스크롤마다 React를 돌리면
  // 프레임을 흘린다.
  const render = useCallback(() => {
    const wrap = wrapRef.current
    if (!wrap || !scene) return
    const r = wrap.getBoundingClientRect()
    const startY = r.top + window.scrollY
    // 진행도는 **래퍼 자신의 위치**로 잰다. 스케치는 문서 전체 스크롤을 썼지만 실제
    // 페이지는 이 아래로 기능 섹션·CTA·푸터가 더 있어서, 문서 전체로 재면 궤도가
    // 페이지 맨 끝에 가서야 닫힌다.
    const span = r.height - window.innerHeight
    const p = span > 0 ? clamp((window.scrollY - startY) / span) : 1

    for (const [key, [s, e, fades]] of Object.entries(SEGMENTS)) {
      const el = paths.current.get(key)
      const len = lengths.current.get(key)
      if (!el || !len) continue
      const local = clamp((p - s) / (e - s))
      el.style.strokeDashoffset = String(len * (1 - local))
      // 떨어진 탄도는 지우지 않고 흐린 자국으로 남긴다 — 같은 대포를 속도를 올려가며
      // 다시 쏜 것이라는 게 자국으로 남아야 읽힌다.
      if (fades) el.style.opacity = String(1 - clamp((p - e) / 0.06) * 0.75)
    }
    // 궤도가 닫히고 나서야 단계가 올라온다
    if (stagesRef.current) stagesRef.current.style.opacity = String(clamp((p - 0.93) / 0.05))
  }, [scene, wrapRef])

  useLayoutEffect(() => {
    if (!scene) return
    for (const [key, el] of paths.current) {
      const len = el.getTotalLength()
      lengths.current.set(key, len)
      el.style.strokeDasharray = String(len)
      el.style.strokeDashoffset = String(len)
    }
    render()
  }, [scene, render])

  useEffect(() => {
    let ticking = false
    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        render()
        ticking = false
      })
    }
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [render])

  if (!scene) return null

  const ref = (key: string) => (el: SVGPathElement | null) => {
    if (el) paths.current.set(key, el)
    else paths.current.delete(key)
  }
  const u = scene.unit

  return (
    <svg
      aria-hidden="true"
      viewBox={scene.viewBox}
      preserveAspectRatio="xMidYMid meet"
      className="pointer-events-none absolute inset-0 -z-10 hidden h-full w-full lg:block"
    >
      <defs>
        <filter id="beam-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="5" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="beam-softglow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* ── 골방 ── */}
      <g fill="none" stroke="var(--border)" strokeWidth={2}>
        <rect x={scene.room.rect.x} y={scene.room.rect.y} width={scene.room.rect.w} height={scene.room.rect.h} rx={4} />
        <line x1={scene.room.wallX} y1={scene.room.wallY1} x2={scene.room.wallX} y2={scene.room.wallY2} />
      </g>
      <circle cx={scene.room.hole[0]} cy={scene.room.hole[1]} r={9} fill="var(--foreground)" filter="url(#beam-glow)" />

      {/* ── 창구멍 → 프리즘 ── */}
      <path
        ref={ref("beam")}
        d={scene.beam}
        fill="none"
        stroke="var(--foreground)"
        strokeWidth={3}
        strokeLinecap="round"
        filter="url(#beam-glow)"
      />

      {/* ── 프리즘 두 개 ── */}
      {scene.glass.map((d, i) => (
        <path key={`glass-${i}`} d={d} fill="var(--card)" stroke="var(--muted-foreground)" strokeWidth={2} />
      ))}
      {scene.bands.map((d, i) => (
        <path
          key={`band-${i}`}
          ref={ref(`band${i}`)}
          d={d}
          fill="none"
          stroke={BAND_COLORS[i]}
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}

      {/* ── 재합성된 흰 광선 → 포신 ── */}
      <path
        ref={ref("descend")}
        d={scene.descend}
        fill="none"
        stroke="var(--foreground)"
        strokeWidth={3}
        strokeLinecap="round"
        filter="url(#beam-glow)"
      />

      {/* ── 지구 · 산 · 대포 ── */}
      <circle cx={scene.earth.cx} cy={scene.earth.cy} r={scene.earth.r} fill="none" stroke="var(--border)" strokeWidth={2} />
      <path d={scene.mountain} fill="none" stroke="var(--border)" strokeWidth={2} />
      <rect
        x={scene.barrel.x}
        y={scene.barrel.y}
        width={scene.barrel.w}
        height={scene.barrel.h}
        rx={1.9 * u}
        fill="var(--card)"
        stroke="var(--muted-foreground)"
        strokeWidth={2}
      />
      <rect
        x={scene.muzzleCap.x}
        y={scene.muzzleCap.y}
        width={scene.muzzleCap.w}
        height={scene.muzzleCap.h}
        rx={0.4 * u}
        fill="var(--card)"
        stroke="var(--muted-foreground)"
        strokeWidth={2}
      />
      {/* 궤도의 중심 — 히어로 창구멍의 그 빛점을 되돌려 놓는다. 페이지 처음과 끝이
          같은 점으로 묶인다. */}
      <circle cx={scene.core[0]} cy={scene.core[1]} r={7} fill="var(--foreground)" filter="url(#beam-glow)" />

      {/* ── 탄도 3발 + 닫힌 궤도 ── */}
      {scene.shots.map((d, i) => (
        <path
          key={`shot-${i}`}
          ref={ref(`shot${i}`)}
          d={d}
          fill="none"
          stroke="var(--foreground)"
          strokeWidth={2.5}
          strokeLinecap="round"
          filter="url(#beam-softglow)"
        />
      ))}
      <path
        ref={ref("closed")}
        d={scene.closed}
        fill="none"
        stroke="var(--foreground)"
        strokeWidth={2.5}
        strokeLinecap="round"
        filter="url(#beam-softglow)"
      />

      {/* ── 궤도가 닫힌 뒤에야 떠오르는 워크플로우 5단계 ── */}
      <g ref={stagesRef} opacity={0}>
        {scene.stages.map((p, i) => (
          <circle key={`stage-${i}`} cx={p[0]} cy={p[1]} r={6} fill={STAGE_COLORS[i]} />
        ))}
      </g>
    </svg>
  )
}
