import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import remarkCjkFriendly from 'remark-cjk-friendly'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import './Markdown.css'

// LLM이 생성한 텍스트(##/**/목록/$...$ 등)를 마크다운+수식으로 렌더링(08-07, RoadMap
// "LLM 생성 텍스트를 마크다운+수식으로 렌더링" 항목). 마크다운만 먼저 넣어 실측한 결과
// (같은 항목 참고) — CommonMark는 $...$ 문법이 없을 뿐 아니라, LaTeX 아래첨자(\mathbf{F}_{AB})의
// 언더스코어를 강조(이탤릭) 구분자로 잘못 먹어 서로 다른 문장 사이를 이탤릭으로
// 묶어버리는 부작용까지 있었다 — remark-math가 $...$/$$...$$를 먼저 수식 노드로
// 떼어내야 그 안의 언더스코어가 마크다운 파서에 안 잡힌다.
//
// 08-07 후속 — 배포 직후 "**용어(영어 병기)**는"처럼 볼드가 닫는 괄호 바로 뒤에서
// 끝나고 공백 없이 조사가 붙으면 안 풀리는 문제를 실사용에서 재현("[한계]" 완료 표
// 항목 참고). CommonMark의 강조 판정 규칙(flanking delimiter run)이 애초에 CJK를
// 고려 안 해서 생기는, 표준 파서 자체의 잘 알려진 문제(commonmark-spec#650) — 우리
// 코드로 못 고치는 지점이라 정확히 이 문제를 위한 remark-cjk-friendly 플러그인을
// 붙였다. remarkMath 뒤·rehype 앞에 두는 순서는 패키지 README의 권장 순서
// (remarkGfm 자리에 remarkMath) 그대로. 이 저장소 실제 의존성으로 12개 케이스
// 전/후 대조해 실사용 사례 2건 포함 5건 고쳐지고 회귀 0건 확인(검증 스크립트는
// 확인 후 삭제 — 이 주석이 그 결과의 기록).
export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkMath, remarkCjkFriendly]} rehypePlugins={[rehypeKatex]}>
        {text}
      </ReactMarkdown>
    </div>
  )
}
