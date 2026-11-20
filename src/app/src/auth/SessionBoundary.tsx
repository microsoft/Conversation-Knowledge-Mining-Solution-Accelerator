import React, { createContext, useContext, useEffect, useState } from "react";
import { Button, Spinner } from "@fluentui/react-components";
import { AuthSession, getTokenSession, invalidateSession, subscribeSession } from "./session";

const SessionContext = createContext<AuthSession | null>(null);
export const useSession = () => useContext(SessionContext);

export default function SessionBoundary({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const unsubscribe = subscribeSession((next, authError) => {
      setSession(next);
      setError(authError || null);
    });
    let active = true;
    const check = () => {
      void getTokenSession().then(({ identity, name, roles }) => {
        if (active) {
          setSession({ identity, name, roles });
          setError(null);
        }
      }).catch(() => {});
    };
    check();
    window.addEventListener("focus", check);
    const timer = window.setInterval(check, 60000);
    return () => {
      active = false;
      unsubscribe();
      window.removeEventListener("focus", check);
      window.clearInterval(timer);
    };
  }, []);

  if (!session) {
    return (
      <div role={error ? "alert" : "status"} style={{ padding: 32 }}>
        {error ? (
          <>
            <p>{error.message}</p>
            <p>Local development also requires a configured EasyAuth session; browser API keys and anonymous access are not supported.</p>
            <Button onClick={() => { window.location.href = "/.auth/login/aad"; }}>Sign in</Button>
          </>
        ) : <Spinner label="Checking sign-in session..." />}
      </div>
    );
  }
  if (!session.roles.length) {
    return (
      <div role="alert" style={{ padding: 32 }}>
        <p>Access denied. Ask your administrator to assign Reader, Contributor, or Admin to your account.</p>
        <Button onClick={() => {
          invalidateSession();
          window.location.href = "/.auth/logout";
        }}>Sign out</Button>
      </div>
    );
  }
  return (
    <SessionContext.Provider key={`${session.identity}:${session.roles.join()}`} value={session}>
      {error && <div role="alert" style={{ padding: 16 }}>{error.message}</div>}
      {children}
    </SessionContext.Provider>
  );
}
