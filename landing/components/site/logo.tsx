import { cn } from "@/lib/utils"

// 08-07 — public/aisaac-logo.png 자체가 깨진 파일이었다: 알파 채널이 있는 척했지만
// 실제로는 "배경"이라고 생각한 영역까지 거의 불투명(232~255)하고 어두운 노이즈가
// 박혀 있었다 — frontend-react/Logo.tsx 주석이 기록해둔 "처음 시도했던 파일은
// 체크무늬가 픽셀로 박혀있어 투명화가 안 됐다"는 바로 그 기각된 파일과 같은 증상
// (실제로 픽셀 알파값을 찍어 확인). frontend-react/public/aisaac-logo.png는 그때
// 검증을 통과한 정상 파일(코너 알파=0 실측 확인)이라 이걸 그대로 가져와 교체했다.
// 원본 아트워크(257x309)는 유리 프리즘+무지개 궤도 링 그림이라 흰 배경에서
// 유리/흰 요소가 안 보인다 — 배지 위에 얹어야 한다.
const ARTWORK_ASPECT_RATIO = 257 / 309

// 08-07 — 이 로고가 예전 frontend-react/src/components/Logo.tsx와 같은 문제를
// 그대로 갖고 있었다(별개 프로젝트라 그때 수정이 여기엔 안 갔음): ① 정사각형 배지에
// 넓은 원본을 욱여넣으려고 260% 확대+임의 위치로 크롭해서 그림이 잘리고 여백이
// 아예 없었다 — background-size: contain(비율 유지, 안 잘림)으로 교체. ② 배지가
// 거의 검정(#0b0d12)이라 너무 어둡다는 지적 — frontend-react 쪽에서 같은 문제를
// 겪고 실측 비교 후 확정한 값(#c8ccd4, 흰 프리즘과는 갈리면서 최대한 밝은 회색)을
// 그대로 재사용해 브랜드 톤을 통일한다. ③ 크기를 키움(기본 28→36) — 위 두 수정으로
// 여백이 생기면서 nav 높이(h-16=64px)에 비해 작아 보이는 걸 상쇄.
// 08-08 — 배지를 한 단계 더 어둡게(#c8ccd4 → #b4b8c0, 사용자 지적). frontend-react
// Logo.css는 여전히 #c8ccd4다 — 이번 요청이 랜딩 한정이라 그쪽은 안 건드렸다.
// 두 화면 톤을 다시 맞추려면 frontend-react 쪽도 같이 갱신해야 한다.
export function Logo({
  className,
  size = 36,
  showWordmark = true,
}: {
  className?: string
  size?: number
  showWordmark?: boolean
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span
        aria-hidden="true"
        className="inline-block shrink-0 overflow-hidden rounded-[30%] bg-[#b4b8c0]"
        style={{
          width: size * ARTWORK_ASPECT_RATIO,
          height: size,
          padding: size * 0.16,
          boxSizing: "content-box",
          backgroundOrigin: "content-box",
          backgroundImage: "url(/aisaac-logo.png)",
          backgroundRepeat: "no-repeat",
          backgroundSize: "contain",
          backgroundPosition: "center",
        }}
      />
      {showWordmark && (
        <span className="font-mono text-sm font-semibold tracking-tight">AIsaac</span>
      )}
    </span>
  )
}
