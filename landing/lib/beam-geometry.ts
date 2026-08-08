// 광선 장면의 좌표 계산 — 08-08 ④.
//
// 스케치(`docs/landing-beam-sketch.html`)는 1000×2880 SVG 하나에 선과 **카피까지**
// 들어 있다. 실제 페이지는 그 비율이 안 나오고(1280px 폭에서 히어로+프리즘+궤도가
// 2256px = 1:1.76, 스케치는 1:2.88) 카피도 HTML이어야 하므로(EN이 KO보다 길고,
// 줄바꿈이 창 너비를 따라가고, 선택·스크린리더도 걸린다) 좌표를 그대로 못 베낀다.
// 그래서 **스케치는 "경로가 왜 이 모양인가"의 정본으로만 쓰고 좌표는 다시 계산한다**
// (사용자 결정). 지키는 결정들:
//   ① 창구멍에서 빛은 처음부터 옆으로 나간다(되꺾이면 ㄹ자가 된다). 직선은 프리즘에
//      닿기 직전 구간만 — 마지막 제어점을 입사 방향 위에 올려 곡선이 직선으로 수렴한다.
//   ② 빛은 꼭짓점이 아니라 **면으로** 들어가고 **분산은 유리 안에서** 시작한다.
//      두 번째 프리즘이 반드시 있어야 한다 — 뉴턴의 재합성 실험이라 다섯이 모여
//      흰빛으로 되돌아간다.
//   ③ 대포는 3시 방향, 포구가 아래. 위에서 내려온 광선이 그대로 발사 방향으로 이어진다.
//   ④ 탄도 3발은 같은 대포를 속도를 올려가며 다시 쏜 것 — 반지름을 균등하게 키운다.
//      셋 다 중심이 포구에서 수평으로만 밀려 있어 포구를 정확히 아래로 떠나고,
//      가장 먼 점이 항상 닫힌 궤도에 안쪽에서 접한다.
//   ⑤ 궤도가 닫힌 뒤에야 그 위에 워크플로우 5단계가 떠오른다.
//
// 좌표계: 래퍼 가로폭을 1000으로 놓은 단위(U). viewBox 높이도 같은 배율로 계산해서
// 넣으므로 가로세로가 균일하게 스케일된다 — `preserveAspectRatio="none"`으로 늘이면
// 궤도의 **원이 타원이 되어** 은유가 깨지기 때문에 이 방식이 아니면 안 된다.

export type Box = { x: number; y: number; w: number; h: number }

/** 앵커 박스 안의 로컬 좌표(가로 0..100 기준)를 전역 U 좌표로. 가로폭으로만 배율을
 *  잡으므로 x·y가 같은 비율로 스케일된다(=도형이 안 찌그러진다). */
function at(b: Box, lx: number, ly: number): [number, number] {
  const s = b.w / 100
  return [b.x + lx * s, b.y + ly * s]
}

function sub(a: [number, number], b: [number, number]): [number, number] {
  return [a[0] - b[0], a[1] - b[1]]
}

function norm(v: [number, number]): [number, number] {
  const l = Math.hypot(v[0], v[1]) || 1
  return [v[0] / l, v[1] / l]
}

function dist(a: [number, number], b: [number, number]) {
  return Math.hypot(a[0] - b[0], a[1] - b[1])
}

const f = (n: number) => Math.round(n * 10) / 10
const pt = (p: [number, number]) => `${f(p[0])} ${f(p[1])}`

// ── 골방(로컬 0..100 × 0..125, 앵커 박스는 aspect-[4/5]) ────────────────────
// 방 하나와 그 가운데를 지나는 벽, 벽에 뚫린 구멍 하나. 스케치와 같은 구성이다.
const ROOM = {
  rect: { x: 10, y: 10, w: 80, h: 105 },
  wallX: 50,
  hole: [50, 62] as [number, number],
}

