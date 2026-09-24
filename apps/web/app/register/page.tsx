import type { Metadata } from "next";
import AuthView from "../../components/auth-view";

export const metadata: Metadata = { title: "Create account - ADDA AI", description: "Create an ADDA AI account." };

export default function RegisterPage() { return <AuthView mode="register" />; }
