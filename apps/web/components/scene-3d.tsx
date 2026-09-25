"use client";

import React, { useRef, useState, useEffect, useMemo, useCallback, Suspense, ReactNode } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';

/**
 * Global pointer coordinates for parallax effects.
 */
let pointerX = 0;
let pointerY = 0;

if (typeof window !== 'undefined') {
  window.addEventListener('pointermove', (e: PointerEvent) => {
    pointerX = (e.clientX / window.innerWidth) * 2 - 1;
    pointerY = -(e.clientY / window.innerHeight) * 2 + 1;
  });
}

/**
 * Basic Error Boundary for 3D components to prevent full app crashes.
 */
export class ErrorBoundary extends React.Component<{ children: ReactNode, fallback?: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode, fallback?: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || null;
    }
    return this.props.children;
  }
}

export interface WorkspaceScene3DProps {
  isDark?: boolean;
  children?: ReactNode;
}

/**
 * Main 3D background scene containing the rotating icosahedron and lighting.
 * Detects mobile context to optimize rendering.
 */
export function WorkspaceScene3D({ isDark = true, children }: WorkspaceScene3DProps) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const checkMobile = () => {
        const userAgentMatch = /iPhone|iPad|Android/i.test(navigator.userAgent);
        const widthMatch = window.innerWidth < 768;
        setIsMobile(userAgentMatch || widthMatch);
      };
      checkMobile();
      window.addEventListener('resize', checkMobile);
      return () => window.removeEventListener('resize', checkMobile);
    }
  }, []);

  const bgColor = isDark ? '#0f172a' : '#f0f0f0';
  const dpr = isMobile ? 1 : (typeof window !== 'undefined' ? Math.min(window.devicePixelRatio, 2) : 1);

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none' }}>
      <ErrorBoundary fallback={<div />}>
        <Canvas
          gl={{
            antialias: !isMobile,
            alpha: true,
            powerPreference: 'high-performance'
          }}
          camera={{ position: [0, 0, 5], fov: 50 }}
          dpr={dpr}
          style={{ width: '100%', height: '100%', background: 'transparent' }}
        >
          <color attach="background" args={[bgColor]} />
          <fog attach="fog" args={[bgColor, 0, 100]} />
          <ambientLight intensity={0.4} />
          <pointLight position={[5, 5, 5]} color="#60a5fa" intensity={1.2} />
          <pointLight position={[-4, -3, 3]} color="#818cf8" intensity={0.6} />
          
          <Suspense fallback={null}>
            <RotatingIcosahedron isMobile={isMobile} />
            {children}
          </Suspense>
        </Canvas>
      </ErrorBoundary>
    </div>
  );
}

export interface RotatingIcosahedronProps {
  isMobile?: boolean;
}

/**
 * Central geometric shape with breathing pulse, mouse parallax, and gradient colors.
 */
export function RotatingIcosahedron({ isMobile = false }: RotatingIcosahedronProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const detail = isMobile ? 3 : 4;

  const geometry = useMemo(() => {
    const geo = new THREE.IcosahedronGeometry(1.4, detail);
    const count = geo.attributes.position.count;
    const colors = new Float32Array(count * 3);
    const colorTop = new THREE.Color('#3b82f6');
    const colorBottom = new THREE.Color('#1e40af');

    for (let i = 0; i < count; i++) {
      const y = geo.attributes.position.getY(i);
      // Normalize y to roughly 0-1 for a radius of 1.4
      const alpha = (y + 1.4) / 2.8; 
      const mixed = colorBottom.clone().lerp(colorTop, alpha);
      colors[i * 3] = mixed.r;
      colors[i * 3 + 1] = mixed.g;
      colors[i * 3 + 2] = mixed.b;
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    return geo;
  }, [detail]);

  useFrame((state, delta) => {
    if (!meshRef.current) return;
    
    // Smooth rotation
    meshRef.current.rotation.x += 0.0005;
    meshRef.current.rotation.y += 0.0008;

    // Mouse parallax
    const targetX = pointerX * 0.6;
    const targetY = pointerY * 0.4;
    meshRef.current.position.x += (targetX - meshRef.current.position.x) * 0.03;
    meshRef.current.position.y += (targetY - meshRef.current.position.y) * 0.03;

    // Breathing pulse
    const scale = 1 + Math.sin(Date.now() * 0.001) * 0.06;
    meshRef.current.scale.set(scale, scale, scale);
  });

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshPhongMaterial
        vertexColors
        emissive="#1e40af"
        emissiveIntensity={0.4}
        transparent
        opacity={0.92}
        shininess={50}
      />
    </mesh>
  );
}

export interface ParticleSystemProps {
  count?: number;
}

/**
 * A descending field of particles simulating gentle rain or energy flow.
 */