// ── 프리즘(로컬 0..100 × 0..130, 앵커 박스는 aspect-[10/13]) ────────────────
// 삼각형 두 개와, E(입사점)에서 갈라져 두 번째 유리에서 다시 X로 모이는 다섯 갈래.
// 각 갈래는 세 구간이다: ① 유리 안에서 벌어짐 ② 공기 중 직진 ③ 두 번째 유리에서 모임.
const PRISM = {
  glass1: [
    [14, 8],
    [62, 26],
    [30, 62],
  ] as [number, number][],
  glass2: [
    [93, 70],
    [59, 108],
    [99, 116],
  ] as [number, number][],
  entry: [34.2, 15.6] as [number, number],
  // 유리 안에서 갈라져 나가는 다섯 점(출사면 B–C 위) — 빨강이 가장 덜 꺾인다.
  inGlass: [
    [52.4, 36.8],
    [50.5, 39.0],
    [48.6, 41.1],
    [46.6, 43.3],
    [44.7, 45.4],
  ] as [number, number][],
  // 공기 중 직진 뒤 두 번째 유리에 닿는 점(입사면 위)
  inAir: [
    [87.0, 77.1],
    [81.5, 83.5],
    [76.0, 89.6],
    [70.2, 95.9],
    [64.7, 102.0],
  ] as [number, number][],
  exit: [86.2, 113.4] as [number, number],
}

// ── 궤도(로컬 0..100 정사각) ───────────────────────────────────────────────
// 스케치의 지구 반지름 230을 33으로 잡으면 닫힌 궤도(340)가 48.8이 되어 박스에 꼭 찬다.
const ORBIT = {
  center: [50, 50] as [number, number],
  earthR: 33,
  orbitR: 48.8,
  muzzle: [98.8, 50] as [number, number],
  barrelTop: [98.8, 31.9] as [number, number],
  mountain: [
    [82.4, 39.4],
    [99.9, 50],
    [82.4, 60.6],
  ] as [number, number][],
  // 탄도 — [반지름, 끝점]. 반지름을 균등하게 키운 것이고, 40.6이 "떨어지는 마지막
  // 한 발"의 한계값이다(더 키우면 지면을 아예 안 스치고 지나가 이미 궤도가 된다).
  shots: [
    { r: 23.7, end: [73.1, 73.5] as [number, number] },
    { r: 32.3, end: [59.6, 81.6] as [number, number] },
    { r: 40.6, end: [19.9, 63.5] as [number, number] },
  ],
  // 닫힌 궤도 위의 워크플로우 5단계(포구에서 시계방향)
  stages: [
    [87.3, 81.3],
    [31.8, 95.2],
    [1.4, 46.6],
    [38.2, 2.7],
    [91.3, 24.2],
  ] as [number, number][],
}

export type Scene = {
  viewBox: string
  room: { rect: Box; wallX: number; wallY1: number; wallY2: number; hole: [number, number] }
  /** 창구멍 → 프리즘 입사점 */
  beam: string
  /** 프리즘 유리 두 개 */
  glass: [string, string]
  /** 다섯 갈래 (빨강→보라 순) */
  bands: string[]
  /** 재합성된 흰 광선 → 포신 위 */
  descend: string
  earth: { cx: number; cy: number; r: number }
  mountain: string
  barrel: { x: number; y: number; w: number; h: number }
  muzzleCap: { x: number; y: number; w: number; h: number }
  core: [number, number]
  shots: string[]
  closed: string
  stages: [number, number][]
  unit: number
}

/**
 * 앵커 박스 세 개(전부 래퍼 기준 px)에서 장면 전체의 path를 만든다.
 * 순수 함수 — DOM을 안 만지므로 측정과 계산이 섞이지 않는다.
 */
