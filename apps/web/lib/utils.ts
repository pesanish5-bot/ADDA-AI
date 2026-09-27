/** Minimal className helper (rare-ui / shadcn `cn` without Tailwind). */
export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}
