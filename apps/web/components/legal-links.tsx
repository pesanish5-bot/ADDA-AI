import Link from "next/link";

export default function LegalLinks({ className = "legal-links" }: { className?: string }) {
  return (
    <nav className={className} aria-label="Legal and policy links">
      <Link href="/privacy/">Privacy</Link>
      <Link href="/terms/">Terms</Link>
      <Link href="/refunds/">Refunds</Link>
      <Link href="/acceptable-use/">Acceptable use</Link>
    </nav>
  );
}

