import type { Metadata } from "next";
import AuthView from "../../components/auth-view";

export const metadata: Metadata = { title: "Sign in - ADDA AI", description: "Sign in to your ADDA AI workspace." };

export default function LoginPage() { return <AuthView mode="login" />; }
