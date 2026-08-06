import { cn } from "@/lib/utils"

/**
 * AIsaac brand mark.
 *
 * The source artwork (public/aisaac-logo.png) is a glass prism refracting a
 * rainbow spectrum wrapped by a white orbital ring on a transparent canvas.
 * It carries a lot of empty padding and its glass/white elements vanish on a
 * light background, so we crop to the content region and sit it on a dark
 * badge — keeping it crisp in both light and dark themes.
 */
export function Logo({
  className,
  size = 28,
  showWordmark = true,
}: {
  className?: string
  size?: number
  showWordmark?: boolean
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span
        aria-hidden="true"
        className="inline-block shrink-0 overflow-hidden rounded-[30%] bg-[#0b0d12] ring-1 ring-white/10"
        style={{
          width: size,
          height: size,
          backgroundImage: "url(/aisaac-logo.png)",
          backgroundRepeat: "no-repeat",
          backgroundSize: "260%",
          backgroundPosition: "49% 48%",
        }}
      />
      {showWordmark && (
        <span className="font-mono text-sm font-semibold tracking-tight">AIsaac</span>
      )}
    </span>
  )
}
