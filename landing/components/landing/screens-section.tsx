"use client"

import { useState } from "react"
import { useLanguage } from "@/lib/i18n"
import type { TKey } from "@/lib/i18n"

// 08-08 신설 — 랜딩에 서비스를 소개하는 자리가 아예 없던 것을 메운다(RoadMap "08-08
// 결론" 진단 ②). 앱 사이드바를 그대로 재현한 목록에서 화면 하나를 골라 보는 방식이다.
//
// 지킨 제약 셋(로드맵):
//  ① 탭은 "기능"이 아니라 "화면"이다 — i18n의 screens.* 주석 참고.
//  ② 호버가 아니라 클릭으로 전환한다 — 모바일에 호버가 없다.
//  ③ 기본 하나는 펼쳐진 채 시작한다 — 인터랙션을 안 하는 방문자에게 정보량이 0이면 안 된다.
//     기본값은 사이드바 첫 항목(홈)이 아니라 챗봇이다: 홈은 대시보드라 "이 앱이 무엇을
//     해주는가"를 가장 약하게 보여준다(통계 타일과 최근 활동 이야기뿐). 탭 순서는
//     사이드바 그대로 두고 기본 선택만 옮겼다 — 순서를 건드리면 목록을 재현한 의미가 깨진다.
//
// 아이콘 대신 색 점을 쓴 이유: 앱 네비는 손으로 그린 SVG 6개(`NavIcons.tsx`)를 쓰는데,
// 랜딩은 별도 Next 앱이라 그걸 가져오면 토큰 이름까지 다른 사본이 두 벌 생겨 어긋난다.
// 색 배정만 앱과 똑같이 맞추면(챗봇=빨강 … 지식노트=보라) 사본 없이 같은 정체성이 남고,
// 색 점 자체는 궤도 섹션이 이미 쓰는 이 저장소의 관용구다. 홈은 앱에도 아이콘이 없어
// 색을 새로 지어내지 않고 빈 테두리 점으로 둔다.
type Screen = {
  id: string
  group: "main" | "library"
  name: TKey
  title: TKey
  desc: TKey
  color: string | null
}

const screens: Screen[] = [
  { id: "home", group: "main", name: "screens.home.name", title: "screens.home.title", desc: "screens.home.desc", color: null },
  { id: "chat", group: "main", name: "screens.chat.name", title: "screens.chat.title", desc: "screens.chat.desc", color: "var(--spectrum-red)" },
  { id: "research", group: "main", name: "screens.research.name", title: "screens.research.title", desc: "screens.research.desc", color: "var(--spectrum-orange)" },
  { id: "papers", group: "library", name: "screens.papers.name", title: "screens.papers.title", desc: "screens.papers.desc", color: "var(--spectrum-yellow)" },
  { id: "interests", group: "library", name: "screens.interests.name", title: "screens.interests.title", desc: "screens.interests.desc", color: "var(--spectrum-green)" },
  { id: "equipment", group: "library", name: "screens.equipment.name", title: "screens.equipment.title", desc: "screens.equipment.desc", color: "var(--spectrum-blue)" },
  { id: "notes", group: "library", name: "screens.notes.name", title: "screens.notes.title", desc: "screens.notes.desc", color: "var(--spectrum-violet)" },
]

const groups: { key: Screen["group"]; label: TKey }[] = [
  { key: "main", label: "screens.group.main" },
  { key: "library", label: "screens.group.library" },
]

