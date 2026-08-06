/** @type {import('next').NextConfig} */
const nextConfig = {
  // 08-06 — EC2에 정적 파일로 서빙(nginx)하기로 결정(RoadMap "EC2 배포 트랙 폐지"
  // 참고 — 앞으로 EC2는 랜딩/다운로드 페이지만 서빙). 서버 API·동적 라우트가 하나도
  // 없는 순수 마케팅 페이지라 `next start`로 Node 프로세스를 계속 띄워둘 이유가
  // 없다 — `output: "export"`로 `out/`에 정적 HTML/JS/CSS만 뽑아 nginx가 파일로
  // 서빙하면 EC2에서 관리할 프로세스가 하나 줄어든다(PM2/systemd 불필요).
  output: "export",
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
