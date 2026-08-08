import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { Providers } from '@/components/providers'
import './globals.css'

const geistSans = Geist({
  subsets: ['latin'],
  variable: '--font-geist-sans',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
})

export const metadata: Metadata = {
  // 08-08 — 제목·설명에 "자율형"/"자율적으로"가 남아 있었다(검색 결과와 탭 제목에
  // 그대로 노출되는 자리다). 카피 전면 재작성과 같은 이유로 정정 — 실제로는 매
  // 단계를 사용자가 넘긴다. "뉴턴처럼 분해하고, 스스로 진실을 포착하다"도 v0.app이
  // 임의로 지은 문구라 새 슬로건으로 교체.
  title: 'AIsaac — AI 연구 어시스턴트',
  description:
    '아이작 뉴턴의 1665년을 당신의 컴퓨터 안에서. AIsaac은 골방의 대학원생, 연구실의 전문 연구자, 밤하늘을 보며 의문을 품는 취미 과학자를 위한 AI 연구 어시스턴트입니다.',
  generator: 'v0.app',
}

export const viewport: Viewport = {
  // 08-08 — 랜딩이 딥 블랙 하나로 고정되면서 'light dark' 이중 지원은 더 이상
  // 사실이 아니다. OS가 라이트 모드여도 페이지는 항상 다크로 렌더링되므로
  // 스크롤바 등 브라우저 크롬도 다크로 맞춰야 페이지와 안 어긋난다.
  colorScheme: 'dark',
  themeColor: '#050506',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    // 08-08 — ThemeProvider의 useEffect는 마운트 후에야 dark 클래스를 붙인다.
    // 서버가 렌더링하는 시점부터 dark를 넣어야 첫 페인트가 라이트로 번쩍이지
    // 않는다(랜딩은 이제 다크가 유일한 모습이라 전환 애니메이션이 필요 없다).
    <html lang="ko" className={`dark bg-background ${geistSans.variable} ${geistMono.variable}`}>
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
