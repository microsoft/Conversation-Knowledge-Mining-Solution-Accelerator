export interface AuthSession {
  identity: string;
  name: string;
  roles: string[];
}

export class AuthError extends Error {
  constructor(message = "Sign-in session expired. Sign in again. If this persists, check the EasyAuth backend API scope and token store configuration.") {
    super(message);
    this.name = "AuthError";
  }
}

type TokenSession = AuthSession & { token: string; expiresAt: number };
let current: TokenSession | null = null;
let pending: Promise<TokenSession> | null = null;
let refreshing: Promise<void> | null = null;
let generation = 0;
const listeners = new Set<(session: AuthSession | null, error?: Error) => void>();
const cacheKeys = [
  "km_home_data", "km_explore_data", "km_insights", "km_headline",
  "km_chat", "km_explore_chat", "km_explore_session",
];

export function clearUserCache() {
  try {
    cacheKeys.forEach((key) => sessionStorage.removeItem(key));
    localStorage.removeItem("userId");
  } catch {
    // Storage may be disabled; authentication never depends on it.
  }
}

export function subscribeSession(listener: (session: AuthSession | null, error?: Error) => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function publish(session: AuthSession | null, error?: Error) {
  listeners.forEach((listener) => listener(session, error));
}

export function invalidateSession(error = new AuthError()) {
  generation += 1;
  current = null;
  clearUserCache();
  publish(null, error);
}

export function reportAccessDenied(): Error {
  const error = new Error("Access denied. Your account needs the required Reader, Contributor, or Admin role for this action.");
  if (current) {
    const { identity, name, roles } = current;
    publish({ identity, name, roles }, error);
  }
  return error;
}

function parseSession(data: unknown): TokenSession {
  if (!Array.isArray(data)) throw new AuthError();
  const entries = data.filter((entry) => entry?.provider_name === "aad");
  if (entries.length !== 1) throw new AuthError();
  const entry = entries[0];
  if (typeof entry.access_token !== "string") throw new AuthError();
  const parts = entry.access_token.split(".");
  if (parts.length !== 3 || parts.some((part: string) => !/^[A-Za-z0-9_-]+$/.test(part))) throw new AuthError();
  let claims;
  try {
    claims = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    throw new AuthError();
  }
  // These are client-side sanity checks, not signature validation or authorization.
  // The API validates the signature, configured audience/tenant, scope and roles.
  if (
    claims.ver !== "2.0" || typeof claims.exp !== "number" || !Number.isFinite(claims.exp) ||
    typeof claims.oid !== "string" || !claims.oid ||
    typeof claims.tid !== "string" || !claims.tid ||
    typeof claims.aud !== "string" || !claims.aud ||
    typeof claims.scp !== "string" || !claims.scp.split(" ").includes("access_as_user")
  ) throw new AuthError();
  const roles = Array.isArray(claims.roles)
    ? claims.roles.filter((role: unknown) => typeof role === "string" && ["Reader", "Contributor", "Admin"].includes(role))
    : [];
  const userClaims = Array.isArray(entry.user_claims) ? entry.user_claims : [];
  const name = userClaims.find((claim: any) => claim?.typ === "name" && typeof claim.val === "string")?.val;
  return {
    token: entry.access_token,
    expiresAt: claims.exp * 1000,
    identity: `${claims.tid}:${claims.oid}`,
    name: name || "Signed-in user",
    roles,
  };
}

async function readSession(): Promise<TokenSession> {
  const response = await fetch("/.auth/me", { credentials: "same-origin", cache: "no-store", redirect: "error" });
  if (!response.ok) throw new AuthError();
  return parseSession(await response.json());
}

export async function refreshSession(): Promise<void> {
  if (!refreshing) {
    refreshing = (async () => {
      const response = await fetch("/.auth/refresh", { credentials: "same-origin", cache: "no-store", redirect: "error" });
      if (!response.ok) throw new AuthError();
    })().finally(() => { refreshing = null; });
  }
  return refreshing;
}

// Re-read EasyAuth for each request (coalescing concurrent reads) so account
// changes cannot reuse an old in-memory identity or persisted application data.
export async function getTokenSession(allowRefresh = true): Promise<TokenSession> {
  if (pending) return pending;
  const started = generation;
  pending = (async () => {
    try {
      let next = await readSession();
      if (next.expiresAt <= Date.now() + 60000 && allowRefresh) {
        await refreshSession();
        next = await readSession();
      }
      if (next.expiresAt <= Date.now()) throw new AuthError();
      if (started !== generation) throw new AuthError("Account changed. Retry after signing in.");
      if (current?.identity !== next.identity || current.roles.join() !== next.roles.join()) {
        generation += 1;
        clearUserCache();
        current = next;
        publish({ identity: next.identity, name: next.name, roles: next.roles });
      } else {
        current = next;
      }
      return next;
    } catch (error) {
      const authError = error instanceof AuthError ? error : new AuthError();
      invalidateSession(authError);
      throw authError;
    } finally {
      pending = null;
    }
  })();
  return pending;
}

export function isCurrentSession(identity: string): boolean {
  return current?.identity === identity;
}

export function sessionGeneration(): number {
  return generation;
}
