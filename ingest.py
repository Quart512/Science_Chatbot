#import chromadb
from dotenv import load_dotenv
import os
import hashlib
#from google import genai

#langchain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Chroma DB 가져오기.  langchain이 알아서

#api key 가져오기 (임베딩은 로컬이라 이제 필요 없지만, 다른 데서 쓸 수도 있어서 유지)
load_dotenv()


# 문서 청크 나누기 500(overlap=50)    langchain으로 간소화
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

SOURCE="feynman"
with open(f"docs/{SOURCE}.txt", "r", encoding="utf-8") as f:
    text = f.read()
    chunks = splitter.split_text(text)

# 로컬 임베딩으로 rate limit 부담이 없어져 전체 청크 사용
# chunks = chunks[:200]  # 테스트용으로 줄이고 싶으면 이 줄 활성화

# 청크 인덱스 기반 id — 중복 안 생김
ids = [(f"{SOURCE}-{i}") for i in range(len(chunks))]

# 로컬 임베딩 모델 사용 (BAAI/bge-m3, 다국어) — API 호출이 아니라 로컬에서 실행되므로
# gemini rate limit과 무관하고, 검색 시점에도 외부 API 의존이 없어짐
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
vectorstore = Chroma.from_texts(chunks, 
                                embeddings, 
                                ids=ids, 
                                persist_directory="./chroma_db", 
                                collection_name="feynman", 
                                metadatas=[{"source": SOURCE} for i in range(len(chunks))]
                                )
    

print("finished!")
