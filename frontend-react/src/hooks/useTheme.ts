import { useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'theme'
const DEFAULT_THEME: Theme = 'dark' // 지금까지 유일했던 모습 — 명시적으로 안 고르면 그대로

function readStoredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'light' ? 'light' : DEFAULT_THEME
}

// 다크/라이트 테마 상태 — 08-06 신설(라이트 모드 도입). index.html의 인라인 스크립트가
// 첫 페인트 전에 이미 같은 localStorage 키('theme')로 `data-theme`를 선반영해두므로
// (번들 로드 전에 동기로 돌아야 해서 그쪽은 순수 JS로 중복 구현 — 그 스크립트 주석
// 참고), 여기서는 React 쪽 상태만 그 값과 동기화하고 이후 변경(설정 화면의 토글)을
// 담당한다. 여러 컴포넌트가 이 훅을 동시에 써도 상태가 안 어긋나도록 각 인스턴스가
// 마운트 시 document.documentElement에서 실제 반영된 값을 다시 읽는다.
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    const attr = document.documentElement.getAttribute('data-theme')
    return attr === 'light' ? 'light' : DEFAULT_THEME
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  function setTheme(next: Theme) {
    setThemeState(next)
  }

  return { theme, setTheme }
}

// 모듈 스코프에서 한 번 더 확인 — index.html 스크립트가 어떤 이유로(예: localStorage
// 접근 실패) 못 미쳤을 때의 안전망. readStoredTheme()는 훅 밖에서도 초기값이 필요할
// 수 있어 export.
export { readStoredTheme }
