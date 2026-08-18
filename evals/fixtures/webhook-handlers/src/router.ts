import { Ctx } from "./context";

// Requests on /webhooks/* are unauthenticated: session is null.
// Everything under /api/* has a session.
export function buildCtx(path: string, body: unknown, requestId: string): Ctx {
  const isPublicWebhook = path.startsWith("/webhooks/");
  return { requestId, body, session: isPublicWebhook ? null : loadSession() };
}

function loadSession() {
  return { userId: "u_1", tenantId: "t_1" };
}
