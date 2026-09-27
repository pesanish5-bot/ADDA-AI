import Link from "next/link";
import BrandMark from "./brand-mark";
import LegalLinks from "./legal-links";
import ThemePicker from "./theme-picker";
import { SITE } from "../lib/site";

export default function PolicyPage({
  eyebrow,
  title,
  summary,
  children,
}: {
  eyebrow: string;
  title: string;
  summary: string;
  children: React.ReactNode;
}) {
  return (
    <div className="policy-shell">
      <header className="policy-header">
        <Link className="policy-brand" href="/"><BrandMark /><span>ADDA <b>AI</b></span></Link>
        <nav aria-label="Policy navigation"><Link href="/login/">Sign in</Link><ThemePicker /></nav>
      </header>
      <main className="policy-main">
        <div className="policy-title">
          <p>{eyebrow}</p>
          <h1>{title}</h1>
          <span>{summary}</span>
          <small>Effective {SITE.policyEffectiveDate} · Pre-launch policy</small>
        </div>
        <div className="policy-notice"><strong>Payments are not live.</strong> ADDA AI does not currently charge users. Commercial terms will be reviewed and updated before paid access is enabled.</div>
        <article className="policy-content">{children}</article>
      </main>
      <footer className="policy-footer"><span>© 2026 {SITE.name}</span><LegalLinks /><a href={`mailto:${SITE.supportEmail}`}>Contact</a></footer>
    </div>
  );
}

