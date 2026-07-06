from dotenv import load_dotenv
load_dotenv()
from langsmith import Client
from pydantic import BaseModel, Field
client = Client()

examples = [
    ("원자란 무엇인가?", "모든 물질을 구성하는 작은 입자로, 양성자와 중성자로 이루어진 핵과 그 주변을 도는 전자로 구성됨"),
    ("고체에서 원자들은 어떻게 결합하는가?", "원자들은 약간 떨어져 있을 때 서로 끌어당기지만 너무 가까워지면 밀어냄"),
    ("원자 가설이란 무엇인가?", "모든 사물은 영구적으로 운동하는 작은 입자인 원자로 이루어져 있다는 것"),
    ("온도와 원자 운동의 관계는?", "온도가 높을수록 원자가 더 빠르게 운동함"),
    ("원자핵은 무엇으로 이루어져 있는가?", "양성자와 중성자"),
    ("원자의 화학적 정체성을 결정하는 것은?", "핵 속의 양성자 수"),
    ("탄소란 무엇인가?", "양성자 6개와 전자 6개를 가진 원자, 화학 주기율표 6번 원소"),
    ("전자가 띠는 전하는?", "음전하"),
    ("물리학은 무엇을 연구하는가?", "자연의 근본적인 규칙을 찾는 학문"),
    ("액체 상태의 원자는 고체와 어떻게 다른가?", "고체보다 자유롭게 움직이며 고정된 위치에 묶여있지 않음"),
]

#dataset = client.create_dataset("feynman-rag-eval")
#client.create_examples(
#    inputs=[{"question": q} for q, _ in examples],
#    outputs=[{"answer": a} for _, a in examples],
#    dataset_id=dataset.id
#)

from graph import app
class evaluated(BaseModel):
    score: float = Field(ge=0, le=1)

def graph_fn(inputs):
    return {"answer": app.invoke({"question": inputs["question"]})["answer"]}
from langsmith.evaluation import evaluate
from langchain_google_genai import ChatGoogleGenerativeAI

def correctness_evaluator(run, example):
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash").with_structured_output(evaluated)
    question = example.inputs["question"]
    reference = example.outputs["answer"]
    prediction = run.outputs["answer"]
    
    prompt = f"""질문에 대한 답변이 참고 답변과 의미적으로 일치하는지 평가해줘.
질문: {question}
참고 답변: {reference}
평가 대상 답변: {prediction}
0.0(완전 틀림)~1.0(완전 정확) 사이 숫자만 답해줘."""
    
    score_result = llm.invoke(prompt).score
    return {"key": "correctness", "score": score_result}


results = evaluate(
    graph_fn,
    data="feynman-rag-eval",
    evaluators=[correctness_evaluator],
)
print(results)