"use client";

import { Amplify } from "aws-amplify";
import {
  confirmResetPassword,
  confirmSignUp,
  fetchAuthSession,
  getCurrentUser,
  resendSignUpCode,
  resetPassword,
  signIn,
  signInWithRedirect,
  signOut,
  signUp,
} from "aws-amplify/auth";

let configured = false;

/** Matches the Cognito pool password policy deployed for ADDA AI. */
export const PASSWORD_RULES = {
  minLength: 12,
  requireLowercase: true,
  requireUppercase: true,
  requireNumber: true,
  requireSymbol: false,
  label: "At least 12 characters, including upper/lowercase letters and a number.",
};

export function cognitoConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID?.trim()
    && process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID?.trim(),
  );
}

export function googleConfigured(): boolean {
  return (
    process.env.NEXT_PUBLIC_GOOGLE_SIGN_IN_ENABLED === "true"
    && Boolean(process.env.NEXT_PUBLIC_COGNITO_DOMAIN?.trim())
  );
}

function redirectOrigins(): string[] {
  const fromEnv = (process.env.NEXT_PUBLIC_OAUTH_REDIRECT_SIGN_IN || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (fromEnv.length) return fromEnv;
  if (typeof window !== "undefined") {
    return [`${window.location.origin}/`];
  }
  return [
    "http://127.0.0.1:3000/",
    "http://localhost:3000/",
    "https://main.dvhyzvzxczywv.amplifyapp.com/",
  ];
}

function logoutOrigins(): string[] {
  const fromEnv = (process.env.NEXT_PUBLIC_OAUTH_REDIRECT_SIGN_OUT || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (fromEnv.length) return fromEnv;
  if (typeof window !== "undefined") {
    return [`${window.location.origin}/login/`];
  }
  return [
    "http://127.0.0.1:3000/login/",
    "http://localhost:3000/login/",
    "https://main.dvhyzvzxczywv.amplifyapp.com/login/",
  ];
}

export function ensureCognito(): boolean {
  if (!cognitoConfigured()) return false;
  if (!configured) {
    const domain = googleConfigured()
      ? process.env.NEXT_PUBLIC_COGNITO_DOMAIN?.trim()
      : undefined;
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID!,
          userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID!,
          ...(domain
            ? {
                loginWith: {
                  oauth: {
                    domain,
                    scopes: ["openid", "email", "profile"],
                    redirectSignIn: redirectOrigins(),
                    redirectSignOut: logoutOrigins(),
                    responseType: "code" as const,
                    providers: ["Google" as const],
                  },
                },
              }
            : {}),
        },
      },
    });
    configured = true;
  }
  return true;
}

export type AuthUser = {
  id: string;
  email: string;
  name: string;
};

export type SignUpDelivery = {
  status: "verify" | "signed_in";
  destination?: string;
  deliveryMedium?: string;
};

export function passwordMeetsPolicy(password: string): string | null {
  if (password.length < PASSWORD_RULES.minLength) {
    return PASSWORD_RULES.label;
  }
  if (PASSWORD_RULES.requireLowercase && !/[a-z]/.test(password)) {
    return PASSWORD_RULES.label;
  }
  if (PASSWORD_RULES.requireUppercase && !/[A-Z]/.test(password)) {
    return PASSWORD_RULES.label;
  }
  if (PASSWORD_RULES.requireNumber && !/[0-9]/.test(password)) {
    return PASSWORD_RULES.label;
  }
  if (PASSWORD_RULES.requireSymbol && !/[^A-Za-z0-9]/.test(password)) {
    return PASSWORD_RULES.label;
  }
  return null;
}

export async function getIdToken(): Promise<string | null> {
  if (!ensureCognito()) return null;
  const session = await fetchAuthSession();
  return session.tokens?.idToken?.toString() ?? null;
}

export async function currentUser(): Promise<AuthUser | null> {
  if (!ensureCognito()) return null;
  try {
    const user = await getCurrentUser();
    const session = await fetchAuthSession();
    const payload = session.tokens?.idToken?.payload ?? {};
    return {
      id: user.userId,
      email: String(payload.email || user.username || ""),
      name: String(payload.name || ""),
    };
  } catch {
    return null;
  }
}

