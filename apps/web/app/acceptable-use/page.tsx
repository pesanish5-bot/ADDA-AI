import type { Metadata } from "next";
import PolicyPage from "../../components/policy-page";
import { SITE } from "../../lib/site";

export const metadata: Metadata = { title: "Acceptable Use | ADDA AI", description: "Rules for safe and responsible use of ADDA AI." };

export default function AcceptableUsePage() {
  return <PolicyPage eyebrow="SAFETY" title="Acceptable use" summary="Rules designed to protect users, other people, and the service.">
    <section><h2>Do not use ADDA AI to</h2><ul><li>break the law, facilitate fraud, impersonation, phishing, harassment, or exploitation;</li><li>create or distribute malware, steal credentials, evade security controls, or gain unauthorized access;</li><li>upload private, confidential, or copyrighted material without the right to process it;</li><li>generate sexual content involving minors or content that exploits or endangers children;</li><li>make fully automated high-impact decisions about another person in areas such as employment, lending, housing, education, insurance, healthcare, or legal access;</li><li>bypass quotas, probe infrastructure, scrape the service, resell access without permission, or interfere with other users.</li></ul></section>
    <section><h2>Code and research</h2><p>Treat generated code and research as untrusted until you review and test it safely. Do not use ADDA AI to execute unknown code or to present generated claims as verified facts without checking the cited sources.</p></section>
    <section><h2>Enforcement</h2><p>We may limit or suspend access while investigating suspected abuse or security risk. Where appropriate, we will consider context, severity, and whether the activity was intentional.</p></section>
    <section><h2>Report a concern</h2><p>Report misuse or a security concern to <a href={`mailto:${SITE.supportEmail}`}>{SITE.supportEmail}</a>. Do not include passwords, API keys, payment details, or unnecessary personal data.</p></section>
  </PolicyPage>;
}

