"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

export type Theme = "light" | "dark"

type Ctx = {
  theme: Theme
  setTheme: (t: Theme) => void
}

const ThemeContext = createContext<Ctx | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  // 08-08 — 랜딩에는 라이트/다크를 바꾸는 버튼이 없다(이 컨텍스트를 실제로
  // 소비하는 곳이 없다). 그래서 기본값이 곧 랜딩의 유일한 모습이다. 골방은
  // 원래 어두우니 전환 연출 없이 히어로부터 딥 블랙으로 간다(RoadMap "08-08
  // 결론" 참고) — 취향이 아니라 스크롤 광선 서사에서 나온 결정이다.
  const [theme, setTheme] = useState<Theme>("dark")

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle("dark", theme === "dark")
    root.style.colorScheme = theme
  }, [theme])

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider")
  return ctx
}