export async function cognitoSignIn(email: string, password: string) {
  if (!ensureCognito()) throw new Error("Cognito is not configured yet.");
  const result = await signIn({ username: email, password });
  if (result.nextStep?.signInStep === "CONFIRM_SIGN_UP") {
    const err = new Error("User is not confirmed.");
    (err as Error & { code?: string }).code = "UserNotConfirmedException";
    throw err;
  }
  if (!result.isSignedIn) {
    throw new Error("Additional sign-in steps are required. Contact support.");
  }
}

export async function cognitoSignUp(
  name: string,
  email: string,
  password: string,
): Promise<SignUpDelivery> {
  if (!ensureCognito()) throw new Error("Cognito is not configured yet.");
  const policyError = passwordMeetsPolicy(password);
  if (policyError) throw new Error(policyError);
  const result = await signUp({
    username: email,
    password,
    options: {
      userAttributes: { email, name },
      autoSignIn: false,
    },
  });
  if (result.isSignUpComplete) {
    await signIn({ username: email, password });
    return { status: "signed_in" };
  }
  const next = result.nextStep as {
    codeDeliveryDetails?: { destination?: string; deliveryMedium?: string };
  } | undefined;
  const delivery = next?.codeDeliveryDetails;
  return {
    status: "verify",
    destination: delivery?.destination,
    deliveryMedium: delivery?.deliveryMedium,
  };
}

export async function cognitoConfirmSignUp(email: string, code: string) {
  if (!ensureCognito()) throw new Error("Cognito is not configured yet.");
  await confirmSignUp({ username: email, confirmationCode: code });
}

export async function cognitoResendSignUp(email: string) {
  if (!ensureCognito()) throw new Error("Cognito is not configured yet.");
  const result = await resendSignUpCode({ username: email });
  return {
    destination: result.destination,
    deliveryMedium: result.deliveryMedium,
  };
}

export async function cognitoForgotPassword(email: string) {
  if (!ensureCognito()) throw new Error("Cognito is not configured yet.");
  const result = await resetPassword({ username: email });
  const delivery = result.nextStep?.codeDeliveryDetails;
  return {
    destination: delivery?.destination,
    deliveryMedium: delivery?.deliveryMedium,
  };
}

export async function cognitoConfirmForgotPassword(
  email: string,
  code: string,
  newPassword: string,
) {
  if (!ensureCognito()) throw new Error("Cognito is not configured yet.");
  const policyError = passwordMeetsPolicy(newPassword);
  if (policyError) throw new Error(policyError);
  await confirmResetPassword({
    username: email,
    confirmationCode: code,
    newPassword,
  });
}

export async function cognitoSignInWithGoogle() {
  if (!ensureCognito()) throw new Error("Cognito is not configured yet.");
  if (!googleConfigured()) {
    throw new Error("Google sign-in is not configured yet.");
  }
  await signInWithRedirect({ provider: "Google" });
}

export async function cognitoSignOut() {
  if (!ensureCognito()) return;
  await signOut();
}

export function mapAuthError(message: string): string {
  const lower = message.toLowerCase();
  if (lower.includes("incorrect username") || lower.includes("not authorized") || lower.includes("user does not exist")) {
    return "Email or password is incorrect.";
  }
  if (lower.includes("usernameexists") || lower.includes("already exists")) {
    return "An account with this email already exists. Sign in instead.";
  }
  if (lower.includes("not confirmed") || lower.includes("user is not confirmed")) {
    return "Confirm your email with the verification code, then sign in.";
  }
  if (lower.includes("code mismatch") || lower.includes("invalid verification") || lower.includes("confirmation code") || lower.includes("invalid code")) {
    return "That code is invalid or expired.";
  }
  if (lower.includes("expired")) {
    return "That code has expired. Request a new one.";
  }
  if (lower.includes("attempt limit") || lower.includes("limit exceeded") || lower.includes("too many")) {
    return "Too many attempts. Wait a moment and try again.";
  }
  if (lower.includes("password")) {
    return PASSWORD_RULES.label;
  }
  if (lower.includes("network") || lower.includes("failed to fetch")) {
    return "Network unavailable. Check your connection and try again.";
  }
  if (lower.includes("google") && lower.includes("cancel")) {
    return "Google sign-in was cancelled.";
  }
  if (lower.includes("oauth") || lower.includes("redirect")) {
    return "Google sign-in failed. Try again or use email.";
  }
  return "Something went wrong. Please try again.";
}
