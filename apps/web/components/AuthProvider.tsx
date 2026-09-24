"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Hub } from "aws-amplify/utils";
import {
  cognitoConfigured,
  cognitoConfirmForgotPassword,
  cognitoConfirmSignUp,
  cognitoForgotPassword,
  cognitoResendSignUp,
  cognitoSignIn,
  cognitoSignInWithGoogle,
  cognitoSignOut,
  cognitoSignUp,
  currentUser,
  ensureCognito,
  googleConfigured,
  mapAuthError,
  type AuthUser,
  type SignUpDelivery,
} from "../lib/cognito";

type AuthContextValue = {
  ready: boolean;
  configured: boolean;
  googleEnabled: boolean;
  user: AuthUser | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<SignUpDelivery>;
  confirmSignUp: (email: string, code: string) => Promise<void>;
  resendSignUp: (email: string) => Promise<{ destination?: string; deliveryMedium?: string }>;
  forgotPassword: (email: string) => Promise<{ destination?: string; deliveryMedium?: string }>;
  confirmForgotPassword: (email: string, code: string, newPassword: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = cognitoConfigured();
  const googleEnabled = googleConfigured();
  const [ready, setReady] = useState(!configured);
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    setUser(await currentUser());
  }, []);

  useEffect(() => {
    if (!ensureCognito()) {
      setReady(true);
      return;
    }
    let active = true;
    void refresh().finally(() => {
      if (active) setReady(true);
    });
    const unsub = Hub.listen("auth", ({ payload }) => {
      if (payload.event === "signedIn" || payload.event === "signInWithRedirect") void refresh();
      if (payload.event === "signedOut") setUser(null);
    });
    return () => {
      active = false;
      unsub();
    };
  }, [refresh]);

  const value = useMemo<AuthContextValue>(() => ({
    ready,
    configured,
    googleEnabled,
    user,
    refresh,
    async signIn(email, password) {
      try {
        await cognitoSignIn(email, password);
        await refresh();
      } catch (failure) {
        throw new Error(mapAuthError(failure instanceof Error ? failure.message : String(failure)));
      }
    },
    async signUp(name, email, password) {
      try {
        return await cognitoSignUp(name, email, password);
      } catch (failure) {
        throw new Error(mapAuthError(failure instanceof Error ? failure.message : String(failure)));
      }
    },
    async confirmSignUp(email, code) {
      try {
        await cognitoConfirmSignUp(email, code);
      } catch (failure) {
        throw new Error(mapAuthError(failure instanceof Error ? failure.message : String(failure)));
      }
    },
    async resendSignUp(email) {
      try {
        return await cognitoResendSignUp(email);
      } catch (failure) {
        throw new Error(mapAuthError(failure instanceof Error ? failure.message : String(failure)));
      }
    },
    async forgotPassword(email) {
      try {
        return await cognitoForgotPassword(email);
      } catch (failure) {
        throw new Error(mapAuthError(failure instanceof Error ? failure.message : String(failure)));
      }
    },
    async confirmForgotPassword(email, code, newPassword) {
      try {
        await cognitoConfirmForgotPassword(email, code, newPassword);
      } catch (failure) {
        throw new Error(mapAuthError(failure instanceof Error ? failure.message : String(failure)));
      }
    },
    async signInWithGoogle() {
      try {
        await cognitoSignInWithGoogle();
      } catch (failure) {
        throw new Error(mapAuthError(failure instanceof Error ? failure.message : String(failure)));
      }
    },
    async signOut() {
      await cognitoSignOut();
      setUser(null);
    },
  }), [configured, googleEnabled, ready, refresh, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