export function buildScene(wrapW: number, wrapH: number, boxes: { room: Box; prism: Box; orbit: Box }): Scene {
  // px → U (래퍼 가로폭 = 1000)
  const k = 1000 / wrapW
  const toU = (b: Box): Box => ({ x: b.x * k, y: b.y * k, w: b.w * k, h: b.h * k })
  const room = toU(boxes.room)
  const prism = toU(boxes.prism)
  const orbit = toU(boxes.orbit)

  const P = at

  // ① 창구멍 → 프리즘
  const hole = P(room, ...ROOM.hole)
  const entry = P(prism, ...PRISM.entry)
  // 입사 방향 = E에서 가운데 갈래(초록)로 향하는 방향. 마지막 제어점을 이 방향 위에
  // 올려야 곡선이 직선으로 수렴하면서 면으로 들어간다.
  const entryDir = norm(sub(P(prism, ...PRISM.inGlass[2]), entry))
  const d1 = dist(hole, entry)
  // 창에서는 부드럽게, 그리고 처음부터 프리즘 쪽(왼쪽)으로 나간다.
  const beam = `M ${pt(hole)} C ${pt([hole[0] - d1 * 0.3, hole[1] + d1 * 0.3])}, ${pt([
    entry[0] - entryDir[0] * d1 * 0.45,
    entry[1] - entryDir[1] * d1 * 0.45,
  ])}, ${pt(entry)}`

  // ② 프리즘 — 유리 두 개와 다섯 갈래
  const poly = (pts: [number, number][], box: Box) =>
    `M ${pts.map((p) => pt(P(box, ...p))).join(" L ")} Z`
  const glass: [string, string] = [poly(PRISM.glass1, prism), poly(PRISM.glass2, prism)]
  const exit = P(prism, ...PRISM.exit)
  const bands = PRISM.inGlass.map((g, i) => {
    const a = P(prism, ...g)
    const b = P(prism, ...PRISM.inAir[i])
    return `M ${pt(entry)} L ${pt(a)} L ${pt(b)} L ${pt(exit)}`
  })

  // ③ 재합성된 광선 → 포신 위. 출발 접선을 가운데 갈래의 진행 방향에 맞추면
  //    프리즘에서 나오는 순간 꺾이지 않고 한 줄기로 이어져 보인다.
  const exitDir = norm(sub(exit, P(prism, ...PRISM.inAir[2])))
  const barrelTop = P(orbit, ...ORBIT.barrelTop)
  const d2 = dist(exit, barrelTop)
  const descend = `M ${pt(exit)} C ${pt([exit[0] + exitDir[0] * d2 * 0.4, exit[1] + exitDir[1] * d2 * 0.4])}, ${pt(
    [barrelTop[0], barrelTop[1] - d2 * 0.45],
  )}, ${pt(barrelTop)}`

  // ④ 지구·산·대포
  const s = orbit.w / 100
  const center = P(orbit, ...ORBIT.center)
  const muzzle = P(orbit, ...ORBIT.muzzle)
  const mountain = `M ${ORBIT.mountain.map((p) => pt(P(orbit, ...p))).join(" L ")}`

  // ⑤ 탄도 3발 + 닫힌 궤도. `<circle>`은 3시 방향에서 그리기 시작해 포구를 출발점으로
  //    못 잡으므로, 닫힌 궤도는 포구에서 출발하는 반원 두 개로 그린다.
  const shots = ORBIT.shots.map(
    (sh) => `M ${pt(muzzle)} A ${f(sh.r * s)} ${f(sh.r * s)} 0 0 1 ${pt(P(orbit, ...sh.end))}`,
  )
  const R = ORBIT.orbitR * s
  const opposite: [number, number] = [center[0] - R, center[1]]
  const closed = `M ${pt(muzzle)} A ${f(R)} ${f(R)} 0 0 1 ${pt(opposite)} A ${f(R)} ${f(R)} 0 0 1 ${pt(muzzle)}`

  return {
    viewBox: `0 0 1000 ${f(wrapH * k)}`,
    room: {
      rect: {
        x: room.x + (ROOM.rect.x / 100) * room.w,
        y: room.y + (ROOM.rect.y / 100) * room.w,
        w: (ROOM.rect.w / 100) * room.w,
        h: (ROOM.rect.h / 100) * room.w,
      },
      wallX: P(room, ROOM.wallX, 0)[0],
      wallY1: P(room, 0, ROOM.rect.y)[1],
      wallY2: P(room, 0, ROOM.rect.y + ROOM.rect.h)[1],
      hole,
    },
    beam,
    glass,
    bands,
    descend,
    earth: { cx: center[0], cy: center[1], r: ORBIT.earthR * s },
    mountain,
    // 포신 치수는 지구 반지름 대비로 잡는다 — 스케치에서 반지름 230에 포신이 28×108,
    // 포구 마개가 20×18이었으므로 여기 반지름 33 기준으로는 4×15.5, 2.9×2.6이다.
    // (처음에 폭을 12로 잡았다가 포신이 전구 모양으로 뭉개졌다.)
    barrel: { x: barrelTop[0] - 2 * s, y: barrelTop[1], w: 4 * s, h: muzzle[1] - barrelTop[1] - 2.6 * s },
    muzzleCap: { x: barrelTop[0] - 1.45 * s, y: muzzle[1] - 2.6 * s, w: 2.9 * s, h: 2.6 * s },
    core: center,
    shots,
    closed,
    stages: ORBIT.stages.map((p) => P(orbit, ...p)),
    unit: s,
  }
}
