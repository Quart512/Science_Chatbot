from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

persist_directory="./chroma_db"


#chromadb 불러오기
# 로컬 임베딩 모델 사용 (BAAI/bge-m3, 다국어) — ingest.py와 반드시 같은 모델이어야 함
# (모델이 다르면 벡터 공간이 달라져서 유사도 검색이 무의미해짐)
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3") # 이건 모델 선택 불가-이미 임베딩함

collection_name="feynman"
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=collection_name
)

# =========================================================
# 논문 요약기(②a, paper_ingest.py)가 쓰는 별도 컬렉션. 물리 QA용 "feynman" 컬렉션과
# 같은 임베딩 모델(embeddings)·persist_directory를 공유하되(모델 재로딩 방지·디스크
# 위치 통일), 컬렉션은 분리한다 — 논문 전문·요약과 파인만 강의록은 성격이 다른 근거라
# 섞이면 검색 품질이 떨어진다. 한 컬렉션 안에서 doc_type(fulltext_chunk/summary)으로
# 나누는 건 같은 논문 안에서의 구분이고, 이건 그 상위의 "논문 vs QA 강의록" 구분이다.
papers_collection_name = "papers"
papers_vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=papers_collection_name,
)

