from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

persist_directory="./chroma_db"
collection_name="feynman"

#chromadb 불러오기
# 로컬 임베딩 모델 사용 (BAAI/bge-m3, 다국어) — ingest.py와 반드시 같은 모델이어야 함
# (모델이 다르면 벡터 공간이 달라져서 유사도 검색이 무의미해짐)
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3") # 이건 모델 선택 불가-이미 임베딩함
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=collection_name
)

