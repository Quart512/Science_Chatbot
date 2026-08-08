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
// 08-08 — 배지를 한 단계 더 어둡게(#c8ccd4 → #b4b8c0, 사용자 지적)까지 했었는데,
// 바로 다음 라운드에서 배지 자체를 없앴다(아래 주석 참고) — 이 히스토리는 그
// 판단 과정 기록으로 남겨둔다.
//
// 08-08 후속(사용자 지적 — "로고가 이상하다, 예전 사진 같다") — 배지를 완전히
// 없앴다. 원인은 이미지가 아니었다(landing과 frontend-react의 aisaac-logo.png는
// MD5까지 같은 파일) — `frontend-react/src/components/Logo.css`가 08-07에 이미
// "다크 테마에서는 배지를 투명으로 둔다"고 결정해뒀는데(라이트에서만 흰 프리즘이
// 밝은 배경에 묻히지 않게 회색판을 깜) 랜딩은 다크 단일 테마로 확정됐으면서도
// (RoadMap "08-08 결론" — 테마 전환 버튼 자체가 없음) 이 배지 컴포넌트만 그 결정을
// 안 따라가 항상 회색 사각 배지를 깔고 있었다. 실측 비교(dev 서버 스크린샷) —
// 배지를 없앤 쪽이 실제 앱의 다크 모드 렌더와 같고, 유리 질감·무지개 테두리가
// 검정 배경 위에 또렷이 뜬다. 배지가 있으면 그림이 회색 카드 안에 갇힌 것처럼
// 보인다 — 08-07 이전(정사각형 크롭+배지 방식)의 흔적이 남아 있던 것.
//
// 패딩(frontend-react의 BADGE_PADDING_RATIO 상당)도 같이 뺐다 — 그건 "테마 전환
// 시 레이아웃이 안 흔들리게" 두 테마 공통으로 유지하는 값인데, 랜딩은 테마 전환이
// 아예 없어 그 이유가 적용 안 된다.
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
        className="inline-block shrink-0"
        style={{
          width: size * ARTWORK_ASPECT_RATIO,
          height: size,
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
