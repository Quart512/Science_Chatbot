from langchain_chroma import Chroma

from embeddings import BGEM3OnnxEmbeddings

persist_directory="./chroma_db"


#chromadb 불러오기
# 로컬 임베딩 모델 사용 (BAAI/bge-m3, 다국어) — ingest.py와 반드시 같은 모델이어야 함
# (모델이 다르면 벡터 공간이 달라져서 유사도 검색이 무의미해짐)
# 08-05에 백엔드를 sentence-transformers(torch) → onnxruntime으로 교체했다. **모델은
# 그대로 bge-m3**이고 가중치도 같아 벡터가 1e-07 수준으로 일치하므로 위 제약을 그대로
# 만족한다(재색인 불필요 — 근거는 embeddings.py 모듈 docstring 참고). 여기서 객체를
# 만드는 시점도 예전과 같은 import 시점으로 유지했다 — main.py의 /api/health가
# "lifespan이 끝나야(임베딩 모델 로딩 완료 후) 라우트가 뜬다"를 전제하고 있어서다.
embeddings = BGEM3OnnxEmbeddings() # 이건 모델 선택 불가-이미 임베딩함

collection_name="feynman"
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=collection_name
)

# 논문 요약기(②a, paper_ingest.py) 전용 컬렉션 — 같은 임베딩 모델·persist_directory를
# 공유하되(재로딩 방지) 파인만 강의록과는 성격이 다른 근거라 컬렉션을 분리한다.
# doc_type(fulltext_chunk/summary/abstract)으로 논문 내부 구분은 이 컬렉션 안에서 한다.
papers_collection_name = "papers"
papers_vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=papers_collection_name,
)

# 지식 노트(08-03) 전용 컬렉션 — 검색용 청크만 담는 disposable 인덱스다. 진짜 텍스트는
# knowledge_notes.py가 SQLite(data/app.db)에 두고 편집도 거기서 한다(관심사를 VDB에서
# RDB로 옮긴 것과 같은 이유 — "편집이 일급 연산이면 VDB가 안 맞는다", RoadMap 07-28
# 참고). 이 컬렉션은 노트가 수정될 때마다 그 노트 몫을 통째로 지우고 다시 만든다.
notes_collection_name = "notes"
notes_vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=notes_collection_name,
)

