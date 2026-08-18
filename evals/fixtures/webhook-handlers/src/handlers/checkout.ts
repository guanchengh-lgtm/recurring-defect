import { Ctx } from "../context";

export async function handleCheckout(ctx: Ctx) {
  if (!ctx.session) {
    return { status: 401, body: "session required" };
  }
  const tenant = ctx.session.tenantId;
  return { status: 200, body: `checkout for ${tenant}` };
}
