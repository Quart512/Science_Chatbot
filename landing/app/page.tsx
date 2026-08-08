import { SiteNav } from "@/components/landing/site-nav"
import { Hero } from "@/components/landing/hero"
import { PrismSection } from "@/components/landing/prism-section"
import { OrbitSection } from "@/components/landing/orbit-section"
import { ScreensSection } from "@/components/landing/screens-section"
import { BeamStage } from "@/components/landing/beam-stage"
import { CtaSection } from "@/components/landing/cta"
import { SiteFooter } from "@/components/landing/site-footer"

export default function Page() {
  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main>
        {/* 광선 한 줄기가 이 셋을 가로지른다 — 세 섹션이 한 무대여야 하므로 묶는다. */}
        <BeamStage>
          <Hero />
          <PrismSection />
          <OrbitSection />
        </BeamStage>
        {/* 은유(프리즘·궤도) 다음에 은유 없는 기능 섹션 — 컨셉이 "연구를 어떻게 대하는가"를
            말한 뒤라 여기서 "무엇을 해주는가"가 이어진다(RoadMap "08-08 결론"). */}
        <ScreensSection />
        <CtaSection />
      </main>
      <SiteFooter />
    </div>
  )
}
