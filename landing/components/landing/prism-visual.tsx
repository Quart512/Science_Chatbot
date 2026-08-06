import { cn } from "@/lib/utils"

const bands = [
  { color: "var(--spectrum-violet)", y2: 44 },
  { color: "var(--spectrum-indigo)", y2: 62 },
  { color: "var(--spectrum-blue)", y2: 80 },
  { color: "var(--spectrum-green)", y2: 98 },
  { color: "var(--spectrum-yellow)", y2: 116 },
  { color: "var(--spectrum-orange)", y2: 134 },
  { color: "var(--spectrum-red)", y2: 152 },
]

export function PrismVisual({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 320 200"
      className={cn("h-full w-full", className)}
      fill="none"
    >
      {/* incoming white beam */}
      <line
        x1="0"
        y1="100"
        x2="132"
        y2="100"
        stroke="currentColor"
        strokeWidth="2"
        className="text-foreground"
      >
        <animate attributeName="opacity" values="0.4;1;0.4" dur="3s" repeatCount="indefinite" />
      </line>

      {/* prism */}
      <path
        d="M150 58 L188 138 L112 138 Z"
        stroke="currentColor"
        strokeWidth="1.25"
        className="text-muted-foreground"
        fill="var(--card)"
        fillOpacity="0.5"
      />

      {/* refracted spectrum */}
      {bands.map((b, i) => (
        <line
          key={i}
          x1="168"
          y1="100"
          x2="320"
          y2={b.y2}
          stroke={b.color}
          strokeWidth="2"
          strokeLinecap="round"
        >
          <animate
            attributeName="opacity"
            values="0.35;1;0.35"
            dur="3s"
            begin={`${i * 0.18}s`}
            repeatCount="indefinite"
          />
        </line>
      ))}
    </svg>
  )
}
