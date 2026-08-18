import { Ctx } from "../context";

export async function handleRefund(ctx: Ctx) {
  if (ctx.session === null) {
    return { status: 401, body: "session required" };
  }
  return { status: 200, body: `refund for ${ctx.session.userId}` };
}
