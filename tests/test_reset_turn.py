# reset_turn은 아키텍처 개편으로 제거됨 — orchestrator.py가 매번 fresh하게 invoke하므로
# (checkpointer 없음) State 필드들이 Pydantic 기본값으로 이미 "리셋"된 채 시작한다.
# 이 파일은 로컬에서 삭제해줘: rm tests/test_reset_turn.py
