import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteEquipment, saveEquipment, type Equipment } from '../api/equipment'

// 08-04 사용자 지적: "수정"이 삭제 옆 버튼이 되어 누르면 그 자리에서 바로 텍스트박스로
// 바뀌고 버튼이 "저장"으로 바뀌는 인라인 편집. 편집 중 다른 항목을 등록/삭제해 목록이
// 리페치돼도 충돌 없게 — name 등 draft 값은 "수정" 클릭 **그 순간**에 item에서 다시
// 채운다(마운트 시점에 한 번만 초기화하면 그 사이 서버 값이 바뀌었을 때 오래된 값으로
// 편집을 시작하게 됨). 편집 시작 이후엔 리페치가 와도 draft를 건드리지 않으므로
// 타이핑 중인 내용도 안 사라진다 — item.id로 key를 잡아 리스트가 새로고침돼도
// 이 컴포넌트 인스턴스 자체는 그대로 유지되기 때문(리마운트 안 됨).
export function EquipmentRow({ item }: { item: Equipment }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(item.name)
  const [purpose, setPurpose] = useState(item.purpose)
  const [detail, setDetail] = useState(item.detail)
  const [precautions, setPrecautions] = useState(item.precautions)

  const saveMutation = useMutation({
    mutationFn: () => saveEquipment({ name, purpose, detail, precautions, update_existing_id: item.id }),
    onSuccess: () => {
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteEquipment(item.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['equipment'] }),
  })

  function startEditing() {
    setName(item.name)
    setPurpose(item.purpose)
    setDetail(item.detail)
    setPrecautions(item.precautions)
    setEditing(true)
  }

  if (editing) {
    return (
      <div className="equipment-row">
        <form
          className="equipment-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (!name) return
            saveMutation.mutate()
          }}
        >
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="이름" />
          <input value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="목적" />
          <textarea value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="세부내용" />
          <textarea value={precautions} onChange={(e) => setPrecautions(e.target.value)} placeholder="주의사항" />
          <div className="equipment-row-actions">
            <div className="equipment-row-actions-left">
              <button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? '저장 중...' : '저장'}
              </button>
              <button type="button" onClick={() => setEditing(false)}>
                취소
              </button>
            </div>
            <button type="button" className="equipment-delete" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
              삭제
            </button>
          </div>
        </form>
      </div>
    )
  }

  return (
    <div className="equipment-row">
      <h3>{item.name}</h3>
      {item.purpose && <p className="equipment-row-meta">목적: {item.purpose}</p>}
      {item.precautions && <p className="equipment-row-warning">⚠️ {item.precautions}</p>}

      <div className="equipment-row-actions">
        <div className="equipment-row-actions-left">
          <button onClick={startEditing}>수정</button>
        </div>
        <button className="equipment-delete" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
          삭제
        </button>
      </div>
    </div>
  )
}
