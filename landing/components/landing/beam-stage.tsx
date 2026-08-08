"use client"

import { useRef, type ReactNode } from "react"
import { BeamScene } from "@/components/landing/beam-scene"

/**
 * 광선 장면이 깔리는 무대 — 히어로·프리즘·궤도를 한 컨테이너로 묶는다.
 * `page.tsx`가 서버 컴포넌트라 ref를 못 들고 있어서 이 얇은 클라이언트 래퍼로 뺐다.
 *
 * `isolate`(= `isolation: isolate`)가 핵심이다. 이게 있어야 이 div가 쌓임 맥락을
 * 만들고, 그 안에서 `-z-10`인 SVG가 **섹션 글자 밑**으로 내려가면서도 페이지 배경
 * 뒤로는 안 빠진다. isolate 없이 `-z-10`을 주면 래퍼가 쌓임 맥락이 아니라서 장면이
 * body 배경 뒤로 사라진다.
 */
export function BeamStage({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)

  return (
    <div ref={ref} className="relative isolate">
      <BeamScene wrapRef={ref} />
      {children}
    </div>
  )
}
