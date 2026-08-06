import { useEffect } from 'react'

const FADE_DELAY_MS = 800

// 스크롤 중에만 스크롤바를 보여주기 위한 전역 훅(08-06, 사용자 요청) — CSS엔 "스크롤
// 진행 중"을 잡는 표준 가상클래스가 없어(스크롤바 자체를 드래그할 때 반응하는 :active
// 류와는 다름) JS로 감지해야 한다. scroll 이벤트는 버블링하지 않으므로 document에
// capture:true로 걸어야 왼쪽 네비·챗 패널·본문 등 어디서 스크롤이 발생하든 다 잡힌다.
// 휠뿐 아니라 트랙패드·키보드·스크롤바 드래그도 전부 'scroll' 이벤트로 들어오니
// 이 하나로 다 커버된다. 요소별로 별도 타이머가 필요해서(동시에 여러 곳을 스크롤할
// 수 있음) WeakMap으로 요소→타이머ID를 따로 들고 있는다.
export function useScrollbarAutoHide() {
  useEffect(() => {
    const timers = new WeakMap<Element, ReturnType<typeof setTimeout>>()

    function handleScroll(e: Event) {
      const target = e.target === document ? document.documentElement : (e.target as Element)
      target.classList.add('is-scrolling')

      const existing = timers.get(target)
      if (existing) clearTimeout(existing)
      timers.set(
        target,
        setTimeout(() => target.classList.remove('is-scrolling'), FADE_DELAY_MS),
      )
    }

    document.addEventListener('scroll', handleScroll, { capture: true, passive: true })
    return () => document.removeEventListener('scroll', handleScroll, { capture: true })
  }, [])
}
