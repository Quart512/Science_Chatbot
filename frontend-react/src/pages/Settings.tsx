import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteApiKey, getVersion, listApiKeyStatus, saveApiKey, type ApiKeyStatus } from '../api/settings'
import { exportLibrary, importLibrary } from '../api/library'
import { useTheme, type Theme } from '../hooks/useTheme'
import { useChatPanelAutoShow } from '../hooks/useChatPanelAutoShow'
import { Markdown } from '../components/Markdown'
import './Settings.css'

const THEME_OPTIONS: { key: Theme; label: string }[] = [
  { key: 'dark', label: '🌙 다크' },
  { key: 'light', label: '☀️ 라이트' },
]

// 08-06 신설 — 라이트 모드 도입과 함께. 저장 위치는 백엔드(다른 설정 카드들)가 아니라
// localStorage(useTheme.ts) — 화면 표시 취향이라 기기별로 다를 수 있고, API 키처럼
// "이 컴퓨터의 서버가 기억해야 하는 값"이 아니다.
function ThemeCard() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="settings-card">
      <h3>테마</h3>
      <p className="settings-card-meta">이 브라우저에만 저장됩니다.</p>
      <div className="settings-card-actions">
        {THEME_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            className={theme === opt.key ? 'settings-theme-active' : undefined}
            onClick={() => setTheme(opt.key)}
            disabled={theme === opt.key}
            aria-pressed={theme === opt.key}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// 08-06 신설 — ChatPanel.tsx "챗봇을 벗어날 때 다시 열지" 설정의 UI. 저장 위치는
// ThemeCard와 같은 이유로 localStorage(useChatPanelAutoShow.ts) — 기기별 화면 취향.
function ChatPanelAutoShowCard() {
  const { autoShow, setAutoShow } = useChatPanelAutoShow()

  return (
    <div className="settings-card">
      <h3>챗 패널 자동 열림</h3>
      <p className="settings-card-meta">
        챗봇 화면을 벗어날 때 오른쪽 챗 패널을 자동으로 다시 열지 정합니다. 껐다 켜는 건
        오른쪽 버튼으로 이 설정과 상관없이 항상 가능합니다.
      </p>
      <div className="settings-card-actions">
        <button
          className={autoShow ? 'settings-theme-active' : undefined}
          onClick={() => setAutoShow(true)}
          disabled={autoShow}
          aria-pressed={autoShow}
        >
          자동으로 열기
        </button>
        <button
          className={!autoShow ? 'settings-theme-active' : undefined}
          onClick={() => setAutoShow(false)}
          disabled={!autoShow}
          aria-pressed={!autoShow}
        >
          버튼으로만
        </button>
      </div>
    </div>
  )
}

// 08-09 신설 — Windows 포터블 번들이 08-09부터 포트 자동 재시도(8000~8049)를 쓰면서
// 실행마다 포트가 달라질 수 있게 됐다(mac/linux는 08-07부터 이미 그랬음). 백엔드에
// 물어볼 필요 없이 지금 이 화면이 떠 있는 주소 자체가 곧 서버 주소라 window.location만
// 읽으면 된다.
function ConnectionInfoCard() {
  return (
    <div className="settings-card">
      <h3>연결 정보</h3>
      <p className="settings-card-meta">
        지금 접속 중인 주소: <code>{window.location.origin}</code>
      </p>
    </div>
  )
}

// 08-09 신설 — 버전은 배포판에서만 의미가 있다("dev"는 소스 실행). 릴리즈 노트는
// 접었다 펼치는 토글로 뒀다 — 버전 한 줄만 보고 싶은 사람이 대부분일 텐데 노트 전문을
// 항상 펴두면 다른 설정 카드들 사이에서 스크롤만 길어진다.
function VersionCard() {
  const [notesOpen, setNotesOpen] = useState(false)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['version'],
    queryFn: getVersion,
  })

  return (
    <div className="settings-card">
      <h3>버전</h3>
      {isLoading && <p className="settings-card-meta">불러오는 중...</p>}
      {isError && <p className="settings-error">조회 실패: {(error as Error).message}</p>}
      {data && (
        <>
          <p className="settings-card-meta">{data.version}</p>
          {data.release_notes ? (
            <>
              <div className="settings-card-actions">
                <button type="button" onClick={() => setNotesOpen((v) => !v)}>
                  {notesOpen ? '릴리즈 노트 접기' : '릴리즈 노트 보기'}
                </button>
              </div>
              {notesOpen && (
                <div className="settings-release-notes">
                  <Markdown text={data.release_notes} />
                </div>
              )}
            </>
          ) : (
            <p className="settings-card-meta settings-card-meta-empty">이 버전의 릴리즈 노트가 없습니다</p>
          )}
        </>
      )}
    </div>
  )
}

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

