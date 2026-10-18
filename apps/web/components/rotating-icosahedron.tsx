"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * RotatingIcosahedron — animated 3D icosahedron for the ADDA AI workspace.
 *
 * Features:
 *  - Smooth continuous rotation on all axes
 *  - Gradient colour from #3b82f6 → #1e40af with emissive glow
 *  - Mouse-driven parallax offset (gentle follow)
 *  - Subtle breathing / pulse animation
 *  - Low polygon count (detail = 4, well under the 5-subdivision cap)
 */

/** Normalised mouse coords shared across the module (avoids per-frame listeners). */
const pointer = { x: 0, y: 0 };
if (typeof window !== "undefined") {
  window.addEventListener("pointermove", (e) => {
    pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
    pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
  });
}

export default function RotatingIcosahedron() {
  const meshRef = useRef<THREE.Mesh>(null);

  /* ---- gradient vertex colours ---- */
  const geometry = useMemo(() => {
    const geo = new THREE.IcosahedronGeometry(1.4, 4);
    const count = geo.attributes.position.count;
    const colours = new Float32Array(count * 3);

    const topColour = new THREE.Color("#3b82f6");
    const bottomColour = new THREE.Color("#1e40af");
    const temp = new THREE.Color();
    const pos = geo.attributes.position;

    for (let i = 0; i < count; i++) {
      // Map y position to [0, 1] for gradient lerp
      const y = pos.getY(i);
      const t = THREE.MathUtils.clamp((y + 1.4) / 2.8, 0, 1);
      temp.copy(bottomColour).lerp(topColour, t);
      colours[i * 3] = temp.r;
      colours[i * 3 + 1] = temp.g;
      colours[i * 3 + 2] = temp.b;
    }

    geo.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    return geo;
  }, []);

  /* ---- per-frame animation ---- */
  useFrame((_, delta) => {
    const mesh = meshRef.current;
    if (!mesh) return;

    // Smooth rotation
    mesh.rotation.x += delta * 0.15;
    mesh.rotation.y += delta * 0.22;
    mesh.rotation.z += delta * 0.08;

    // Breathing / pulse (scale oscillates ±6 %)
    const pulse = 1 + Math.sin(Date.now() * 0.001) * 0.06;
    mesh.scale.setScalar(pulse);

    // Gentle parallax follow (lerp toward pointer)
    mesh.position.x += (pointer.x * 0.6 - mesh.position.x) * 0.03;
    mesh.position.y += (pointer.y * 0.4 - mesh.position.y) * 0.03;
  });

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        vertexColors
        emissive="#1e3a8a"
        emissiveIntensity={0.35}
        roughness={0.35}
        metalness={0.55}
        transparent
        opacity={0.92}
      />
    </mesh>
  );
}
