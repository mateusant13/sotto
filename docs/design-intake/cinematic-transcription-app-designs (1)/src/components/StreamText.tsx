import { cn } from "@/utils/cn";

/**
 * Renders words as they stream in. Each word eases in with a small blur-lift;
 * the tail word stays slightly translucent, the way live captions do while the
 * engine is still deciding on it.
 */
export function StreamText({
  words,
  className,
  wordClassName,
  soft = true,
  caret = true,
  caretColor,
  caretClassName,
}: {
  words: string[];
  className?: string;
  wordClassName?: string;
  soft?: boolean;
  caret?: boolean;
  caretColor?: string;
  caretClassName?: string;
}) {
  if (!words.length) return null;
  return (
    <span className={className}>
      {words.map((w, i) => {
        const isTail = i === words.length - 1;
        return (
          <span
            key={i}
            className={cn(
              "mr-[0.3em] inline-block whitespace-pre",
              soft ? "anim-word-soft" : "anim-word",
              wordClassName,
            )}
            style={{
              opacity: isTail && caret ? 0.72 : undefined,
              transition: "opacity 320ms ease",
            }}
          >
            {w}
          </span>
        );
      })}
      {caret && (
        <span
          className={cn("anim-caret -mb-[0.1em] inline-block h-[1em] w-[0.5ch] align-baseline", caretClassName)}
          style={{ background: caretColor, opacity: 0.55, borderRadius: 2 }}
          aria-hidden
        />
      )}
    </span>
  );
}
