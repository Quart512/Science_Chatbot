import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteApiKey, listApiKeyStatus, saveApiKey, type ApiKeyStatus } from '../api/settings'
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
    </div>
  )
}
