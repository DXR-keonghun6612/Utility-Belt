import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import { SceneNode } from './core/SceneNode';
import { NodeRegistry } from './core/NodeRegistry';
import { SceneDeserializer } from './core/SceneDeserializer';
import { type SceneSnapshot, type NodeDescriptor } from './core/NodeAssembler';
import { AssetManager } from './core/AssetManager';
import { BROADCAST_CHANNEL } from './ui/AssetEditorApp';

import { TabManager }      from './ui/TabManager';
import { SceneGraphPanel } from './ui/SceneGraphPanel';
import { InstancePanel }   from './ui/InstancePanel';
import { RaycastSelector } from './ui/RaycastSelector';
import { PresetPanel }     from './ui/PresetPanel';
import { BuilderPanel }    from './ui/BuilderPanel';

export class SceneEditorApp {
    private scene!:    THREE.Scene;
    private camera!:   THREE.PerspectiveCamera;
    private renderer!: THREE.WebGLRenderer;
    private controls!: OrbitControls;

    private sceneRoot!: SceneNode;

    private tabManager!:    TabManager;
    private graphPanel!:    SceneGraphPanel;
    private instancePanel!: InstancePanel;
    private presetPanel!:   PresetPanel;
    private builderPanel!:  BuilderPanel;

    private assetManager: AssetManager;

    constructor(assetManager: AssetManager) {
        this.assetManager = assetManager;
        this.initEngine();
        this.initUI();
        this.bindEvents();
    }

    public async start(initialPresetName?: string): Promise<void> {
        if (initialPresetName) {
            const snapshot = this.assetManager.getPreset(initialPresetName);
            await this.loadScene(snapshot);
        } else {
            // 빈 씬 생성
            await this.loadScene({ version: 1, scene: [] });
        }
        this.animate();
    }

    // ── THREE.js ─────────────────────────────────────

    private w(): number {
        const panel = document.getElementById('scene-panel');
        return window.innerWidth - (panel?.offsetWidth ?? 300);
    }
    private h(): number { return window.innerHeight; }

    private initEngine(): void {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color('#f4f6f9');

        this.camera = new THREE.PerspectiveCamera(35, this.w() / this.h(), 0.1, 1000);
        this.camera.position.set(0, 10, 40);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.w(), this.h());
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        document.body.appendChild(this.renderer.domElement);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.set(0, 5, 0);
        this.controls.update();

        this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const dir = new THREE.DirectionalLight(0xffffff, 0.6);
        dir.position.set(20, 50, 30);
        dir.castShadow = true;
        dir.shadow.mapSize.set(2048, 2048);
        this.scene.add(dir);

        const floor = new THREE.Mesh(
            new THREE.PlaneGeometry(150, 150),
            new THREE.MeshStandardMaterial({ color: '#ffffff', depthWrite: false }),
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -0.3;
        floor.receiveShadow = true;
        this.scene.add(floor);

        const grid = new THREE.GridHelper(150, 150, 0x000000, 0x000000);
        if (grid.material instanceof THREE.Material) {
            grid.material.opacity = 0.05;
            grid.material.transparent = true;
        }
        grid.position.y = -0.25;
        this.scene.add(grid);
    }

    // ── UI ───────────────────────────────────────────

    private initUI(): void {
        this.tabManager = new TabManager();

        this.graphPanel = new SceneGraphPanel(
            this.tabManager.sceneTreePane,
            (node) => this.onSelect(node),
            undefined,
            (node) => this.onRemoveNode(node),
            (node, newParent) => this.onReparentNode(node, newParent),
        );

        this.instancePanel = new InstancePanel(
            this.tabManager.sceneInspectorPane,
            this.assetManager,
            () => this.refreshPanels(),
        );
        this.instancePanel.clear();

        this.presetPanel = new PresetPanel(
            this.tabManager.sceneActionPane,
            (name) => this.assetManager.getModel(name),
            (root) => this.onSceneReloaded(root),
        );

        this.builderPanel = new BuilderPanel(
            this.tabManager.tabs['builder'],
            this.assetManager,
            () => this.refreshPanels(),
        );

        new RaycastSelector(
            this.scene,
            this.camera,
            this.renderer,
            (node) => this.onSelect(node),
        );
    }

    // ── Scene ────────────────────────────────────────

    private onRemoveNode(node: SceneNode): void {
        if (!node.parent) {
            console.warn('Cannot remove the root node.');
            return;
        }
        node.parent.removeChild(node);

        for (const n of node.flatten()) NodeRegistry.unregister(n);

        this.instancePanel.clear();
        this.refreshPanels();
    }

    private onReparentNode(node: SceneNode, newParent: SceneNode): void {
        if (node.parent === newParent) return;
        
        // prevent circular parenting
        let cur: SceneNode | null = newParent;
        while (cur) {
            if (cur === node) {
                console.warn('Cannot reparent a node to its own descendant.');
                return;
            }
            cur = cur.parent;
        }

        if (node.parent) {
            node.parent.removeChild(node);
        }
        newParent.addChild(node);
        this.refreshPanels();
        this.onSelect(node);
    }

    private async loadScene(snapshot: SceneSnapshot): Promise<void> {
        NodeRegistry.clear();
        this.sceneRoot = await SceneDeserializer.load(
            snapshot,
            (name) => this.assetManager.getModel(name)
        );
        this.scene.add(this.sceneRoot.object3D);
        this.refreshPanels();
    }

    private onSceneReloaded(root: SceneNode): void {
        this.scene.remove(this.sceneRoot.object3D);
        this.sceneRoot = root;
        this.scene.add(root.object3D);
        this.instancePanel.clear();
        this.refreshPanels();
    }

    private refreshPanels(): void {
        this.graphPanel.render([this.sceneRoot]);
        this.builderPanel.setRoots([this.sceneRoot]);
        this.presetPanel.setRoot(this.sceneRoot);
    }

    // ── Selection ────────────────────────────────────

    private onSelect(node: SceneNode): void {
        this.instancePanel.show(node);
        this.graphPanel.highlight(node);
        this.tabManager.switchTo('scene');
    }

    // ── Loop ─────────────────────────────────────────

    private bindEvents(): void {
        const syncRenderer = () => {
            this.camera.aspect = this.w() / this.h();
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.w(), this.h());
        };
        window.addEventListener('resize', syncRenderer);
        new ResizeObserver(syncRenderer).observe(this.tabManager.panel);

        // Asset Editor 탭에서 전송된 에셋을 AssetManager에 등록
        const channel = new BroadcastChannel(BROADCAST_CHANNEL);
        channel.addEventListener('message', (e: MessageEvent) => {
            if (e.data?.type !== 'ASSET_SAVED') return;
            const { name, descriptor } = e.data as { name: string; descriptor: NodeDescriptor };
            this.assetManager.registerModel(name, descriptor);
            this._showToast(`Asset "${name}" registered`);
        });
    }

    private _showToast(msg: string): void {
        const el = document.createElement('div');
        el.style.cssText = `
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            background: #004d5f; border: 1px solid #00bcd4; color: #00bcd4;
            font-family: monospace; font-size: 12px; padding: 6px 16px;
            border-radius: 4px; z-index: 9999; pointer-events: none;
        `;
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 2500);
    }

    private animate(): void {
        requestAnimationFrame(this.animate.bind(this));
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
}
