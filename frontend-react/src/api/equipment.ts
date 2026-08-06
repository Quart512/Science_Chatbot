import { apiFetch } from './client'

export interface Equipment {
  id: number
  name: string
  purpose: string
  detail: string
  precautions: string
}

export interface SaveEquipmentBody {
  name: string
  purpose?: string
  detail?: string
  precautions?: string
  update_existing_id?: number
}

export function listEquipment() {
  return apiFetch<{ equipment: Equipment[] }>('/equipment')
}

export function saveEquipment(body: SaveEquipmentBody) {
  return apiFetch<{ equipment_id: number; action: string }>('/equipment', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function deleteEquipment(id: number) {
  return apiFetch<{ equipment_id: number; action: string }>(`/equipment/${id}`, { method: 'DELETE' })
}

export function moveEquipment(id: number, direction: 'up' | 'down') {
  return apiFetch<{ equipment_id: number; moved: boolean }>(`/equipment/${id}/move?direction=${direction}`, {
    method: 'POST',
  })
}
