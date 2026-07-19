import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

const ORBIT_TEXT = "DISCOVER KNOWLEDGE ACTIVATE ";

function TextRing({
  radius = 12,
  fontSize = 1.2,
  depth = 0.2,
}: {
  radius?: number;
  fontSize?: number;
  depth?: number;
}) {
  const groupRef = useRef<THREE.Group>(null);

  const chars = useMemo(() => ORBIT_TEXT.split(""), []);

  useFrame(({ clock }) => {
    if (groupRef.current) {
      groupRef.current.rotation.z = clock.getElapsedTime() * 0.2;
    }
  });

  return (
    <group ref={groupRef} rotation={[Math.PI * 0.35, 0, 0]}>
      {chars.map((char, i) => {
        if (char === " ") return null;
        const angle = (i / chars.length) * Math.PI * 2;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        const rotZ = angle - Math.PI / 2;

        return (
          <mesh
            key={i}
            position={[x, y, 0]}
            rotation={[0, 0, rotZ]}
          >
            {/* Use a simple box for each character as a stylized representation */}
            <boxGeometry args={[fontSize * 0.7, fontSize, depth]} />
            <meshBasicMaterial
              color={i % 2 === 0 ? "#5B21FF" : "#FFD600"}
              transparent
              opacity={0.9}
            />
          </mesh>
        );
      })}

      {/* Haze shell - torus for glow effect */}
      <mesh scale={[1.1, 1.1, 1.1]}>
        <torusGeometry args={[radius, radius * 0.25, 16, 100]} />
        <meshBasicMaterial
          color="#1a1a1a"
          transparent
          opacity={0.3}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

export default function IntelligenceOrbit({
  className = "",
  style = {},
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`${className}`}
      style={{ width: "100%", height: "500px", ...style }}
    >
      <Canvas
        camera={{ position: [0, 0, 30], fov: 50 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <TextRing radius={12} fontSize={1.2} depth={0.2} />
      </Canvas>
    </div>
  );
}
