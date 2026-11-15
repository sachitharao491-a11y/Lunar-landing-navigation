import { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars, useGLTF } from "@react-three/drei";
import { Box3, Group, Vector3 } from "three";
import moonModelUrl from "../../assets/moon-optimized.glb?url";
import type { Site } from "../types/api";

function MoonModel({ autoRotate }: { autoRotate: boolean }) {
  const { scene } = useGLTF(moonModelUrl);
  const normalized = useMemo(() => {
    const object = scene.clone(true);
    object.updateMatrixWorld(true);
    const bounds = new Box3().setFromObject(object);
    const center = bounds.getCenter(new Vector3());
    const size = bounds.getSize(new Vector3());
    const scale = 2 / Math.max(size.x, size.y, size.z);
    object.scale.setScalar(scale);
    object.position.set(-center.x * scale, -center.y * scale, -center.z * scale);
    return object;
  }, [scene]);
  const group = useRef<Group>(null);
  useFrame((_state, delta) => {
    if (autoRotate && group.current) group.current.rotation.y += delta * 0.035;
  });
  return <group ref={group}><primitive object={normalized} /></group>;
}

function MoonPlaceholder() {
  return <mesh><sphereGeometry args={[0.98, 48, 32]} /><meshStandardMaterial color="#696b6c" roughness={1} metalness={0.02} /></mesh>;
}

function SiteMarker({ site, active, onSelect }: { site: Site; active: boolean; onSelect: (site: Site) => void }) {
  // This converts the backend coordinates to model-space only for marker placement.
  const lat = (site.lat * Math.PI) / 180;
  const lon = (site.lon * Math.PI) / 180;
  const point: [number, number, number] = [Math.cos(lat) * Math.cos(lon), Math.sin(lat), -Math.cos(lat) * Math.sin(lon)];
  return (
    <group position={point}>
      <mesh onClick={(event) => { event.stopPropagation(); onSelect(site); }}>
        <sphereGeometry args={[active ? 0.027 : 0.016, 12, 12]} />
        <meshBasicMaterial color={active ? "#F5F5F5" : "#A6A6A6"} />
      </mesh>
      {active && <mesh scale={1.9}><sphereGeometry args={[0.026, 12, 12]} /><meshBasicMaterial color="#C7C7C7" transparent opacity={0.2} /></mesh>}
    </group>
  );
}

function Scene({ sites, selectedId, onSelect, autoRotate, interactive }: {
  sites: Site[]; selectedId?: number; onSelect?: (site: Site) => void; autoRotate: boolean; interactive: boolean;
}) {
  return <>
    <color attach="background" args={["#080A0D"]} />
    <Stars radius={36} depth={20} count={900} factor={1.2} saturation={0} fade speed={0.18} />
    <ambientLight intensity={0.65} />
    <directionalLight position={[-3.5, 1.6, 4]} intensity={2.1} color="#fff8ec" />
    <Suspense fallback={<MoonPlaceholder />}><MoonModel autoRotate={autoRotate} /></Suspense>
    {sites.map((site) => <SiteMarker key={site.id} site={site} active={site.id === selectedId} onSelect={onSelect ?? (() => undefined)} />)}
    {interactive && <OrbitControls enablePan={false} minDistance={2.1} maxDistance={5} rotateSpeed={0.55} />}
  </>;
}

export function MoonScene({ sites, selectedId, onSelect, autoRotate = false, interactive = false, className = "" }: {
  sites: Site[]; selectedId?: number; onSelect?: (site: Site) => void; autoRotate?: boolean; interactive?: boolean; className?: string;
}) {
  return <div className={`moon-canvas ${className}`}>
    <Canvas camera={{ position: [0, 0.15, 3.35], fov: 38 }} dpr={[1, 1]} frameloop={autoRotate ? "always" : "demand"} gl={{ antialias: true, alpha: false }}>
      <Scene sites={sites} selectedId={selectedId} onSelect={onSelect} autoRotate={autoRotate} interactive={interactive} />
    </Canvas>
  </div>;
}

useGLTF.preload(moonModelUrl);
