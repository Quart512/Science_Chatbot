import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteApiKey, listApiKeyStatus, saveApiKey, type ApiKeyStatus } from '../api/settings'
import { exportLibrary } from '../api/library'
import './Settings.css'

const PROVIDER_LABELS: Record<ApiKeyStatus['provider'], string> = {
  gemini: 'Gemini',
  claude: 'Claude',
}

// provider 하나(gemini 또는 claude)의 카드 — EquipmentRow.tsx와 같은 인라인 편집 패턴
// (수정 누르면 그 자리에서 입력창으로 바뀜)이지만, 목록에서 지우는 게 아니라 "저장된
// 키를 지우면 .env로 되돌아간다"는 게 다르다.
function ApiKeyCard({ status }: { status: ApiKeyStatus }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [apiKey, setApiKey] = useState('')

  const saveMutation = useMutation({
    mutationFn: () => saveApiKey(status.provider, apiKey),
    onSuccess: () => {
      setEditing(false)
      setApiKey('')
      queryClient.invalidateQueries({ queryKey: ['api-key-status'] })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteApiKey(status.provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-key-status'] }),
  })

  if (editing) {
    return (
      <div className="settings-card">
        <h3>{PROVIDER_LABELS[status.provider]}</h3>
        <form
          className="settings-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (!apiKey.trim()) return
            saveMutation.mutate()
          }}
        >
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={`${PROVIDER_LABELS[status.provider]} API 키를 붙여넣으세요`}
            autoComplete="off"
          />
          <div className="settings-card-actions">
            <button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? '저장 중...' : '저장'}
            </button>
            <button type="button" onClick={() => { setEditing(false); setApiKey('') }}>
              취소
            </button>
          </div>
          {saveMutation.isError && (
            <p className="settings-error">저장 실패: {(saveMutation.error as Error).message}</p>
          )}
        </form>
      </div>
    )
  }

  return (
    <div className="settings-card">
      <h3>{PROVIDER_LABELS[status.provider]}</h3>
      {status.saved ? (
        <p className="settings-card-meta">저장된 키: {status.masked_key}</p>
      ) : (
        <p className="settings-card-meta settings-card-meta-empty">
          저장된 키 없음 — 서버의 .env 값을 그대로 씁니다
        </p>
      )}
      <div className="settings-card-actions">
        <button onClick={() => setEditing(true)}>{status.saved ? '키 변경' : '키 입력'}</button>
        {status.saved && (
          <button
            className="settings-delete"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
          >
            삭제
          </button>
        )}
      </div>
    </div>
  )
}

// ⑥-A(08-05) — 3단계 누적 범위(RoadMap "논문·노트 저장 방식 재설계" 참고). 뒤로 갈수록
// include_index·include_library가 추가로 켜지는 것뿐이라 서버 계약과 그대로 맞춘다.
type ExportScope = { includeIndex: boolean; includeLibrary: boolean }

const EXPORT_OPTIONS: { key: string; label: string; hint: string; scope: ExportScope }[] = [
  {
    key: 'share',
    label: '공유용',
    hint: '논문 서지·상태·관심사·노트만 — 가볍고 저작권 안전(원본 PDF 제외)',
    scope: { includeIndex: false, includeLibrary: false },
  },
  {
    key: 'migrate',
    label: '기기 이전용',
    hint: '+검색 인덱스 — 새 기기에서 재파싱·재임베딩 없이 그대로 복원',
    scope: { includeIndex: true, includeLibrary: false },
  },
  {
    key: 'backup',
    label: '완전 백업',
    hint: '+원본 PDF까지 전부 — 본인용, 파일이 가장 큼',
    scope: { includeIndex: true, includeLibrary: true },
  },
]

function LibraryExportCard() {
  const [pendingKey, setPendingKey] = useState<string | null>(null)
  const exportMutation = useMutation({
    mutationFn: (scope: ExportScope) => exportLibrary(scope.includeIndex, scope.includeLibrary),
    onSuccess: (blob) => {
      // Blob URL을 만들어 <a download>를 트리거하는 표준 패턴 — 서버가 준 바이트를
      // 그대로 브라우저 다운로드로 넘긴다. 다운로드가 시작되면 URL은 더 안 필요해
      // revoke해서 메모리에 안 남긴다.
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'library_export.zip'
      a.click()
      URL.revokeObjectURL(url)
    },
    onSettled: () => setPendingKey(null),
  })

  return (
    <div className="settings-card">
      <h3>라이브러리 내보내기</h3>
      <p className="settings-card-meta">
        논문·관심사·실험도구·노트를 ZIP으로 내려받습니다. 범위가 넓을수록 파일이 커집니다.
      </p>
      <div className="settings-card-actions">
        {EXPORT_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            title={opt.hint}
            onClick={() => {
              setPendingKey(opt.key)
              exportMutation.mutate(opt.scope)
            }}
            disabled={exportMutation.isPending}
          >
            {exportMutation.isPending && pendingKey === opt.key ? '내보내는 중...' : opt.label}
          </button>
        ))}
      </div>
      {exportMutation.isError && (
        <p className="settings-error">내보내기 실패: {(exportMutation.error as Error).message}</p>
      )}
    </div>
  )
}

export function Settings() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['api-key-status'],
    queryFn: listApiKeyStatus,
  })

  return (
    <div>
      <h1>⚙️ 설정</h1>
      <p className="settings-intro">
        여기서 입력한 키는 이 컴퓨터에 저장되고, 다음 질문부터(서버 재시작 없이) 바로
        적용됩니다. 입력하지 않으면 서버의 .env 값을 그대로 씁니다. Qwen-tuned(로컬
        모델)는 키가 필요 없습니다.
      </p>

      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="settings-error">조회 실패: {(error as Error).message}</p>}
      {data && data.keys.map((status) => <ApiKeyCard key={status.provider} status={status} />)}

      <LibraryExportCard />
    </div>
  )
}
