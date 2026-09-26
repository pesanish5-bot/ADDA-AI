"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "../components/AuthProvider";

export default function Providers({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
