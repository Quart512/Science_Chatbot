import { useEffect, useState } from 'react'

const STORAGE_KEY = 'chatPanelAutoShow'
// localStorage엔 'storage' 이벤트가 있지만 그건 다른 탭/창에서 쓸 때만 발화하고
// 같은 문서 안에서 쓴 건 못 잡는다(브라우저 표준 동작). 이 훅은 ChatPanel.tsx와
// Settings.tsx의 카드가 같은 화면(/settings)에 동시에 떠서 서로 다른 useState 인스턴스로
// 같은 값을 읽는데, 처음엔 그냥 각자 localStorage를 읽기만 하고 끝냈더니 Settings에서
// 토글해도 이미 마운트돼 있던 ChatPanel 쪽 값은 안 바뀌는 버그가 났다(브라우저로 실제
// 재현 확인 — 08-06). 커스텀 이벤트로 모든 인스턴스에 변경을 알린다.
const CHANGE_EVENT = 'chatPanelAutoShow-change'

function readStored(): boolean {
  const stored = localStorage.getItem(STORAGE_KEY)
  // 기본값 true: 지금까지 "패널이 항상 떠 있던" 모습에 가장 가까운 쪽이라 설정을
  // 한 번도 안 건드린 사용자에게 놀라움이 적다.
  return stored === null ? true : stored === 'true'
}

export function useChatPanelAutoShow() {
  const [autoShow, setAutoShowState] = useState<boolean>(readStored)

  useEffect(() => {
    function handleChange() {
      setAutoShowState(readStored())
    }
    window.addEventListener(CHANGE_EVENT, handleChange)
    return () => window.removeEventListener(CHANGE_EVENT, handleChange)
  }, [])

  function setAutoShow(next: boolean) {
    localStorage.setItem(STORAGE_KEY, String(next))
    // 이 인스턴스 자신도 이벤트를 거쳐 갱신 — 직접 setAutoShowState를 부르지 않는 건
    // "값이 바뀌는 경로는 하나"로 유지해 다른 인스턴스와 갱신 로직이 갈라지지 않게 하기 위함.
    window.dispatchEvent(new Event(CHANGE_EVENT))
  }

  return { autoShow, setAutoShow }
}
