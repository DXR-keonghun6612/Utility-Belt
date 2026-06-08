import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js';

import { SceneNode } from '../../core/SceneNode';
import { NodeRegistry } from '../../core/NodeRegistry';

export interface ViewportConfig {
    bgColor?:        string;
    cameraFov?:      number;
    cameraPosition?: [number, number, number];
    orbitTarget?:    [number, number, number];
    gridSize?:       number;
    gridDivisions?:  number;
    gridColor?:      number;
    gridOpacity?:    number;
    gridOffsetY?:    number;
}

export class ViewportBase {
    // ── Three.js ──────────────────────────────────────────────────
    protected scene!:             THREE.Scene;
    protected camera!:            THREE.PerspectiveCamera;
    protected renderer!:          THREE.WebGLRenderer;
    protected controls!:          OrbitControls;
    protected transformControls!: TransformControls;

    // ── 선택 / 기즈모 ─────────────────────────────────────────────
    protected selectedNodeId: string | null = null;
    private   selectionBox:   THREE.BoxHelper | null = null;
    protected gizmoWasActive  = false;
    protected gizmoDragging   = false;

    // ── 스냅 ──────────────────────────────────────────────────────
    private snapEnabled           = true;
    private readonly snapThreshold    = 0.5;
    private readonly unsnapThreshold  = 0.8;
    private activeSnapTargetPt:   THREE.Vector3 | null = null;
    private activeSnapDraggedLocal: THREE.Vector3 | null = null;
    private snapIndicatorObj!:    THREE.Object3D;

    // ── Scene root ────────────────────────────────────────────────
    protected sceneRootObj:  THREE.Object3D | null = null;
    protected sceneRootNode: SceneNode | null = null;

    // ── Callbacks ─────────────────────────────────────────────────
    private onNodeSelectedCb:  (id: string | null) => void;
    private onGizmoDragEndCb:  (id: string, pos: THREE.Vector3, rot: THREE.Euler) => void;

    constructor(
        container: HTMLElement,
        callbacks: {
            onNodeSelected:  (id: string | null) => void;
            onGizmoDragEnd:  (id: string, pos: THREE.Vector3, rot: THREE.Euler) => void;
        },
        config: ViewportConfig = {},
    ) {
        this.onNodeSelectedCb = callbacks.onNodeSelected;
        this.onGizmoDragEndCb = callbacks.onGizmoDragEnd;
        this._initEngine(container, config);
        this._setupInteraction();
        this._animate();
    }

    // ── Public API ────────────────────────────────────────────────

    setScene(rootObj: THREE.Object3D, rootNode: SceneNode): void {
        if (this.sceneRootObj) this.scene.remove(this.sceneRootObj);
        this.sceneRootObj  = rootObj;
        this.sceneRootNode = rootNode;
        this.scene.add(rootObj);
        this._onSceneChanged();
    }

    restoreSelection(prevNodeId: string | null): void {
        if (prevNodeId && NodeRegistry.get(prevNodeId)) {
            this._selectNode(prevNodeId);
        }
    }

    detachGizmo(): void {
        this.transformControls.detach();
        if (this.selectionBox) {
            this.scene.remove(this.selectionBox);
            this.selectionBox = null;
        }
        this.selectedNodeId = null;
    }

    getSelectedNodeId(): string | null { return this.selectedNodeId; }

    setSnapEnabled(v: boolean): void { this.snapEnabled = v; }

    // ── Protected hooks (서브클래스에서 override) ──────────────────

    /** 드래그 중인 node / 타겟 node의 로컬 snap point 목록. 빈 배열 = snap 비활성. */
    protected _getSnapPoints(_node: SceneNode): THREE.Vector3[] { return []; }

    /** raycast 대상 object 목록 */
    protected _getRaycastTargets(): THREE.Object3D[] {
        return this.sceneRootObj ? [this.sceneRootObj] : [];
    }

    /** 클릭 이벤트 처리. 서브클래스에서 mode 필터 등을 추가할 때 override. */
    protected _handleRaycast(e: PointerEvent): void {
        const targets = this._getRaycastTargets();
        if (targets.length === 0) return;

        const canvas = this.renderer.domElement;
        const rect   = canvas.getBoundingClientRect();
        const mouse  = new THREE.Vector2(
            ((e.clientX - rect.left) / rect.width)  *  2 - 1,
            -((e.clientY - rect.top)  / rect.height) *  2 + 1,
        );
        const raycaster = new THREE.Raycaster();
        raycaster.params.Line = { threshold: 0.1 };
        raycaster.setFromCamera(mouse, this.camera);

        for (const hit of raycaster.intersectObjects(targets, true)) {
            const nodeId = this._nodeIdFromHit(hit.object);
            if (!nodeId) continue;
            if (!NodeRegistry.get(nodeId)) continue;
            this._selectNode(nodeId);
            return;
        }
        this._selectNode(null);
    }