export function ParticleSystem({ count = 3000 }: ParticleSystemProps) {
  const pointsRef = useRef<THREE.Points>(null);

  const particlesPosition = useMemo(() => {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = Math.random() * 10 - 5;
      positions[i * 3 + 1] = Math.random() * 10 - 5;
      positions[i * 3 + 2] = Math.random() * 10 - 5;
    }
    return positions;
  }, [count]);

  useFrame(() => {
    if (!pointsRef.current) return;
    const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;

    for (let i = 0; i < count; i++) {
      const idx = i * 3 + 1;
      positions[idx] -= 0.01;
      if (positions[idx] < -5) {
        positions[idx] = 5;
        positions[i * 3] = Math.random() * 10 - 5;
        positions[i * 3 + 2] = Math.random() * 10 - 5;
      }
    }
    pointsRef.current.geometry.attributes.position.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[particlesPosition, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#60a5fa"
        size={0.05}
        transparent
        opacity={0.6}
        sizeAttenuation={true}
      />
    </points>
  );
}

/**
 * Floating secondary shapes orbiting the central area.
 */
export function FloatingObjectsField() {
  const groupRef = useRef<THREE.Group>(null);

  const objects = useMemo(() => {
    const colors = ['#3b82f6', '#06b6d4', '#8b5cf6', '#ec4899', '#f59e0b'];
    const positions = [
      [-3, 2, -2],
      [3, -1, -3],
      [-2, -2, -1],
      [4, 1, -2],
      [0, 3, -4],
    ];
    
    return positions.map((pos, index) => ({
      position: new THREE.Vector3(...pos),
      color: colors[index % colors.length],
      offset: index * 1.5
    }));
  }, []);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const time = clock.getElapsedTime();
    
    groupRef.current.children.forEach((child, index) => {
      const obj = objects[index];
      if (child) {
        child.position.y += Math.sin(time + obj.offset) * 0.003;
        child.rotation.x += 0.003;
        child.rotation.y += 0.005;
      }
    });
  });

  return (
    <group ref={groupRef}>
      {objects.map((obj, i) => (
        <mesh key={i} position={obj.position}>
          <octahedronGeometry args={[0.15, 0]} />
          <meshPhongMaterial
            color={obj.color}
            emissive={obj.color}
            emissiveIntensity={0.6}
            shininess={100}
          />
        </mesh>
      ))}
    </group>
  );
}

export interface AnimatedSpecialistCardProps {
  icon: string;
  label: string;
  status: string;
  children?: ReactNode;
}

/**
 * A CSS-only animated card with 3D hover and glow effects.
 */
export function AnimatedSpecialistCard({ icon, label, status, children }: AnimatedSpecialistCardProps) {
  const [isHovered, setIsHovered] = useState(false);

  const wrapperStyle: React.CSSProperties = {
    perspective: '1000px',
    margin: '1rem',
    display: 'inline-block'
  };

  const cardStyle: React.CSSProperties = {
    transformStyle: 'preserve-3d',
    transition: 'transform 0.3s ease-out, box-shadow 0.3s ease-out',
    transform: isHovered ? 'rotateY(5deg) rotateX(-5deg)' : 'rotateY(0deg) rotateX(0deg)',
    boxShadow: isHovered 
      ? '0 20px 40px -10px rgba(59, 130, 246, 0.4), 0 0 20px rgba(59, 130, 246, 0.2)' 
      : '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    background: 'linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%)',
    backdropFilter: 'blur(10px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '1rem',
    padding: '1.5rem',
    position: 'relative',
    overflow: 'hidden'
  };

  const glowStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.15), transparent 70%)',
    opacity: isHovered ? 1 : 0,
    transition: 'opacity 0.3s ease-out',
    pointerEvents: 'none',
    zIndex: 0
  };

  return (
    <div 
      style={wrapperStyle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div style={cardStyle}>
        <div style={glowStyle} />
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ fontSize: '2rem' }}>{icon}</div>
          <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: '#e2e8f0' }}>{label}</h3>
          <span style={{ fontSize: '0.875rem', color: '#94a3b8' }}>{status}</span>
          {children}
        </div>
      </div>
    </div>
  );
}

export interface ThemeSelectorCanvasProps {
  isDark?: boolean;
}

function ThemeSphere({ isDark }: { isDark: boolean }) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.01;
    }
  });

  const color = isDark ? '#1e1e2e' : '#f0f0f0';
  const emissive = isDark ? '#3b82f6' : '#93c5fd';

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.8, 32, 32]} />
      <meshPhongMaterial color={color} emissive={emissive} emissiveIntensity={0.5} shininess={50} />
    </mesh>
  );
}

/**
 * Small 32x32 inline Canvas representing a theme toggle visually.
 */
