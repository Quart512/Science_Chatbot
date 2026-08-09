import { useEffect, useState } from 'react'

// 첫 실행 안내창을 설정 화면에서 수동으로 다시 열기 위한 신호 통로(08-09).
//
// localStorage가 아니라 메모리 pub-sub인 이유: "다시 보여줘"는 한 번 일어나는 **사건**이지
// useTheme.ts·useChatPanelAutoShow.ts가 다루는 것 같은 지속되는 **설정값**이 아니다.
// WelcomeModal(Layout.tsx에 항상 마운트)과 Settings.tsx는 라우트가 다른 형제 화면이라
// props로 못 이어주므로, 이 얇은 이벤트 버스로 연결한다.
type Listener = () => void
const listeners = new Set<Listener>()

export function openWelcomeModal(): void {
  listeners.forEach((l) => l())
}

// WelcomeModal이 구독한다 — 신호를 받으면 true, 모달이 스스로 닫힐 때 clear()를 불러
// 원래대로(= 다시 동의 여부로만 판단하는 상태) 되돌린다.
export function useWelcomeModalForceOpen(): [boolean, () => void] {
  const [forceOpen, setForceOpen] = useState(false)

  useEffect(() => {
    const listener = () => setForceOpen(true)
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }, [])

  return [forceOpen, () => setForceOpen(false)]
}