export function ScreensSection() {
  const { t } = useLanguage()
  const [activeId, setActiveId] = useState("chat")
  // 힌트를 언제 거둘지만 판단하는 값이라 "무엇을 눌렀는지"는 안 본다.
  const [touched, setTouched] = useState(false)
  const active = screens.find((s) => s.id === activeId) ?? screens[0]

  return (
    <section id="screens" className="scroll-mt-16 border-b border-border">
      <div className="mx-auto max-w-6xl px-5 py-20 md:py-24">
        <p className="font-mono text-xs uppercase tracking-widest text-accent">{t("screens.kicker")}</p>
        <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("screens.title")}
        </h2>
        <p className="mt-5 max-w-xl text-pretty leading-relaxed text-muted-foreground">
          {t("screens.desc")}
        </p>

        <div className="mt-10 grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
          {/* min-w-0 — 이게 없으면 그리드 칸의 최소 폭이 min-content(= 안 접히는 가로
              탭 줄 전체 폭)로 잡혀서, 목록이 자기 안에서 스크롤되는 대신 페이지 전체를
              가로로 늘려버린다. 모바일에서 실제로 페이지 폭이 375→822로 벌어졌다. */}
          <div className="min-w-0">
            {/* 첫 클릭 뒤엔 opacity로만 숨긴다 — display로 지우면 목록이 위로 튀어오른다. */}
            <p
              aria-hidden={touched}
              className={`mb-3 flex items-center gap-1.5 font-mono text-xs text-accent transition-opacity duration-300 ${
                touched ? "opacity-0" : "opacity-100"
              }`}
            >
              <span className="animate-pulse" aria-hidden="true">
                ▸
              </span>
              {t("screens.hint")}
            </p>

            {/* 좁은 화면에서는 세로 목록이 화면을 다 잡아먹어 가로 스크롤 줄로 바꾼다.
                그룹 제목은 그때 자리가 없어 숨기고, `display:contents`로 그룹 <div>를
                레이아웃에서 빼 버튼들이 바깥 flex 줄에 바로 참여하게 한다. */}
            <div className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:gap-0 lg:overflow-visible lg:pb-0">
              {groups.map((g, gi) => (
                <div key={g.key} className="contents lg:block">
                  <p
                    className={`hidden font-mono text-[0.7rem] uppercase tracking-widest text-muted-foreground lg:block ${
                      gi === 0 ? "" : "mt-5"
                    }`}
                  >
                    {t(g.label)}
                  </p>
                  <div className="contents lg:mt-2 lg:flex lg:flex-col lg:gap-1">
                    {screens
                      .filter((s) => s.group === g.key)
                      .map((s) => {
                        const isActive = s.id === active.id
                        return (
                          <button
                            key={s.id}
                            type="button"
                            aria-controls="screens-panel"
                            aria-current={isActive ? "true" : undefined}
                            onClick={() => {
                              setActiveId(s.id)
                              setTouched(true)
                            }}
                            className={`flex shrink-0 cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-left text-sm transition-colors lg:w-full ${
                              isActive
                                ? "border-accent bg-secondary text-foreground"
                                : "border-border bg-card text-muted-foreground hover:border-accent/40 hover:text-foreground"
                            }`}
                          >
                            <span
                              aria-hidden="true"
                              className="h-2 w-2 shrink-0 rounded-full"
                              style={
                                s.color
                                  ? { backgroundColor: s.color }
                                  : { border: "1px solid var(--muted-foreground)" }
                              }
                            />
                            <span className="whitespace-nowrap">{t(s.name)}</span>
                          </button>
                        )
                      })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* aria-live — 버튼과 떨어진 자리의 글이 바뀌므로 스크린리더에 알려야 한다.
              key로 노드를 갈아끼워 페이드인을 다시 태운다: 클릭에 화면이 눈에 띄게
              반응하는 것 자체가 "누를 수 있다"를 알리는 세 겹 중 하나다. */}
          <div
            id="screens-panel"
            aria-live="polite"
            className="rounded-xl border border-border bg-card p-6 md:p-8 lg:min-h-[16rem]"
          >
            <div key={active.id} className="animate-[fadein_240ms_ease-out]">
              <p className="font-mono text-xs uppercase tracking-widest text-accent">{t(active.name)}</p>
              <h3 className="mt-3 text-balance text-xl font-semibold tracking-tight sm:text-2xl">
                {t(active.title)}
              </h3>
              <p className="mt-4 max-w-2xl text-pretty leading-relaxed text-muted-foreground">
                {t(active.desc)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
