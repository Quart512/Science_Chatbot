"""
pytest가 tests/ 아래 테스트 파일들을 수집(import)하기 전에 항상 먼저 실행되는 설정 파일.
이 파일 하나로 아래 내용이 모든 테스트에 일관되게 적용된다 — 어떤 순서로 테스트 파일이
실행되든 안전하다.

--- 왜 필요한가 ---
graph.py는 최상단에서 `from retrieval import vectorstore`를 실행한다.
retrieval.py는 그 vectorstore를 만들면서 BAAI/bge-m3 임베딩 모델(~2GB)을 로드한다 —
즉 graph.py를 import하기만 해도 이 무거운 로딩이 함께 실행된다.

route_by_fix처럼 vectorstore를 전혀 쓰지 않는 순수 함수를 테스트할 때도 이 로딩을
피할 수 없으므로, graph.py가 import되기 전에 sys.modules에 가짜 retrieval 모듈을
먼저 등록해 진짜 retrieval.py(무거운 로딩)가 실행되지 않도록 막는다.

--- retrieve() 노드처럼 vectorstore가 실제로 필요한 테스트를 나중에 추가한다면 ---
graph.py는 `from retrieval import vectorstore`로 가져오므로, graph 모듈 안에도
`vectorstore`라는 이름이 그대로 생긴다. 개별 테스트에서
    monkeypatch.setattr("graph.vectorstore", 원하는_가짜객체)
로 그때그때 원하는 가짜 객체를 넣으면 된다 — 이 conftest.py를 다시 건드릴 필요 없음.

--- API 키 더미값 ---
models.py의 model_map은 import되는 순간 ChatGoogleGenerativeAI(...) 등을 생성하는데,
이 생성자가 "API 키가 실제로 존재하는지"를 그 자리에서 검사한다(진짜 네트워크 호출은
.invoke() 시점에만 일어나 — 키 존재 여부만 보는 것). 로컬은 .env로 채워지지만 CI 등
키가 없는 환경에서는 graph.py를 import하는 것만으로 즉시 에러가 난다. 더미 문자열이면
이 생성 시점 검사는 통과하고, 테스트에서 실제로 .invoke()를 부르지만 않으면(지금 우리
테스트들은 안 부름) 진짜 API 호출도, 진짜 키도 필요 없다.
os.environ.setdefault를 쓰므로 로컬에서 .env로 이미 값이 있으면 그대로 두고,
없을 때만 더미로 채운다.
"""
import os
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy-key")

sys.modules.setdefault("retrieval", SimpleNamespace(vectorstore=None))


@pytest.fixture
def make_state():
    """테스트용 State를 최소 필드로 만드는 팩토리를 제공하는 fixture.
    (State 인스턴스 하나가 아니라 '만드는 함수'를 리턴하는 이유: 테스트마다
    question 외의 필드를 서로 다르게 덮어써야 하므로, 고정된 값 하나로는 부족함)

    테스트 함수 인자 이름을 make_state로 두기만 하면 pytest가 이 fixture를 자동으로
    찾아 주입해준다 — import는 따로 필요 없음."""
    from graph import State

    def _make_state(**overrides):
        defaults = {"question": "테스트 질문"}
        defaults.update(overrides)
        return State(**defaults)

    return _make_state