    /** setScene 후 서브클래스 후처리 훅 */
    protected _onSceneChanged(): void {}

    // ── Node 선택 (서브클래스에서 필요시 호출) ────────────────────

    protected _selectNode(nodeId: string | null): void {
        this.transformControls.detach();
        if (this.selectionBox) {
            this.scene.remove(this.selectionBox);
            this.selectionBox = null;
        }
        this.selectedNodeId = nodeId;

        if (!nodeId) { this.onNodeSelectedCb(null); return; }

        const sceneNode = NodeRegistry.get(nodeId);
        if (!sceneNode) return;

        this.transformControls.attach(sceneNode.object3D);
        this.selectionBox = new THREE.BoxHelper(sceneNode.object3D, 0x81d4fa);
        this.scene.add(this.selectionBox);
        this.onNodeSelectedCb(nodeId);
    }

    protected _nodeIdFromHit(obj: THREE.Object3D): string | null {
        let cur: THREE.Object3D | null = obj;
        while (cur) {
            if (cur.userData['nodeId']) return cur.userData['nodeId'] as string;
            cur = cur.parent;
        }
        return null;
    }

    // ── Engine init ───────────────────────────────────────────────

    private _initEngine(container: HTMLElement, cfg: ViewportConfig): void {
        const {
            bgColor        = '#1a1e28',
            cameraFov      = 45,
            cameraPosition = [0, 8, 20] as [number, number, number],
            orbitTarget    = [0, 2, 0]  as [number, number, number],
            gridSize       = 40,
            gridDivisions  = 40,
            gridColor      = 0x333344,
            gridOpacity,
            gridOffsetY    = 0,
        } = cfg;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(bgColor);

        this.camera = new THREE.PerspectiveCamera(
            cameraFov,
            container.clientWidth / container.clientHeight,
            0.1, 1000,
        );
        this.camera.position.set(...cameraPosition);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(container.clientWidth, container.clientHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(this.renderer.domElement);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.set(...orbitTarget);
        this.controls.update();

        this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const dir = new THREE.DirectionalLight(0xffffff, 0.6);
        dir.position.set(10, 20, 15);
        dir.castShadow = true;
        this.scene.add(dir);

        const grid = new THREE.GridHelper(gridSize, gridDivisions, gridColor, gridColor);
        if (gridOpacity !== undefined && grid.material instanceof THREE.Material) {
            grid.material.opacity     = gridOpacity;
            grid.material.transparent = true;
        }
        grid.position.y = gridOffsetY;
        this.scene.add(grid);

        this.transformControls = new TransformControls(this.camera, this.renderer.domElement);
        this.transformControls.setMode('translate');
        this.transformControls.addEventListener('dragging-changed', (event) => {
            const e = event as unknown as { value: boolean };
            this.controls.enabled = !e.value;
            this.gizmoDragging    = e.value;
            if (e.value) {
                this.gizmoWasActive        = true;
                this.activeSnapTargetPt    = null;
                this.activeSnapDraggedLocal = null;
            } else {
                this.snapIndicatorObj.visible = false;
                this.activeSnapTargetPt    = null;
                this.activeSnapDraggedLocal = null;
                this._onGizmoDragEnd();
            }
        });
        this.transformControls.addEventListener('change', () => {
            if (this.gizmoDragging && this.snapEnabled) this._applySnap();
        });
        this.scene.add(this.transformControls.getHelper() as unknown as THREE.Object3D);

        this._initSnapIndicator();

        window.addEventListener('keydown', (e) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
            if (e.key === 't' || e.key === 'T') this.transformControls.setMode('translate');
            if (e.key === 'r' || e.key === 'R') this.transformControls.setMode('rotate');
            if (e.key === 'Escape') this._selectNode(null);
        });

        new ResizeObserver(entries => {
            const { width, height } = entries[0].contentRect;
            if (width <= 0 || height <= 0) return;
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(width, height);
        }).observe(container);
    }

    private _animate(): void {
        requestAnimationFrame(this._animate.bind(this));
        this.controls.update();
        if (this.selectionBox) this.selectionBox.update();
        this.renderer.render(this.scene, this.camera);
    }

    private _setupInteraction(): void {
        const canvas = this.renderer.domElement;
        let downPos = { x: 0, y: 0 };
        let moved   = false;

        canvas.addEventListener('pointerdown', (e) => { downPos = { x: e.clientX, y: e.clientY }; moved = false; });
        canvas.addEventListener('pointermove', (e) => {
            const dx = e.clientX - downPos.x, dy = e.clientY - downPos.y;
            if (Math.sqrt(dx * dx + dy * dy) > 4) moved = true;
        });
        canvas.addEventListener('pointerup', (e) => {
            const wasGizmo = this.gizmoWasActive;
            this.gizmoWasActive = false;
            if (moved || wasGizmo) return;
            this._handleRaycast(e);
        });
    }