// 08-08 — 사용자 질문("공유용이랑 기기 이전용이랑 뭐가 달라?")에 답하며 문구를
// 늘렸다. 예전 hint는 "무엇이 더 들어가는지"(+검색 인덱스 등)만 말하고 "그래서
// 뭐가 달라지는지"는 안 적어서, 셋을 구분하는 실제 기준(재파싱 없이 검색이 바로
// 되는지, 원본을 다시 봐야 하는지)이 화면에서 안 보였다 — 원인-결과를 명시적으로
// 잇는다.
const EXPORT_OPTIONS: { key: string; label: string; hint: string; scope: ExportScope }[] = [
  {
    key: 'share',
    label: '공유용',
    hint: '논문 서지·상태·관심사·노트만 담습니다. 가볍고 저작권 걱정 없이 남과 나눌 수 있지만, 검색 인덱스도 원본 PDF도 없어서 가져온 쪽은 논문을 다시 등록해야 검색·요약이 됩니다.',
    scope: { includeIndex: false, includeLibrary: false },
  },
  {
    key: 'migrate',
    label: '기기 이전용',
    hint: '위 내용 + 검색 인덱스까지 담습니다. 새 기기에서 가져오면 재파싱·재임베딩 없이 검색·추출 결과가 바로 됩니다. 원본 PDF는 없어서, 다시 봐야 하는 논문 파일은 따로 옮겨야 합니다.',
    scope: { includeIndex: true, includeLibrary: false },
  },
  {
    key: 'backup',
    label: '완전 백업',
    hint: '위 전부 + 원본 PDF까지 통째로 담습니다. 이 파일 하나로 완전히 복원되지만, 파일이 가장 큽니다 — 본인 백업용.',
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
      {/* 08-08 — 설명을 버튼 title(마우스를 올려야만 보이는 툴팁)에서 항상 보이는
          텍스트로 옮겼다(사용자 요청 — "공유용이랑 기기 이전용이랑 뭐가 달라?"를
          화면만 보고는 알 수 없었다). 셋 다 눌러야 알 수 있던 차이를 미리 읽고 고를
          수 있게. */}
      <div className="settings-export-options">
        {EXPORT_OPTIONS.map((opt) => (
          <div key={opt.key} className="settings-export-option">
            <button
              onClick={() => {
                setPendingKey(opt.key)
                exportMutation.mutate(opt.scope)
              }}
              disabled={exportMutation.isPending}
            >
              {exportMutation.isPending && pendingKey === opt.key ? '내보내는 중...' : opt.label}
            </button>
            <p className="settings-export-hint">{opt.hint}</p>
          </div>
        ))}
      </div>
      {exportMutation.isError && (
        <p className="settings-error">내보내기 실패: {(exportMutation.error as Error).message}</p>
      )}
    </div>
  )
}

// ⑥-B(08-05) — 병합은 없다(사용자 결정, RoadMap "라이브러리 import" 행 참고). 서버가
// 기존 데이터가 있으면 400으로 거부하지만, 눌러보기 전에 미리 알려주는 게 사용자 요청
// ("기존 데이터 있으면 안된다는 안내도 추가하자") — 실패하고 나서야 이유를 아는 것보다
// 먼저 조건을 밝혀두는 쪽이 낫다.
function LibraryImportCard() {
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)

  const importMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('가져올 ZIP 파일을 선택해주세요.')
      return importLibrary(file)
    },
    onSuccess: () => {
      setFile(null)
      // 내보내기가 앱의 거의 모든 데이터(논문·관심사·실험도구·노트)를 건드리므로,
      // 각 화면이 쓰는 쿼리 키를 전부 무효화해야 방금 들어온 데이터가 바로 보인다.
      queryClient.invalidateQueries({ queryKey: ['papers'] })
      queryClient.invalidateQueries({ queryKey: ['library', 'files'] })
      queryClient.invalidateQueries({ queryKey: ['interests'] })
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
    },
  })

  const result = importMutation.data

  return (
    <div className="settings-card">
      <h3>라이브러리 가져오기</h3>
      <p className="settings-card-meta">
        위에서 내보낸 ZIP을 복원합니다. <strong>새로 설치한 상태(논문·관심사·실험도구·노트가 전부 비어있을 때)에서만
        가능합니다</strong> — 기존 데이터가 하나라도 있으면 가져오기가 거부됩니다(병합 없음, 덮어쓰기 방지).
      </p>
      <form
        className="settings-form"
        onSubmit={(e) => {
          e.preventDefault()
          importMutation.mutate()
        }}
      >
        <input type="file" accept=".zip" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <div className="settings-card-actions">
          <button type="submit" disabled={importMutation.isPending || !file}>
            {importMutation.isPending ? '가져오는 중...' : '가져오기'}
          </button>
        </div>
      </form>
      {importMutation.isError && (
        <p className="settings-error">가져오기 실패: {(importMutation.error as Error).message}</p>
      )}
      {result && (
        <>
          <p className="settings-card-meta">
            가져오기 완료 — 논문 {result.papers}편, 관심사 {result.interests}건, 실험도구 {result.equipment}건, 노트{' '}
            {result.notes}건
          </p>
          {/* 검색 인덱스(chroma_db)를 같이 가져왔으면 재시작 전까지 검색·추출이 깨진다
              (main.py import_library() 주석 — 실제로 재현·확인한 근거). 논문·관심사·
              실험도구·노트 목록 자체는 재시작 없이 바로 반영된다(RDB는 매 요청마다
              새 연결이라 이 문제가 없음). */}
          {result.restart_required && (
            <p className="settings-warning">
              검색 인덱스를 같이 가져왔습니다 — 논문 검색·추출이 정상 동작하려면 앱을 재시작해주세요.
            </p>
          )}
        </>
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

      <ThemeCard />
      <ChatPanelAutoShowCard />
      <ConnectionInfoCard />
      <VersionCard />

      <p className="settings-intro">
        여기서 입력한 키는 이 컴퓨터에 저장되고, 다음 질문부터(서버 재시작 없이) 바로
        적용됩니다. 입력하지 않으면 서버의 .env 값을 그대로 씁니다. Qwen-tuned(로컬
        모델)는 키가 필요 없습니다.
      </p>

      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="settings-error">조회 실패: {(error as Error).message}</p>}
      {data && data.keys.map((status) => <ApiKeyCard key={status.provider} status={status} />)}

      <LibraryExportCard />
      <LibraryImportCard />
    </div>
  )
}
