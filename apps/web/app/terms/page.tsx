import type { Metadata } from "next";
import Link from "next/link";
import PolicyPage from "../../components/policy-page";
import { SITE } from "../../lib/site";

export const metadata: Metadata = { title: "Terms | ADDA AI", description: "Pre-launch terms for using the ADDA AI workspace." };

export default function TermsPage() {
  return <PolicyPage eyebrow="TERMS" title="Terms of use" summary="The basic rules that apply when you create an account and use ADDA AI.">
    <section><h2>Using the service</h2><p>You must provide accurate account information, keep your credentials secure, and be legally able to accept these terms. You are responsible for activity performed through your account and must notify us if you believe it has been compromised.</p></section>
    <section><h2>Your content</h2><p>You keep ownership of content you submit. You give ADDA AI the limited permission needed to store, process, and transmit that content solely to operate the service. Only submit content you have the right to use.</p></section>
    <section><h2>AI-generated results</h2><p>AI output can be incomplete, outdated, or incorrect. Review results and sources before relying on them, especially for code or decisions involving health, law, finance, safety, employment, or other high-impact matters. ADDA AI does not execute generated code on your behalf.</p></section>
    <section><h2>Availability and changes</h2><p>This is a pre-launch service. Features, models, providers, quotas, and availability can change as the product is tested. We may suspend access when necessary to protect users, infrastructure, or the service.</p></section>
    <section><h2>Payments</h2><p>Paid plans are not currently active. Before accepting payment, ADDA AI will publish the final price, included usage, renewal and cancellation rules, taxes, supported payment provider, and refund terms. No plan will be upgraded solely from a browser response; payment status must be verified by the server.</p></section>
    <section><h2>Acceptable use</h2><p>You must follow the <Link href="/acceptable-use/">Acceptable Use Policy</Link>. Attempts to bypass limits, access another person&apos;s data, disrupt the service, or use it for unlawful activity may result in suspension.</p></section>
    <section><h2>Contact</h2><p>Questions about these terms can be sent to <a href={`mailto:${SITE.supportEmail}`}>{SITE.supportEmail}</a>. Final business identity and governing-law details will be added before commercial launch.</p></section>
  </PolicyPage>;
}

