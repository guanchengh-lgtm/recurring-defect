import { Ctx } from "../context";

export async function handleReport(ctx: Ctx) {
  const owner = ctx.session.userId;
  return { status: 200, body: `report for ${owner}` };
}
