"use client"

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
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

// 08-08 후속(사용자 지적 — "빛 그려지는 지점이 화면 아래에 치우친다") — 예전엔 이
// 구간을 스케치(고정 1000×2880 레이아웃)의 배분 그대로 하드코딩해뒀다. 뷰포트 중앙
// 기준으로 진행도를 재도(아래 render() 참고) "지금 화면 중앙이 가리키는 지점"과
// "지금 실제로 그려지는 지점"이 안 맞았던 진짜 이유가 이거였다 — 프리즘 분산은
// p=0.18~0.40에 그리도록 돼 있었는데 실측 프리즘 박스는 p=0.373~0.664에 있었다.
// 그래서 각 조각을 **실제 앵커 박스 위치**(scene.sectionsY, 매 리사이즈·언어 전환마다
// 다시 잰 값)에서 계산한다 — 구간이 항상 그 조각이 실제로 그려지는 자리와 맞아떨어진다.
// 탄도 3발+닫힌 궤도의 상대 비율(궤도 구간을 23.7/23.7/23.7/28.9%로 나누는 것)만
// 스케치 배분을 그대로 유지한다 — 그건 위치가 아니라 "같은 대포를 점점 빠르게 다시
// 쏜다"는 서사 배분이라 실측과 무관하다.
function buildSegments(scene: Scene): Record<string, [number, number, boolean]> {
  const { room, prism, orbit } = scene.sectionsY
  // 창구멍(대략 room 구간의 중간)에서 프리즘 입사까지.
  const beamStart = room[0] + (room[1] - room[0]) * 0.5
  const beamEnd = prism[0]
  const bandsStart = prism[0]
  const bandsEnd = prism[1]
  const descendStart = prism[1]
  const descendEnd = orbit[0]
  const orbitStart = orbit[0]
  const orbitEnd = orbit[1]
  const orbitSpan = orbitEnd - orbitStart
  // 옛 배분(0.62~1.00, 전체 0.38)에서 탄도 3발이 각 23.7%, 닫힌 궤도가 28.9%를 썼다.
  const shot0End = orbitStart + orbitSpan * 0.237
  const shot1End = orbitStart + orbitSpan * 0.474
  const shot2End = orbitStart + orbitSpan * 0.711

  return {
    beam: [beamStart, beamEnd, false],
    band0: [bandsStart, bandsEnd, false],
    band1: [bandsStart, bandsEnd, false],
    band2: [bandsStart, bandsEnd, false],
    band3: [bandsStart, bandsEnd, false],
    band4: [bandsStart, bandsEnd, false],
    descend: [descendStart, descendEnd, false],
    shot0: [orbitStart, shot0End, true],
    shot1: [shot0End, shot1End, true],
    shot2: [shot1End, shot2End, true],
    closed: [shot2End, orbitEnd, false],
  }
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
  // scene(=측정 결과)이 바뀔 때만 다시 계산하면 된다 — 스크롤마다 새로 만들 이유가 없다.
  const segments = useMemo(() => (scene ? buildSegments(scene) : null), [scene])
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
    if (!wrap || !scene || !segments) return
    const r = wrap.getBoundingClientRect()
    const wrapTop = r.top + window.scrollY
    // 08-08 후속(사용자 지적) — "빛이 그려지는 지점이 화면 아래쪽에 치우친다".
    // 예전엔 **뷰포트 위쪽 가장자리**를 기준으로 진행도를 쟀다(래퍼 top이 뷰포트
    // top과 겹칠 때 p=0, 래퍼 bottom이 뷰포트 bottom과 겹칠 때 p=1). 그러면 p=1에
    // 도달하기 전까지는 "지금 그려지는 지점"이 화면 하단 근처에 머무른다 — 뷰포트가
    // 아직 래퍼를 다 못 지나간 상태이기 때문. 화면 높이(vh)만큼을 통째로 손해 보는 셈.
    //
    // 그래서 기준을 **뷰포트 중앙**으로 바꾼다: 뷰포트 중앙이 래퍼 top과 겹칠 때 p=0,
    // 래퍼 bottom과 겹칠 때 p=1. 이러면 "지금 그려지는 지점"이 스크롤 내내 화면
    // 중앙 언저리에 붙어 따라온다 — 스크롤리텔링에서 흔히 쓰는 관용구다.
    const viewportCenterY = window.scrollY + window.innerHeight / 2
    const p = r.height > 0 ? clamp((viewportCenterY - wrapTop) / r.height) : 1

    for (const [key, [s, e, fades]] of Object.entries(segments)) {
      const el = paths.current.get(key)
      const len = lengths.current.get(key)
      if (!el || !len) continue
      const local = clamp((p - s) / (e - s))
      el.style.strokeDashoffset = String(len * (1 - local))
      // 떨어진 탄도는 지우지 않고 흐린 자국으로 남긴다 — 같은 대포를 속도를 올려가며
      // 다시 쏜 것이라는 게 자국으로 남아야 읽힌다.
      if (fades) el.style.opacity = String(1 - clamp((p - e) / 0.06) * 0.75)
    }
    // 궤도가 닫히고 나서야 단계가 올라온다 — 옛 하드코딩(0.93)도 같은 이유로 버리고
    // "closed"가 끝나는 실제 지점(=orbit 박스 끝)에서 시작해 0.05만큼 페이드.
    const closedEnd = segments.closed[1]
    if (stagesRef.current) stagesRef.current.style.opacity = String(clamp((p - closedEnd) / 0.05))
  }, [scene, segments, wrapRef])

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
