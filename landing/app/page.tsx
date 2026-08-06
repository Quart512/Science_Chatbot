import { SiteNav } from "@/components/landing/site-nav"
import { Hero } from "@/components/landing/hero"
import { PrismSection } from "@/components/landing/prism-section"
import { OrbitSection } from "@/components/landing/orbit-section"
import { DarkSideSection } from "@/components/landing/darkside-section"
import { CtaSection } from "@/components/landing/cta"
import { SiteFooter } from "@/components/landing/site-footer"

export default function Page() {
  return (
    <div className="min-h-screen bg-background">
      <SiteNav />
      <main>
        <Hero />
        <PrismSection />
        <OrbitSection />
        <DarkSideSection />
        <CtaSection />
      </main>
      <SiteFooter />
    </div>
  )
}
