/**
 * x402 paid actions — Freak Town's funny endpoints, driven by the
 * three.ws payment modal (@three-ws/x402-modal).
 *
 * Flow: modal discovers the 402 challenge on the settle endpoint,
 * user signs USDC (Base) in-wallet, modal retries with X-PAYMENT,
 * server verifies via facilitator, executes, settles, receipt header.
 *
 * Until POT_ESCROW_ADDRESS + FACILITATOR_URL are configured, the server
 * answers 501 (settlement_not_configured) and the modal surfaces that
 * honestly — no fake charges, ever.
 */

import { pay } from '@three-ws/x402-modal';

export type PaidAction = 'pot' | 'message' | 'hype' | 'tip';

export interface PayResult {
  ok: boolean;
  error?: string;
}

export async function payForAction(opts: {
  action: PaidAction;
  showId: string;
  target?: string;
  message?: string;
  merchant?: string;
}): Promise<PayResult> {
  const labels: Record<PaidAction, string> = {
    pot: 'Contribute to the pot',
    message: 'Flash message on screen',
    hype: 'Trigger hype SFX',
    tip: 'Tip this Freak',
  };
  try {
    await pay({
      endpoint: `/v1/pay/${opts.action}/settle`,
      method: 'POST',
      body: {
        show_id: opts.showId,
        target: opts.target ?? '',
        message: opts.message ?? '',
      },
      merchant: opts.merchant ?? 'Freak Town',
      action: labels[opts.action],
    });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}
