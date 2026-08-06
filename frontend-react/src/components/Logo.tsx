import { useId } from 'react'
import './Logo.css'

// AIsaac 브랜드 마크 — 원본 아트워크(public/aisaac-logo.png, ai-saac 랜딩 프로젝트와
// 공유)는 유리 프리즘이 무지개를 굴절시키고 흰 궤도 링이 감싸는 그림인데, 여백이
// 넓고 유리/흰색 요소가 밝은 배경에서 안 보여서(ai-saac의 Logo.tsx 컴포넌트 주석과
// 같은 문제) 내용부만 크롭해 어두운 배지 위에 얹는다 — 라이트/다크 테마 둘 다에서
// 또렷하게 보이게. 이 저장소용으로 480px로 리사이즈(2.2MB → 275KB, 08-06 — "다운로드
// 크기" 제약, CLAUDE.md §5) — ai-saac 원본과 같은 비율이라 crop 위치(backgroundPosition)
// 값도 그대로 재사용 가능.
export function Logo({
  className,
  size = 28,
  showWordmark = true,
}: {
  className?: string
  size?: number
  showWordmark?: boolean
}) {
  return (
    <span className={className ? `logo-mark ${className}` : 'logo-mark'}>
      <span
        aria-hidden="true"
        className="logo-mark-badge"
        style={{
          width: size,
          height: size,
          backgroundImage: 'url(/aisaac-logo.png)',
        }}
      />
      {showWordmark && <span className="logo-mark-wordmark">AIsaac</span>}
    </span>
  )
}

// 작은 자리(네비 등, ~20px 이하)용 단순화 마크(08-06, 실기 확인 후 사용자 결정) —
// 그 크기에선 원본 사진 로고(무지개·유리 질감)가 그냥 어두운 사각형으로 뭉개져서
// 안 읽힌다는 걸 실제로 렌더링해보고 확인했다. 프리즘 삼각형 실루엣만 남긴 단색
// SVG로 교체 — 이 코드베이스에 아이콘 라이브러리가 없어(PaperRow의 ExpandIcon과
// 같은 이유) 직접 그린다. 큰 자리(홈 헤더 등)는 계속 위 Logo(원본 이미지)를 쓴다.
//
// 08-07 — 단색 윤곽선 삼각형이 "그냥 액센트색 아이콘"처럼 보인다는 피드백으로 원본
// 아트워크의 두 요소(무지개 궤도 링 + 삼각형)를 다시 가져옴. 삼각형은 stroke가 아니라
// fill="var(--color-text)"로 채운다 — 이 토큰이 라이트에서 거의 검정, 다크에서 거의
// 흰색이라 "라이트는 검정 삼각형/다크는 흰 삼각형"이 새 변수 없이 테마 전환에 그대로
// 따라온다. 궤도 링은 .app-nav-spectrum과 같은 스펙트럼 토큰을 재사용한 linearGradient
// stroke — 링 하나만 그려서 20px에서도 원본 사진 로고처럼 뭉개지지 않는지가 관건
// (실기 확인 후 필요하면 뺄 수 있게 분리해둠). 그라디언트 id는 useId()로 인스턴스마다
// 고유하게 만든다 — 페이지에 LogoMark가 두 번 이상 그려지면 <svg> 밖에서도 id가
// 전역으로 조회돼 고정 id였다면 충돌할 수 있어서.
export function LogoMark({ size = 20, className }: { size?: number; className?: string }) {
  const gradientId = `aisaac-orbit-${useId()}`
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--color-spectrum-violet)" />
          <stop offset="16.6%" stopColor="var(--color-spectrum-indigo)" />
          <stop offset="33.3%" stopColor="var(--color-spectrum-blue)" />
          <stop offset="50%" stopColor="var(--color-spectrum-green)" />
          <stop offset="66.6%" stopColor="var(--color-spectrum-yellow)" />
          <stop offset="83.3%" stopColor="var(--color-spectrum-orange)" />
          <stop offset="100%" stopColor="var(--color-spectrum-red)" />
        </linearGradient>
      </defs>
      <circle cx="12" cy="12" r="10" fill="none" stroke={`url(#${gradientId})`} strokeWidth="1.6" />
      <path d="M12 4.5 19.5 18.5 4.5 18.5Z" fill="var(--color-text)" />
    </svg>
  )
}
