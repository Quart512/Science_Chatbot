AIsaac — 물리 연구 어시스턴트 (Docker 배포판)

필요한 것: Docker Desktop (https://www.docker.com/products/docker-desktop)
Docker Desktop을 설치하고 실행해둔 뒤 아래 스크립트를 더블클릭하세요.

실행:
  - macOS: start.command
  - Windows: start.bat

종료:
  - macOS: stop.command
  - Windows: stop.bat
  (탭/창을 닫아도 컨테이너는 계속 떠 있습니다 — 반드시 stop 스크립트로 종료하세요)

처음 실행할 때는 이미지·AI 임베딩 모델을 내려받으므로 몇 분 걸립니다.
두 번째부터는 바로 뜹니다.

AI 모델 API 키는 앱 안의 "설정" 화면에서 입력합니다.
데이터(논문·노트·대화 기록)는 이 폴더 밑에 자동으로 생기는 chroma_db/ 와 data/ 에 저장됩니다.

Intel Mac·Windows·일반 x86_64 Linux 전부 이 방식을 쓰세요 — portable 번들(별도 zip)은
Apple Silicon Mac(arm64)에서만 됩니다(onnxruntime이 Intel Mac용 wheel을 안 내서
원리적으로 막혀 있습니다, 자세한 이유는 저장소의 docs/RoadMap.md 참고).
