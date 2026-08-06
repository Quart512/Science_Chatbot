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
export function LogoMark({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M12 3.5 20.5 19.5 3.5 19.5Z" />
    </svg>
  )
}
