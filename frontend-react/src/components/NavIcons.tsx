// 왼쪽 네비 항목 아이콘 — 08-07 사용자 피드백으로 이모지(💬📄🔬🧪📝, 어디서나 보는
// OS 기본 이모지라 브랜드감이 없다는 지적)를 손으로 그린 단색 SVG로 교체. LogoMark와
// 같은 이유로 이 저장소엔 아이콘 라이브러리가 없어 직접 그린다(Logo.tsx 주석 참고).
//
// 색 배정 — 항목마다 --color-spectrum-* 토큰 하나씩(위→아래 나열 순서로 빨주노초파보
// 순서: 챗봇/연구 워크플로우/논문/관심사/실험도구/지식노트 = 빨강·주황·노랑·초록·파랑·
// 보라, 08-07 사용자 의도대로 수정 — 처음엔 반대(보라→빨강)로 배정했었다). 보라 바로
// 옆 남색은 눈으로 구분이 잘 안 돼 건너뛰었다(6항목 다 색이 있고, 스펙트럼 7색 중
// 남색만 안 쓴 것 — 항목을 뺀 게 아님). 이 색은 테마와 무관하게 고정 — 아이콘의
// "정체성" 색이라 라이트/다크가 바뀐다고 같이 바뀌면 오히려 항목을 못 알아본다.
// 테두리(stroke)는 var(--color-text)로 테마를 따라간다(라이트=검정, 다크=흰색) —
// 08-07에 이 테두리를 라이트에서 회색 배지로 바꾼 적이 있었는데, 그건 사실 이
// 네비 아이콘이 아니라 홈 로고(Logo.css) 얘기였다는 게 나중에 확인돼 원복함.
import type { ComponentType, SVGProps } from 'react'
import './NavIcons.css'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }
export type NavIconComponent = ComponentType<IconProps>

function baseProps(size: number, fill: string, className?: string) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill,
    stroke: 'var(--color-text)',
    strokeWidth: 1.2,
    strokeLinejoin: 'round' as const,
    strokeLinecap: 'round' as const,
    className: className ? `nav-icon-svg ${className}` : 'nav-icon-svg',
    'aria-hidden': true,
  }
}

export function ChatIcon({ size = 16, className, ...rest }: IconProps) {
  return (
    <svg {...baseProps(size, 'var(--color-spectrum-red)', className)} {...rest}>
      <path d="M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H9l-4 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" />
    </svg>
  )
}

// 08-07 세 번째 시도 — 1차(원 3개+연결선)는 공유 아이콘과 겹쳐 보인다는 지적, 2차
// (계단식 사각형)도 여전히 마음에 안 든다는 피드백으로 체인(사슬 고리) 모양으로
// 교체. 체인 링은 "속이 빈 고리"가 정체성이라(속을 채우면 그냥 알약 모양 얼룩으로
// 뭉개짐) 나머지 5개 아이콘처럼 fill=스펙트럼색을 그대로는 못 쓴다.
// 08-07 후속 — 그래서 처음엔 stroke=스펙트럼색·fill=none만 썼는데, 그러면 이 아이콘만
// 다른 5개(테마 반응 테두리 있음)와 다르게 테두리가 없어 보인다는 지적. 같은 두 개의
// 고리 경로를 두 번 그려서 해결 — 먼저 굵게 var(--color-text)로(테두리 역할), 그 위에
// 얇게 스펙트럼색으로(색 정체성) 겹쳐 그리면 굵은 선의 양 가장자리가 얇은 선 밖으로
// 삐져나와 "채움+테두리"처럼 보인다 — 속은 여전히 비어있어 고리 모양은 유지됨.
const RESEARCH_LINK_PATHS = (
  <>
    <rect x="2" y="9.3" width="11" height="6.4" rx="3.2" transform="rotate(-45 7.5 12.5)" />
    <rect x="10.5" y="8.3" width="11" height="6.4" rx="3.2" transform="rotate(-45 16 11.5)" />
  </>
)

export function ResearchIcon({ size = 16, className, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className ? `nav-icon-svg ${className}` : 'nav-icon-svg'}
      aria-hidden="true"
      {...rest}
    >
      <g stroke="var(--color-text)" strokeWidth={3.6}>
        {RESEARCH_LINK_PATHS}
      </g>
      <g stroke="var(--color-spectrum-orange)" strokeWidth={2.2}>
        {RESEARCH_LINK_PATHS}
      </g>
    </svg>
  )
}

export function PaperIcon({ size = 16, className, ...rest }: IconProps) {
  return (
    <svg {...baseProps(size, 'var(--color-spectrum-yellow)', className)} {...rest}>
      <path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M8.5 12h7M8.5 15.5h4.5" fill="none" />
    </svg>
  )
}

export function InterestIcon({ size = 16, className, ...rest }: IconProps) {
  return (
    <svg {...baseProps(size, 'var(--color-spectrum-green)', className)} {...rest}>
      <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" />
    </svg>
  )
}

export function EquipmentIcon({ size = 16, className, ...rest }: IconProps) {
  return (
    <svg {...baseProps(size, 'var(--color-spectrum-blue)', className)} {...rest}>
      <path d="M10 3.5V9L4.9 18.1A2 2 0 0 0 6.6 21h10.8a2 2 0 0 0 1.7-3L14 9V3.5" />
      <path d="M9 3.5h6" fill="none" />
    </svg>
  )
}

export function NoteIcon({ size = 16, className, ...rest }: IconProps) {
  return (
    <svg {...baseProps(size, 'var(--color-spectrum-violet)', className)} {...rest}>
      <path d="M4.3 19.7 5.2 15.3 15.3 5.2 18.8 8.7 8.7 18.8Z" />
      <path d="M13.3 6.7 17.3 10.7" fill="none" />
    </svg>
  )
}