    private _onGizmoDragEnd(): void {
        const nodeId = this.selectedNodeId;
        if (!nodeId) return;
        const node = NodeRegistry.get(nodeId);
        if (!node) return;
        this.onGizmoDragEndCb(nodeId, node.object3D.position.clone(), node.object3D.rotation.clone());
    }

    // ── Snap ──────────────────────────────────────────────────────

    private _initSnapIndicator(): void {
        const group = new THREE.Group();
        const sphere = new THREE.Mesh(
            new THREE.SphereGeometry(0.09, 8, 8),
            new THREE.MeshBasicMaterial({ color: 0x00e5ff, depthTest: false }),
        );
        sphere.renderOrder = 999;
        group.add(sphere);

        const lineMat = new THREE.LineBasicMaterial({ color: 0x00e5ff, depthTest: false });
        const s = 0.35;
        for (const [ax, ay, az] of [[s,0,0],[0,s,0],[0,0,s]] as [number,number,number][]) {
            const geo  = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(-ax, -ay, -az),
                new THREE.Vector3( ax,  ay,  az),
            ]);
            const line = new THREE.Line(geo, lineMat);
            line.renderOrder = 999;
            group.add(line);
        }
        group.visible = false;
        this.scene.add(group);
        this.snapIndicatorObj = group;
    }

    private _applySnap(): void {
        if (!this.selectedNodeId) return;
        const node = NodeRegistry.get(this.selectedNodeId);
        if (!node) return;

        const worldQuat = new THREE.Quaternion();
        node.object3D.getWorldQuaternion(worldQuat);
        const worldPos = new THREE.Vector3();
        node.object3D.getWorldPosition(worldPos);

        if (this.activeSnapTargetPt && this.activeSnapDraggedLocal) {
            const curDraggedWorld = this.activeSnapDraggedLocal.clone()
                .applyQuaternion(worldQuat).add(worldPos);
            if (curDraggedWorld.distanceTo(this.activeSnapTargetPt) <= this.unsnapThreshold) {
                this._warpSnapPoint(node, this.activeSnapDraggedLocal, this.activeSnapTargetPt);
                return;
            }
            this.activeSnapTargetPt     = null;
            this.activeSnapDraggedLocal  = null;
            this.snapIndicatorObj.visible = false;
        }

        const pair = this._nearestSnapPair(node, worldQuat, worldPos);
        if (pair && pair.dist <= this.snapThreshold) {
            this.activeSnapTargetPt     = pair.targetWorld.clone();
            this.activeSnapDraggedLocal  = pair.draggedLocal.clone();
            this._warpSnapPoint(node, pair.draggedLocal, pair.targetWorld);
            this.snapIndicatorObj.position.copy(pair.targetWorld);
            this.snapIndicatorObj.visible = true;
        } else {
            this.snapIndicatorObj.visible = false;
        }
    }

    private _warpSnapPoint(node: SceneNode, localPt: THREE.Vector3, worldTarget: THREE.Vector3): void {
        const worldQuat = new THREE.Quaternion();
        node.object3D.getWorldQuaternion(worldQuat);
        const originTarget = worldTarget.clone().sub(localPt.clone().applyQuaternion(worldQuat));
        const parent = node.object3D.parent;
        if (!parent) {
            node.object3D.position.copy(originTarget);
        } else {
            node.object3D.position.copy(parent.worldToLocal(originTarget));
        }
    }

    private _nearestSnapPair(
        dragged: SceneNode,
        draggedWorldQuat: THREE.Quaternion,
        draggedWorldPos: THREE.Vector3,
    ): { draggedLocal: THREE.Vector3; targetWorld: THREE.Vector3; dist: number } | null {
        const draggedLocals = this._getSnapPoints(dragged);
        if (draggedLocals.length === 0) return null;

        let best: { draggedLocal: THREE.Vector3; targetWorld: THREE.Vector3; dist: number } | null = null;

        const walk = (node: SceneNode) => {
            if (node === dragged) return;
            const targetLocals = this._getSnapPoints(node);
            if (targetLocals.length > 0) {
                const tQuat = new THREE.Quaternion();
                node.object3D.getWorldQuaternion(tQuat);
                const tPos = new THREE.Vector3();
                node.object3D.getWorldPosition(tPos);
                for (const tLocal of targetLocals) {
                    const tWorld = tLocal.clone().applyQuaternion(tQuat).add(tPos);
                    for (const dLocal of draggedLocals) {
                        const dWorld = dLocal.clone().applyQuaternion(draggedWorldQuat).add(draggedWorldPos);
                        const dist = dWorld.distanceTo(tWorld);
                        if (!best || dist < best.dist) {
                            best = { draggedLocal: dLocal.clone(), targetWorld: tWorld.clone(), dist };
                        }
                    }
                }
            }
            for (const child of node.children) walk(child);
        };

        if (this.sceneRootNode) walk(this.sceneRootNode);
        return best;
    }
}
