"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { fetchJson } from "@/lib/api";
import type { MeshResponse, StoneMesh } from "@/lib/types";

type ViewerState = {
    status: "idle" | "loading" | "ready" | "error";
    error?: string;
    payload?: MeshResponse | null;
};

const COLORS = ["#0b7d77", "#1e9a92", "#63b8b1"];

const buildGeometry = (mesh: StoneMesh) => {
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(mesh.vertices.flat());
    const indices = new Uint32Array(mesh.faces.flat());
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setIndex(new THREE.BufferAttribute(indices, 1));
    geometry.computeVertexNormals();
    return geometry;
};

const disposeObject = (object: THREE.Object3D) => {
    object.traverse((child) => {
        if (child instanceof THREE.Mesh) {
            if (child.geometry) {
                child.geometry.dispose();
            }
            if (Array.isArray(child.material)) {
                child.material.forEach((material) => material.dispose());
            } else if (child.material) {
                child.material.dispose();
            }
        }
    });
};

export default function StoneMeshViewer({
    analysisId,
    title = "3D stone model",
}: {
    analysisId?: string | null;
    title?: string;
}) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [state, setState] = useState<ViewerState>({
        status: "idle",
        payload: null,
    });

    const metadata = state.payload?.metadata;
    const meshCount = useMemo(() => {
        if (metadata && typeof metadata === "object") {
            const value = (metadata as Record<string, unknown>).stone_count;
            if (typeof value === "number") {
                return value;
            }
        }
        return state.payload?.meshes?.length || 0;
    }, [metadata, state.payload]);

    useEffect(() => {
        if (!analysisId) {
            setState({ status: "idle", payload: null });
            return;
        }

        let isActive = true;
        setState({ status: "loading", payload: null });

        fetchJson<MeshResponse>(`/analyses/${analysisId}/mesh`).then((response) => {
            if (!isActive) {
                return;
            }
            if (response.error) {
                setState({ status: "error", error: response.error, payload: null });
                return;
            }
            const payload = response.data || null;
            if (!payload || !payload.available || !payload.meshes?.length) {
                setState({
                    status: "ready",
                    payload: payload || { available: false, meshes: [] },
                });
                return;
            }
            setState({ status: "ready", payload });
        });

        return () => {
            isActive = false;
        };
    }, [analysisId]);

    useEffect(() => {
        const container = containerRef.current;
        const payload = state.payload;
        if (!container || state.status !== "ready" || !payload?.available) {
            return;
        }

        container.innerHTML = "";
        const width = container.clientWidth || 480;
        const height = container.clientHeight || 360;

        const scene = new THREE.Scene();
        scene.background = new THREE.Color("#10181b");

        const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000);
        camera.position.set(80, 50, 80);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(width, height);
        container.appendChild(renderer.domElement);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
        controls.rotateSpeed = 0.55;
        controls.zoomSpeed = 0.8;

        const ambient = new THREE.AmbientLight(0xffffff, 0.65);
        const keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
        keyLight.position.set(1, 1, 1);
        const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
        fillLight.position.set(-1, -0.4, 0.6);
        scene.add(ambient, keyLight, fillLight);

        const group = new THREE.Group();
        payload.meshes.forEach((mesh, index) => {
            const geometry = buildGeometry(mesh);
            const material = new THREE.MeshStandardMaterial({
                color: new THREE.Color(COLORS[index % COLORS.length]),
                roughness: 0.35,
                metalness: 0.08,
                transparent: true,
                opacity: 0.95,
            });
            const stone = new THREE.Mesh(geometry, material);
            group.add(stone);
        });
        scene.add(group);

        const box = new THREE.Box3().setFromObject(group);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        group.position.sub(center);

        const maxDim = Math.max(size.x, size.y, size.z);
        const distance = maxDim > 0 ? maxDim * 1.8 : 80;
        camera.near = Math.max(distance / 100, 0.1);
        camera.far = Math.max(distance * 10, 200);
        camera.position.set(distance, distance * 0.6, distance * 1.1);
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.update();

        let frameId = 0;
        const animate = () => {
            frameId = window.requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        };
        animate();

        const handleResize = () => {
            if (!container) {
                return;
            }
            const nextWidth = container.clientWidth || 480;
            const nextHeight = container.clientHeight || 360;
            camera.aspect = nextWidth / nextHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(nextWidth, nextHeight);
        };
        window.addEventListener("resize", handleResize);

        return () => {
            window.removeEventListener("resize", handleResize);
            window.cancelAnimationFrame(frameId);
            controls.dispose();
            disposeObject(group);
            renderer.dispose();
            container.innerHTML = "";
        };
    }, [state.payload, state.status]);

    return (
        <div className="card mesh-card">
            <div className="card-header">
                <h2>{title}</h2>
                <span className="badge">Interactive</span>
            </div>
            <p className="muted">
                Drag to rotate. Scroll or pinch to zoom. Mesh loads from the
                latest CT segmentation output.
            </p>
            <div className="mesh-meta">
                <div>
                    <span>Stone meshes</span>
                    <strong>{meshCount}</strong>
                </div>
                <div>
                    <span>Status</span>
                    <strong>
                        {state.status === "loading"
                            ? "Loading"
                            : state.status === "error"
                            ? "Error"
                            : state.payload?.available
                            ? "Ready"
                            : "Unavailable"}
                    </strong>
                </div>
            </div>
            {state.status === "error" ? (
                <p className="status error">{state.error || "Unable to load mesh."}</p>
            ) : null}
            <div className="mesh-canvas" ref={containerRef} />
            {!state.payload?.available && state.status === "ready" ? (
                <p className="empty">
                    No mesh available yet. Ensure segmentation ran and a 3D model
                    was generated for this analysis.
                </p>
            ) : null}
        </div>
    );
}
