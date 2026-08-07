import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import './Markdown.css'

// LLM이 생성한 텍스트(##/**/목록/$...$ 등)를 마크다운+수식으로 렌더링(08-07, RoadMap
// "LLM 생성 텍스트를 마크다운+수식으로 렌더링" 항목). 마크다운만 먼저 넣어 실측한 결과
// (같은 항목 참고) — CommonMark는 $...$ 문법이 없을 뿐 아니라, LaTeX 아래첨자(\mathbf{F}_{AB})의
// 언더스코어를 강조(이탤릭) 구분자로 잘못 먹어 서로 다른 문장 사이를 이탤릭으로
// 묶어버리는 부작용까지 있었다 — remark-math가 $...$/$$...$$를 먼저 수식 노드로
// 떼어내야 그 안의 언더스코어가 마크다운 파서에 안 잡힌다.
export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {text}
      </ReactMarkdown>
    </div>
  )
}