export function ThemeSelectorCanvas({ isDark = true }: ThemeSelectorCanvasProps) {
  return (
    <div style={{ width: 32, height: 32, display: 'inline-block' }}>
      <ErrorBoundary fallback={<div style={{ width: '100%', height: '100%', background: 'transparent' }} />}>
        <Canvas camera={{ position: [0, 0, 2], fov: 50 }}>
          <ambientLight intensity={0.5} />
          <pointLight position={[2, 2, 2]} intensity={1} />
          <ThemeSphere isDark={isDark} />
        </Canvas>
      </ErrorBoundary>
    </div>
  );
}

export interface AnimatedCardProps {
  delay?: number;
  children: ReactNode;
}

/**
 * A CSS-only card that fades and slides up smoothly when scrolled into view.
 */
export function AnimatedCard({ delay = 0, children }: AnimatedCardProps) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (ref.current) observer.unobserve(ref.current);
        }
      },
      { threshold: 0.1 }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, []);

  const style: React.CSSProperties = {
    opacity: isVisible ? 1 : 0,
    transform: isVisible ? 'translateY(0) rotateX(0deg)' : 'translateY(20px) rotateX(-10deg)',
    transition: 'all 600ms cubic-bezier(0.23, 1, 0.320, 1)',
    transitionDelay: `${delay}ms`,
    transformOrigin: 'top center'
  };

  return (
    <div style={{ perspective: '1000px' }}>
      <div ref={ref} style={style}>
        {children}
      </div>
    </div>
  );
}

export interface TiltCardProps {
  children: ReactNode;
}

/**
 * A CSS-only card that tilts relative to the mouse position hovering over it.
 */
export function TiltCard({ children }: TiltCardProps) {
  const [rotation, setRotation] = useState({ x: 0, y: 0 });
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    
    // Max rotation is 10deg
    const rotateX = ((y - centerY) / centerY) * -10;
    const rotateY = ((x - centerX) / centerX) * 10;
    
    setRotation({ x: rotateX, y: rotateY });
  }, []);

  const handleMouseLeave = useCallback(() => {
    setRotation({ x: 0, y: 0 });
  }, []);

  return (
    <div style={{ perspective: '1000px', display: 'inline-block' }}>
      <div
        ref={cardRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{
          transform: `rotateX(${rotation.x}deg) rotateY(${rotation.y}deg)`,
          transition: 'transform 0.1s ease-out',
          transformStyle: 'preserve-3d',
          width: '100%',
          height: '100%'
        }}
      >
        {children}
      </div>
    </div>
  );
}

export interface OptimizedWorkspaceSceneProps {
  isDark?: boolean;
}

/**
 * Combines the main 3D scene with appropriate decorative particle/floating fields based on device.
 */
export function OptimizedWorkspaceScene({ isDark = true }: OptimizedWorkspaceSceneProps) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const checkMobile = () => {
        const userAgentMatch = /iPhone|iPad|Android/i.test(navigator.userAgent);
        const widthMatch = window.innerWidth < 768;
        setIsMobile(userAgentMatch || widthMatch);
      };
      checkMobile();
      window.addEventListener('resize', checkMobile);
      return () => window.removeEventListener('resize', checkMobile);
    }
  }, []);

  const particleCount = isMobile ? 2000 : 3000;

  return (
    <WorkspaceScene3D isDark={isDark}>
      <ParticleSystem count={particleCount} />
      {!isMobile && <FloatingObjectsField />}
    </WorkspaceScene3D>
  );
}

export interface WorkspaceLayoutProps {
  isDark?: boolean;
  children: ReactNode;
}

/**
 * Layout wrapper that manages positioning the 3D canvas behind main content.
 */
export function WorkspaceLayout({ isDark = true, children }: WorkspaceLayoutProps) {
  const bgColor = isDark ? '#0f172a' : '#f0f0f0';
  
  return (
    <div style={{ position: 'relative', width: '100%', minHeight: '100vh', backgroundColor: bgColor, overflow: 'hidden' }}>
      <OptimizedWorkspaceScene isDark={isDark} />
      <div style={{ position: 'relative', zIndex: 10 }}>
        {children}
      </div>
    </div>
  );
}

export default WorkspaceScene3D;

/*
Usage Example:

import WorkspaceScene3D, { 
  WorkspaceLayout, 
  AnimatedSpecialistCard, 
  ThemeSelectorCanvas 
} from '@/components/scene-3d';

export default function MyPage() {
  return (
    <WorkspaceLayout isDark={true}>
      <header>
        <h1>Welcome</h1>
        <ThemeSelectorCanvas isDark={true} />
      </header>
      <main>
        <AnimatedSpecialistCard icon="🚀" label="Deploy" status="Active">
          <p>This card has 3D tilt effects</p>
        </AnimatedSpecialistCard>
      </main>
    </WorkspaceLayout>
  );
}
*/
