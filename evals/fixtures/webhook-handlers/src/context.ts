export interface Session { userId: string; tenantId: string; }

export interface Ctx {
  requestId: string;
  /** Null for requests arriving on the public webhook path. See src/router.ts. */
  session: Session | null;
  body: unknown;
}
