const STORAGE_KEY = 'lastViewedChatThreadId'

// 왼쪽 챗 화면(Chat.tsx, /chat/:id)에서 "본" 스레드만 기록한다 — 오른쪽 패널(ChatPanel.tsx)이
// 자기가 띄운 세션을 다시 기록하면 순환이 되어 절대 안 바뀐다(RoadMap "오른쪽 패널이
// '마지막으로 답변을 요청한' 챗을 연다" 항목 참고). 두 컴포넌트가 동시에 마운트되는 일이
// 없어(ChatPanel은 /chat 라우트에서 항상 숨음) useChatPanelAutoShow처럼 커스텀 이벤트로
// 인스턴스 간 동기화할 필요가 없다 — 그냥 읽고 쓰기만 하면 된다.
export function setLastViewedChatThreadId(threadId: string): void {
  localStorage.setItem(STORAGE_KEY, threadId)
}

export function getLastViewedChatThreadId(): string | null {
  return localStorage.getItem(STORAGE_KEY)
}
