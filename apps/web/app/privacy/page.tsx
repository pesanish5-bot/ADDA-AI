import type { Metadata } from "next";
import PolicyPage from "../../components/policy-page";
import { SITE } from "../../lib/site";

export const metadata: Metadata = { title: "Privacy | ADDA AI", description: "How ADDA AI collects, uses, and protects account and workspace data." };

export default function PrivacyPage() {
  return <PolicyPage eyebrow="PRIVACY" title="Privacy notice" summary="What ADDA AI collects, why it is needed, and the choices available to you.">
    <section><h2>Information we collect</h2><p>We collect the account details you provide, such as your name and email address; authentication and security events; tasks, files, and feedback you choose to submit; and technical usage records needed to operate, secure, and improve the service.</p></section>
    <section><h2>How information is used</h2><p>We use this information to authenticate your account, route requests to the appropriate AI specialist, return and store results, enforce usage limits, investigate abuse, provide support, and understand service reliability.</p></section>
    <section><h2>AI and service providers</h2><p>Only the information needed to complete a request is sent to the relevant provider. Current infrastructure may use Amazon Web Services, including Amazon Cognito, Bedrock, DynamoDB, S3, and CloudWatch. Search requests may be sent to Tavily when web search is available. A payment provider will process payment details if paid plans launch; ADDA AI will not store complete card numbers.</p></section>
    <section><h2>Files, tasks, and retention</h2><p>Workspace history is private to the signed-in account. Uploaded documents and extracted evidence are stored only as needed for the document workflow and security controls. Operational logs and authentication events are retained for limited troubleshooting, security, and audit periods. Retention controls will be documented before paid launch.</p></section>
    <section><h2>Your choices</h2><p>You can choose what to submit and can sign out at any time. Self-service export and account deletion controls are planned. Until those controls are available, contact us to request access, correction, export, or deletion; we may need to verify account ownership first.</p></section>
    <section><h2>Local storage and sessions</h2><p>The site uses browser storage for your signed-in session and appearance preferences. These are necessary for authentication and to remember settings; advertising trackers are not intentionally used.</p></section>
    <section><h2>Contact</h2><p>Privacy questions and requests can be sent to <a href={`mailto:${SITE.supportEmail}`}>{SITE.supportEmail}</a>. This address will be replaced with the official business-domain privacy address when it is active.</p></section>
  </PolicyPage>;
}

