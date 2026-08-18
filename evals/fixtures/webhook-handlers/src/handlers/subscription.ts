import { Ctx } from "../context";

export async function handleSubscription(ctx: Ctx) {
  // Crashed in prod this morning: ctx.session is null on the public webhook path.
  const tenant = ctx.session.tenantId;
  return { status: 200, body: `subscription for ${tenant}` };
}
