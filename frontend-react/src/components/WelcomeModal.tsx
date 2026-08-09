import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getTelemetryConsent, installLocalModel, setTelemetryConsent } from '../api/settings'
import { useLocalModel } from '../hooks/useLocalModel'
import { TELEMETRY_CONSENT_TEXT, TELEMETRY_CONSENT_REVERSIBLE } from '../lib/telemetryCopy'
import { EmbeddingProgress } from './EmbeddingProgress'
import './WelcomeModal.css'

const USAGE_GUIDE_URL = 'https://github.com/Quart512/AIsaac/blob/main/docs/USAGE.md'

// API 키가 없는 사람을 위한 대안 제시(08-09, 사용자 요청 "안내문에도 다운로드 버튼").
//
// **경고를 버튼 위에 둔다** — 설정 화면의 같은 카드와 동일한 원칙이다. 여기서는 아직
// 앱을 한 번도 안 써본 사람이라 더 중요하다: 품질을 모르고 1GB를 받은 뒤 "이 앱은
// 형편없다"고 결론 내리면 그게 첫인상이 된다.
//
// 지원 안 하는 환경이거나 이미 받았으면 아예 안 보인다 — 첫 화면에 못 쓰는 선택지를
// 늘어놓지 않는다.
function LocalModelOffer() {
  const queryClient = useQueryClient()
  const { data } = useLocalModel()
  const install = useMutation({
    mutationFn: installLocalModel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['local-model'] }),
  })

  // 받는 중에는 이미 파일이 깔려도(installed=true) 계속 보여준다 — 모델을 메모리에
  // 올리는 마지막 단계가 남아 있어서, 여기서 사라지면 진행 상황을 볼 곳이 없어진다.
  if (!data || !data.supported || (data.installed && data.state !== 'downloading')) return null

  const downloading = data.state === 'downloading'
  const hasTotal = data.total_bytes > 0
  const percent = hasTotal ? Math.round((data.downloaded_bytes / data.total_bytes) * 100) : 0

  return (
    <div className="welcome-modal-local">
      <strong>API 키 없이 먼저 둘러보고 싶다면</strong>
      <p>
        로컬 모델을 받으면 키 없이도 챗 질문이 동작합니다(약 1GB).{' '}
        <b>다만 품질이 매우 낮습니다</b> — 자체 평가 0.132점(같은 기준 Claude Haiku 0.915)이고,
        질문한 언어와 다른 언어로 답하는 경우도 잦습니다. 앱이 도는지 확인하는 용도이지
        실제 연구에 쓸 수준이 아닙니다.
      </p>
      {downloading ? (
        <p className="welcome-modal-local-progress">
          받는 중 — {data.phase}
          {hasTotal && ` (${percent}%)`}
        </p>
      ) : (
        <button type="button" onClick={() => install.mutate()} disabled={install.isPending}>
          로컬 모델 받기 (약 1GB)
        </button>
      )}
      {install.isError && (
        <p className="welcome-modal-error">{(install.error as Error).message}</p>
      )}
    </div>
  )
}

// 첫 실행 안내창(08-09). 두 가지를 한 창에서 끝낸다 — ① 앱을 쓰려면 반드시 필요한
// 사전 작업(API 키) 안내, ② 사용 데이터 공유 동의.
//
// **기존 FullscreenModal을 일부러 재사용하지 않는다.** 그건 X 버튼·Esc·오버레이 클릭이
// 전부 "닫기"로 이어지게 설계된 컴포넌트인데(components/FullscreenModal.tsx), 여기서는
// 정반대가 필요하다: 두 버튼 중 하나를 눌러야만 닫혀야 한다. 그냥 닫히면 "거부"인지
// "아직 대답 안 함"인지 서버가 구분할 수 없고, 그러면 다음 실행에서 또 물어보게 된다.
//
// 두 버튼은 크기·색을 똑같이 둔다. 한쪽을 강조하면 그건 동의를 받는 게 아니라 유도다.
export function WelcomeModal() {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['telemetry-consent'],
    queryFn: getTelemetryConsent,
  })

  const mutation = useMutation({
    mutationFn: (consent: boolean) => setTelemetryConsent(consent),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['telemetry-consent'] }),
  })

  // asked가 false일 때만 뜬다 — 거부한 사용자에게 매번 다시 묻지 않기 위한 값이다
  // (api/settings.ts의 TelemetryConsent 주석 참고). 조회 전(data === undefined)에는
  // 아무것도 안 그린다: 잠깐 떴다 사라지는 깜빡임을 막는다.
  if (!data || data.asked) return null

  return (
    <div className="welcome-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="welcome-modal-title">
      <div className="welcome-modal-panel">
        <h2 id="welcome-modal-title" className="welcome-modal-title">
          AIsaac을 시작합니다
        </h2>

        <p className="welcome-modal-lead">과학 논문을 찾고 읽고 정리하는 연구 어시스턴트입니다.</p>

        <div className="welcome-modal-callout">
          <strong>먼저 할 일 — API 키 넣기</strong>
          <p>
            AI 모델은 본인 API 키로 동작합니다. 왼쪽 메뉴 맨 아래 <b>⚙️ 설정</b>에서 넣어주세요.
            Google Gemini 키는 무료로 발급받을 수 있습니다.
          </p>
        </div>

        <LocalModelOffer />

        <p className="welcome-modal-guide">
          화면별 사용법은{' '}
          <a href={USAGE_GUIDE_URL} target="_blank" rel="noreferrer noopener">
            사용법 가이드
          </a>
          에 있습니다.
        </p>

        {/* 준비가 끝났으면 이 컴포넌트가 스스로 아무것도 안 그린다 — 두 번째 실행부터는
            이 자리가 비어 안내창이 짧아진다. */}
        <EmbeddingProgress />

        <hr className="welcome-modal-divider" />

        <div className="welcome-modal-consent">
          <strong>사용 데이터 공유</strong>
          <p>
            {TELEMETRY_CONSENT_TEXT} {TELEMETRY_CONSENT_REVERSIBLE}
          </p>
        </div>

        {mutation.isError && (
          <p className="welcome-modal-error">저장 실패: {(mutation.error as Error).message}</p>
        )}

        <div className="welcome-modal-actions">
          <button type="button" onClick={() => mutation.mutate(true)} disabled={mutation.isPending}>
            공유하고 시작
          </button>
          <button type="button" onClick={() => mutation.mutate(false)} disabled={mutation.isPending}>
            공유 없이 시작
          </button>
        </div>
      </div>
    </div>
  )
}
