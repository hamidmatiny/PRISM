import {
  AmbientLight,
  BoxGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  Group,
  Mesh,
  Object3D,
  PerspectiveCamera,
  PlaneGeometry,
  Raycaster,
  Scene,
  Vector2,
  MeshStandardNodeMaterial,
} from "three/webgpu";
import { color as tslColor } from "three/tsl";
import type { FleetAssetView } from "@/api/types";
import { createHealthMaterial } from "./healthMaterial";
import { createTwinRenderer, type TwinRenderer } from "./createRenderer";

export class FleetScene {
  readonly scene = new Scene();
  readonly camera: PerspectiveCamera;
  readonly root = new Group();
  private renderer!: TwinRenderer;
  private backend: "webgpu" | "webgl" = "webgl";
  private assets = new Map<string, Mesh>();
  private raycaster = new Raycaster();
  private pointer = new Vector2();
  private running = false;
  private reducedMotion = false;
  private onSelect: (assetId: string | null) => void;
  private canvas: HTMLCanvasElement;

  constructor(canvas: HTMLCanvasElement, onSelect: (assetId: string | null) => void) {
    this.canvas = canvas;
    this.onSelect = onSelect;
    this.camera = new PerspectiveCamera(45, 1, 0.1, 200);
    this.camera.position.set(8, 10, 14);
    this.camera.lookAt(0, 0, 0);
    this.scene.background = new Color("#0b0f14");
    this.scene.add(this.root);

    const amb = new AmbientLight(0x9aabbd, 0.45);
    const key = new DirectionalLight(0xe8eef5, 1.1);
    key.position.set(6, 12, 4);
    this.scene.add(amb, key);

    const floorMat = new MeshStandardNodeMaterial();
    floorMat.colorNode = tslColor(new Color("#121820"));
    floorMat.roughness = 0.92;
    floorMat.metalness = 0.05;
    const floor = new Mesh(new PlaneGeometry(40, 40), floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    this.root.add(floor);

    this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  async init(): Promise<"webgpu" | "webgl"> {
    const { renderer, backend } = await createTwinRenderer(this.canvas);
    this.renderer = renderer;
    this.backend = backend;
    this.resize();
    this.canvas.addEventListener("pointerdown", this.onPointer);
    this.canvas.tabIndex = 0;
    this.canvas.setAttribute("role", "application");
    this.canvas.setAttribute(
      "aria-label",
      "Fleet digital twin. Click or press Enter on focused asset markers.",
    );
    return backend;
  }

  setAssets(list: FleetAssetView[]): void {
    const keep = new Set(list.map((a) => a.asset_id));
    for (const [id, mesh] of this.assets) {
      if (!keep.has(id)) {
        this.root.remove(mesh);
        mesh.geometry.dispose();
        (mesh.material as MeshStandardNodeMaterial).dispose();
        this.assets.delete(id);
      }
    }
    for (const asset of list) {
      let mesh = this.assets.get(asset.asset_id);
      if (!mesh) {
        mesh = this.buildAssetMesh(asset);
        this.assets.set(asset.asset_id, mesh);
        this.root.add(mesh);
      } else {
        this.restyle(mesh, asset);
      }
      mesh.position.set(...asset.position);
      mesh.userData.assetId = asset.asset_id;
    }
  }

  private buildAssetMesh(asset: FleetAssetView): Mesh {
    const body = new BoxGeometry(1.4, 1.1, 2.2);
    const material = createHealthMaterial(asset.health);
    if (this.reducedMotion) {
      // Static emissive — TSL pulse disabled via zero intensity path in material factory.
    }
    const mesh = new Mesh(body, material);
    const mast = new Mesh(
      new CylinderGeometry(0.08, 0.08, 1.4, 8),
      createHealthMaterial(asset.health),
    );
    mast.position.y = 1.2;
    mesh.add(mast);
    return mesh;
  }

  private restyle(mesh: Mesh, asset: FleetAssetView): void {
    const old = mesh.material as MeshStandardNodeMaterial;
    old.dispose();
    mesh.material = createHealthMaterial(asset.health);
    mesh.children.forEach((child) => {
      if (child instanceof Mesh) {
        (child.material as MeshStandardNodeMaterial).dispose();
        child.material = createHealthMaterial(asset.health);
      }
    });
  }

  highlight(assetId: string | null): void {
    for (const [id, mesh] of this.assets) {
      mesh.scale.setScalar(id === assetId ? 1.12 : 1);
    }
  }

  resize = (): void => {
    const parent = this.canvas.parentElement;
    if (!parent || !this.renderer) return;
    const w = parent.clientWidth;
    const h = parent.clientHeight;
    this.camera.aspect = w / Math.max(h, 1);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  };

  private onPointer = (ev: PointerEvent): void => {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObjects([...this.assets.values()], true);
    if (!hits.length) {
      this.onSelect(null);
      return;
    }
    let obj: Object3D | null = hits[0].object;
    while (obj && !obj.userData.assetId) obj = obj.parent;
    this.onSelect((obj?.userData.assetId as string) || null);
  };

  start(): void {
    if (this.running) return;
    this.running = true;
    const loop = () => {
      if (!this.running) return;
      // Gentle orbit for presence — skipped under reduced motion.
      if (!this.reducedMotion) {
        const t = performance.now() * 0.00015;
        this.camera.position.x = Math.sin(t) * 14;
        this.camera.position.z = Math.cos(t) * 14;
        this.camera.lookAt(0, 0.5, 0);
      }
      void this.renderer.render(this.scene, this.camera);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
    this.canvas.removeEventListener("pointerdown", this.onPointer);
    this.renderer?.dispose();
  }

  getBackend(): "webgpu" | "webgl" {
    return this.backend;
  }
}
