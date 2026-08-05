// FastAPI 백엔드 호출 공용 헬퍼 — frontend/common.py의 BACKEND_URL과 같은 역할.
// Vite는 VITE_ 접두사가 붙은 환경변수만 클라이언트 코드에 노출한다(보안 경계 —
// 접두사 없는 변수는 서버 전용 시크릿일 수 있어 번들에 안 실림).
//
// 기본값은 빈 문자열(같은 오리진) — 08-05 Docker 패키징부터 main.py가 dist를 같은
// 포트(8000)로 같이 서빙하므로 프로덕션 빌드는 상대 경로(`/query` 등)로 충분하다.
// 로컬 개발(Vite 5173 + 백엔드 8000, 서로 다른 포트)에서는 frontend-react/.env의
// VITE_BACKEND_URL=http://localhost:8000이 이 기본값을 덮어쓴다.
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// 모든 API 함수가 공유하는 저수준 fetch 래퍼 — 에러 응답(4xx/5xx)을 ApiError로
// 통일해서 던진다. FastAPI의 HTTPException은 {"detail": "..."} 형태로 오므로
// 그 필드를 우선 메시지로 쓴다.
//
// 경로에 /api를 여기서 한 번만 붙인다(08-05) — main.py의 모든 API 라우트가 /api
// 프리픽스를 쓰므로(리액트 페이지 경로 /papers 등과 겹치는 걸 막기 위해, RoadMap
// "Docker 패키징" 참고), 호출부마다 반복해서 안 붙여도 되게 여기 한 곳에서 처리한다.
// apiFetch를 안 쓰고 fetch()를 직접 부르는 곳(chat.ts의 스트리밍, papers.ts의 파일
// 업로드)은 이 헬퍼를 안 거치므로 각자 /api를 직접 붙여야 한다.
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_URL}/api${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}
