import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listEquipment, saveEquipment } from '../api/equipment'
import { EquipmentRow } from './EquipmentRow'
import { EquipmentIcon } from '../components/NavIcons'
import './Equipment.css'

export function Equipment() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [purpose, setPurpose] = useState('')
  const [detail, setDetail] = useState('')
  const [precautions, setPrecautions] = useState('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['equipment'],
    queryFn: listEquipment,
  })

  const createMutation = useMutation({
    mutationFn: () => saveEquipment({ name, purpose, detail, precautions }),
    onSuccess: () => {
      setName('')
      setPurpose('')
      setDetail('')
      setPrecautions('')
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
    },
  })

  return (
    <div>
      <h1><EquipmentIcon size={22} /> 실험도구</h1>

      <details>
        <summary>새 실험도구 등록</summary>
        <form
          className="equipment-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (!name) return
            createMutation.mutate()
          }}
        >
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="이름" />
          <input value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="목적" />
          <textarea value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="세부내용" />
          <textarea value={precautions} onChange={(e) => setPrecautions(e.target.value)} placeholder="주의사항" />
          <button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? '등록 중...' : '등록'}
          </button>
        </form>
      </details>

      <hr />

      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="equipment-error">조회 실패: {(error as Error).message}</p>}
      {data && data.equipment.length === 0 && <p>등록된 실험도구가 없습니다.</p>}
      {data &&
        data.equipment.map((item, i) => (
          <EquipmentRow key={item.id} item={item} isFirst={i === 0} isLast={i === data.equipment.length - 1} />
        ))}
    </div>
  )
}
