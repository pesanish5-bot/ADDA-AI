"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

/** Redirects unauthenticated users away from the workspace. */
export default function AuthGate({ children }: { children: ReactNode }) {
  const { ready, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !user) router.replace("/login/");
  }, [ready, user, router]);

  if (!ready) {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Checking your session…
      </div>
    );
  }
  if (!user) {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Redirecting to sign in…
      </div>
    );
  }
  return <>{children}</>;
}
