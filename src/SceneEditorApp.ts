import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import { SceneNode } from './core/SceneNode';
import { NodeRegistry } from './core/NodeRegistry';
import { SceneDeserializer } from './core/SceneDeserializer';
import { NodeAssembler, type SceneSnapshot } from './core/NodeAssembler';
import { AssetManager } from './core/AssetManager';

import { TabManager }      from './ui/TabManager';
import { SceneGraphPanel } from './ui/SceneGraphPanel';
import { PropertiesPanel } from './ui/PropertiesPanel';
import { RaycastSelector } from './ui/RaycastSelector';
import { PresetPanel }     from './ui/PresetPanel';
import { BuilderPanel }    from './ui/BuilderPanel';

export class SceneEditorApp {
    private scene!:    THREE.Scene;
    private camera!:   THREE.PerspectiveCamera;
    private renderer!: THREE.WebGLRenderer;
    private controls!: OrbitControls;

    private sceneRoot!: SceneNode;

    private tabManager!:   TabManager;
    private graphPanel!:   SceneGraphPanel;
    private propsPanel!:   PropertiesPanel;
    private presetPanel!:  PresetPanel;
    private builderPanel!: BuilderPanel;

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

    private w(): number { return window.innerWidth - 300; }
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
            (node) => this.onAddToJoint(node),
            (node) => this.onRemoveNode(node),
            (node, newParent) => this.onReparentNode(node, newParent),
        );

        this.propsPanel = new PropertiesPanel(this.tabManager.sceneInspectorPane);
        this.propsPanel.clear();

        this.presetPanel = new PresetPanel(
            this.tabManager.sceneActionPane,
            (name) => this.assetManager.getModel(name),
            (root) => this.onSceneReloaded(root),
        );

        this.builderPanel = new BuilderPanel(this.tabManager.tabs['builder'], () => {
            // Apply or tree changes in BuilderPanel should update Scene UI
            this.refreshPanels();
        });

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
        
        // Remove from registry recursively
        const nodesToRemove = node.flatten();
        for (const n of nodesToRemove) {
            NodeRegistry.unregister(n);
        }
        
        this.propsPanel.clear();
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

    private async onAddToJoint(jointNode: SceneNode): Promise<void> {
        const available = this.assetManager.getAllModelNames();
        const msg = `Select a model to attach to [${jointNode.label}].\n\nAvailable models:\n${available.join('\n')}`;
        const chosen = prompt(msg);
        if (!chosen) return;

        if (!available.includes(chosen)) {
            alert(`Model '${chosen}' not found.`);
            return;
        }

        try {
            const descriptor = this.assetManager.getModel(chosen);
            const instanceId = `${chosen}_${Math.floor(Math.random() * 10000)}`;
            
            // SceneDeserializer 대신 NodeAssembler를 직접 사용하여 'scene' 중복 ID 방지
            const newGroup = NodeAssembler.load(descriptor, instanceId);
            
            // 모델 출처 기록 — SceneSerializer가 나중에 저장할 때 사용
            newGroup.metadata._modelName = chosen;

            jointNode.addChild(newGroup);
            
            // Re-render panels
            this.refreshPanels();
            this.onSelect(newGroup);
        } catch (err) {
            console.error('Failed to attach model:', err);
            alert(`Failed to attach model: ${(err as Error).message}`);
        }
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
        this.propsPanel.clear();
        this.refreshPanels();
    }

    private refreshPanels(): void {
        this.graphPanel.render([this.sceneRoot]);
        this.builderPanel.setRoots([this.sceneRoot]);
        this.presetPanel.setRoot(this.sceneRoot);
    }

    // ── Selection ────────────────────────────────────

    private onSelect(node: SceneNode): void {
        this.propsPanel.show(node);
        this.graphPanel.highlight(node);
        this.tabManager.switchTo('scene');
    }

    // ── Loop ─────────────────────────────────────────

    private bindEvents(): void {
        window.addEventListener('resize', () => {
            this.camera.aspect = this.w() / this.h();
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.w(), this.h());
        });
    }

    private animate(): void {
        requestAnimationFrame(this.animate.bind(this));
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
}
