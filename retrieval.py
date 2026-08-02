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

# 논문 요약기(②a, paper_ingest.py) 전용 컬렉션 — 같은 임베딩 모델·persist_directory를
# 공유하되(재로딩 방지) 파인만 강의록과는 성격이 다른 근거라 컬렉션을 분리한다.
# doc_type(fulltext_chunk/summary/abstract)으로 논문 내부 구분은 이 컬렉션 안에서 한다.
papers_collection_name = "papers"
papers_vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=papers_collection_name,
)

