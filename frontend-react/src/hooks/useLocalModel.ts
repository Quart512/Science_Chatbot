import { useQuery } from '@tanstack/react-query'
import { getLocalModelStatus, type LocalModelStatus } from '../api/settings'
import { CHAT_MODELS } from './useChatThread'

// 로컬 모델(Qwen-tuned) 설치 상태(08-09). 설정 화면·첫 실행 안내창·모델 드롭다운이
// 같이 쓴다 — queryKey가 같으므로 react-query가 요청을 하나로 합쳐준다.
//
// 받는 중일 때만 폴링한다. 설치는 사용자가 버튼을 눌러야 시작되고 그때 mutation이
// 이 쿼리를 무효화하므로, 평소에 2초마다 물어볼 이유가 없다.
export function useLocalModel() {
  return useQuery<LocalModelStatus>({
    queryKey: ['local-model'],
    queryFn: getLocalModelStatus,
    refetchInterval: (query) => (query.state.data?.state === 'downloading' ? 2000 : false),
  })
}

// 드롭다운에 실제로 고를 수 있는 모델만 남긴다(08-09).
//
// 이전엔 `Qwen-tuned`가 모든 사용자에게 보였는데, 배포판에는 GGUF도 llama-server도 안
// 실려서 **고르면 100% 접속 실패**였다. 하필 API 키가 없어 막힌 사용자가 "키 없이 되는 게
// 있나" 하고 그걸 고르게 되는 구조라, 가장 헤매는 사람을 정확히 함정에 빠뜨렸다.
//
// 조회 전(data === undefined)에는 로컬 모델을 뺀 목록을 준다 — 잠깐 보였다 사라지는
// 것보다 안 보이다가 나타나는 쪽이 덜 혼란스럽다.
export const LOCAL_CHAT_MODEL = 'Qwen-tuned'

export function useAvailableChatModels(): string[] {
  const { data } = useLocalModel()
  const installed = data?.installed ?? false
  return CHAT_MODELS.filter((m) => m !== LOCAL_CHAT_MODEL || installed)
}
