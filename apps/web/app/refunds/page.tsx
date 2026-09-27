import type { Metadata } from "next";
import PolicyPage from "../../components/policy-page";
import { SITE } from "../../lib/site";

export const metadata: Metadata = { title: "Refunds | ADDA AI", description: "Current payment and refund status for ADDA AI." };

export default function RefundsPage() {
  return <PolicyPage eyebrow="BILLING" title="Cancellation and refunds" summary="A clear statement of the current pre-launch billing position.">
    <section><h2>No live purchases today</h2><p>ADDA AI does not currently accept payments or activate paid plans. This means there is presently no subscription to cancel and no ADDA AI charge to refund.</p></section>
    <section><h2>Before paid launch</h2><p>Before charging users, we will publish the final subscription or credit terms, what each purchase includes, when credits expire if applicable, how recurring billing works, and the exact cancellation and refund rules. Those terms will also be visible before checkout.</p></section>
    <section><h2>Payment problems</h2><p>If you see a charge claiming to be from ADDA AI during this pre-launch period, do not share card or banking credentials with anyone. Contact your payment provider and notify us at <a href={`mailto:${SITE.supportEmail}`}>{SITE.supportEmail}</a> so it can be investigated.</p></section>
    <section><h2>Statutory rights</h2><p>Any future commercial policy will respect refund and consumer rights that cannot legally be excluded in the buyer&apos;s location.</p></section>
  </PolicyPage>;
}

