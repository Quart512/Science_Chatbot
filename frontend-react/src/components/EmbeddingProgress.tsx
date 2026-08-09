import { useEmbeddingStatus, formatBytes } from '../hooks/useEmbeddingStatus'
import './EmbeddingProgress.css'

// 첫 실행 때 bge-m3(약 2.1GB)를 받는 동안 무슨 일이 벌어지는지 보여준다(08-09).
// 이게 없으면 사용자에겐 "검색·논문 기능이 이유 없이 멈춤"으로만 보인다.
//
// **total_bytes가 0이면 퍼센트를 그리지 않는다.** 두 경우에 0으로 온다: ① 파일
// 메타데이터가 아직 안 도착한 아주 초기, ② 모델이 이미 캐시에 있어 다운로드가 아예
// 일어나지 않는 경우(두 번째 실행부터). 0을 "0%"로 그리면 다 받아둔 사용자에게
// 매번 "0%"가 스쳐 지나가 오히려 뭔가 잘못된 것처럼 보인다.
export function EmbeddingProgress() {
  const { data } = useEmbeddingStatus()

  if (!data || data.state === 'ready') return null

  if (data.state === 'failed') {
    return (
      <div className="embedding-progress embedding-progress-failed">
        <span className="embedding-progress-label">
          검색 모델 준비 실패 — 인터넷 연결을 확인해주세요. 다음 질문에서 다시 시도합니다.
        </span>
        {data.error && <span className="embedding-progress-detail">{data.error}</span>}
      </div>
    )
  }

  const hasTotal = data.total_bytes > 0
  const percent = hasTotal ? Math.min(100, Math.round((data.downloaded_bytes / data.total_bytes) * 100)) : 0

  return (
    <div className="embedding-progress">
      <span className="embedding-progress-label">
        {data.state === 'loading' ? '검색 모델 불러오는 중…' : '검색 모델 내려받는 중…'}
        {hasTotal && (
          <span className="embedding-progress-detail">
            {formatBytes(data.downloaded_bytes)} / {formatBytes(data.total_bytes)} ({percent}%)
          </span>
        )}
      </span>
      <div
        className="embedding-progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        // 총량을 모르는 동안은 aria에서도 값을 비워 "진행 중이지만 미상"임을 알린다.
        aria-valuenow={hasTotal ? percent : undefined}
      >
        <div
          className={hasTotal ? 'embedding-progress-fill' : 'embedding-progress-fill embedding-progress-fill-indeterminate'}
          style={hasTotal ? { width: `${percent}%` } : undefined}
        />
      </div>
      {/* 챗 질문도 예외가 아니다 — graph.py가 START → retrieve로 시작해서 모든 질문이
          벡터스토어를 거친다(08-09 확인). "챗은 지금도 된다"고 쓰면 거짓말이 된다.
          대신 지금 할 수 있는 일(API 키 입력)을 안내한다. */}
      <span className="embedding-progress-note">
        준비가 끝나기 전까지 질문·검색은 응답을 기다립니다. 그동안 설정 화면에서 API 키를 넣어두면 됩니다.
      </span>
    </div>
  )
}

// 화면 하단 고정 배너 — 안내창을 닫은 뒤에도 준비가 끝날 때까지 남는다.
// 감쌀 상자 자체가 조건부여야 한다: EmbeddingProgress가 null을 돌려줄 때 래퍼만 남으면
// 준비가 다 끝난 뒤에도 테두리와 배경만 있는 빈 상자가 화면 구석에 계속 떠 있게 된다.
export function EmbeddingProgressBanner() {
  const { data } = useEmbeddingStatus()

  if (!data || data.state === 'ready') return null

  return (
    <div className="embedding-progress-banner">
      <EmbeddingProgress />
    </div>
  )
}
