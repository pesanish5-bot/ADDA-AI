"use client";

import { Component, type ReactNode, Suspense, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import RotatingIcosahedron from "./rotating-icosahedron";

/* ------------------------------------------------------------------ */
/*  Error boundary — catches WebGL / Three.js errors gracefully       */
/* ------------------------------------------------------------------ */

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class Scene3DErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? null;
    }
    return this.props.children;
  }
}

/* ------------------------------------------------------------------ */
/*  Fallback shown while the canvas is loading                        */
/* ------------------------------------------------------------------ */

function LoadingFallback() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "#0f172a",
        display: "grid",
        placeItems: "center",
        color: "#334155",
        fontSize: 12,
        fontFamily: "var(--mono, monospace)",
      }}
    >
      Loading 3D scene…
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Scene3D — the ready-to-use canvas wrapper                         */
/* ------------------------------------------------------------------ */

/**
 * Drop-in 3D background component for the ADDA AI workspace.
 *
 * Features:
 *  - Dark background (#0f172a) matching the design system
 *  - Ambient + point lights for soft illumination
 *  - Camera at [0, 0, 5] with 50° FOV
 *  - Responsive resize via CSS + R3F's built-in resize observer
 *  - Error boundary so 3D failures never break the rest of the UI
 *  - Mobile performance: disables antialiasing on narrow viewports
 *  - pointer-events: none so it never blocks DOM interaction
 */
export default function Scene3D() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  return (
    <Scene3DErrorBoundary
      fallback={
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "#0f172a",
          }}
        />
      }
    >
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          overflow: "hidden",
        }}
      >
        <Suspense fallback={<LoadingFallback />}>
          <Canvas
            gl={{
              antialias: !isMobile,
              alpha: false,
              powerPreference: "high-performance",
            }}
            camera={{ position: [0, 0, 5], fov: 50, near: 0.1, far: 100 }}
            dpr={[1, isMobile ? 1.5 : 2]}
            style={{ background: "#0f172a" }}
            onCreated={({ gl }) => {
              gl.setClearColor("#0f172a");
            }}
          >
            {/* Lighting */}
            <ambientLight intensity={0.4} />
            <pointLight position={[5, 5, 5]} intensity={1.2} color="#60a5fa" />
            <pointLight position={[-4, -3, 3]} intensity={0.6} color="#818cf8" />

            {/* Main object */}
            <RotatingIcosahedron />
          </Canvas>
        </Suspense>
      </div>
    </Scene3DErrorBoundary>
  );
}
