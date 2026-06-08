import * as THREE from 'three';

import { SceneNode, NodeType } from '../../core/SceneNode';
import { NodeRegistry } from '../../core/NodeRegistry';
import { NodeFactory, GeometryDescriptor } from '../../core/NodeFactory';
import { AnchorLayout } from '../../core/NodeAssembler';
import { ViewportBase } from '../shared/ViewportBase';

export class Viewport3D extends ViewportBase {
    // ── Asset-editor 전용 ─────────────────────────────────────────
    private selectMode: 'link' | 'joint-anchor' = 'link';

    private anchorMarkersGroup = new THREE.Group();
    private jointMarkersGroup  = new THREE.Group();
    private showAnchorMarkers  = true;
    private showJointMarkers   = true;

    constructor(
        container: HTMLElement,
        callbacks: {
            onNodeSelected: (nodeId: string | null) => void;
            onGizmoDragEnd: (nodeId: string, pos: THREE.Vector3, rot: THREE.Euler) => void;
        },
    ) {
        super(container, callbacks, {
            bgColor:        '#1a1e28',
            cameraFov:      45,
            cameraPosition: [0, 8, 20],
            orbitTarget:    [0, 2, 0],
            gridSize:       40,
            gridDivisions:  40,
            gridColor:      0x333344,
        });
        this.scene.add(this.anchorMarkersGroup);
        this.scene.add(this.jointMarkersGroup);
    }

    // ── Public API ────────────────────────────────────────────────

    setDraftScene(rootObj: THREE.Object3D, rootNode: SceneNode): void {
        this.setScene(rootObj, rootNode);
    }

    setSelectMode(mode: 'link' | 'joint-anchor'): void { this.selectMode = mode; }

    setShowAnchorMarkers(v: boolean): void {
        this.showAnchorMarkers = v;
        this.anchorMarkersGroup.visible = v;
    }

    setShowJointMarkers(v: boolean): void {
        this.showJointMarkers = v;
        this.jointMarkersGroup.visible = v;
    }

    // ── ViewportBase override ─────────────────────────────────────

    protected _getSnapPoints(node: SceneNode): THREE.Vector3[] {
        if (node.type !== NodeType.LINK) return [];
        const geo = node.metadata['_geometryDescriptor'] as GeometryDescriptor | null;
        return geo ? NodeFactory.getSnapPoints(geo) : [];
    }

    protected _getRaycastTargets(): THREE.Object3D[] {
        if (!this.sceneRootObj) return [];
        return [this.sceneRootObj, this.anchorMarkersGroup, this.jointMarkersGroup];
    }

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

        let anyNodeHit = false;
        for (const hit of raycaster.intersectObjects(targets, true)) {
            const nodeId = this._nodeIdFromHit(hit.object);
            if (!nodeId) continue;
            const node = NodeRegistry.get(nodeId);
            if (!node) continue;

            anyNodeHit = true;

            if (this.selectMode === 'link' && node.type !== NodeType.LINK) continue;
            if (this.selectMode === 'joint-anchor' &&
                node.type !== NodeType.JOINT && node.type !== NodeType.ANCHOR) continue;

            this._selectNode(nodeId);
            return;
        }
        if (!anyNodeHit) this._selectNode(null);
    }

    protected _onSceneChanged(): void {
        this._updateAnchorMarkers();
        this._updateJointMarkers();
    }

    // ── Anchor / Joint markers ────────────────────────────────────

    private _collectExposedAnchors(root: SceneNode): SceneNode[] {
        const result: SceneNode[] = [];
        const traverse = (node: SceneNode) => {
            if (node.type === NodeType.ANCHOR) {
                const layout = node.metadata['_layoutDescriptor'] as AnchorLayout | null;
                if (layout?.exposed !== false) result.push(node);
            }
            for (const child of node.children) traverse(child);
        };
        traverse(root);
        return result;
    }

    private _disposeGroup(group: THREE.Group): void {
        group.children.slice().forEach(c => {
            group.remove(c);
            if ((c as THREE.Mesh).geometry) (c as THREE.Mesh).geometry.dispose();
        });
    }

    private _updateAnchorMarkers(): void {
        this._disposeGroup(this.anchorMarkersGroup);
        if (!this.sceneRootNode) return;

        const mat = new THREE.MeshBasicMaterial({ color: 0x81c784, depthTest: false });
        for (const node of this._collectExposedAnchors(this.sceneRootNode)) {
            const worldPos  = new THREE.Vector3();
            const worldQuat = new THREE.Quaternion();
            node.object3D.getWorldPosition(worldPos);
            node.object3D.getWorldQuaternion(worldQuat);

            const sphere = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), mat);
            sphere.position.copy(worldPos);
            sphere.renderOrder = 999;
            sphere.userData['nodeId'] = node.id;

            const axes = new THREE.AxesHelper(0.5);
            axes.position.copy(worldPos);
            axes.quaternion.copy(worldQuat);
            axes.renderOrder = 999;
            axes.userData['nodeId'] = node.id;

            this.anchorMarkersGroup.add(sphere, axes);
        }
        this.anchorMarkersGroup.visible = this.showAnchorMarkers;
    }

    private _updateJointMarkers(): void {
        this._disposeGroup(this.jointMarkersGroup);
        if (!this.sceneRootNode) return;

        const sphereMat  = new THREE.MeshBasicMaterial({ color: 0xb39ddb, depthTest: false });
        const axisColors: Record<string, number> = { x: 0xff5555, y: 0x55dd55, z: 0x5599ff };

        const traverse = (node: SceneNode) => {
            if (node.type === NodeType.JOINT) {
                const worldPos  = new THREE.Vector3();
                const worldQuat = new THREE.Quaternion();
                node.object3D.getWorldPosition(worldPos);
                node.object3D.getWorldQuaternion(worldQuat);

                const sphere = new THREE.Mesh(new THREE.SphereGeometry(0.10, 8, 8), sphereMat);
                sphere.position.copy(worldPos);
                sphere.renderOrder = 998;
                sphere.userData['nodeId'] = node.id;

                const axis      = (node.metadata['axis'] as string) ?? 'y';
                const localAxis = ({ x: new THREE.Vector3(1,0,0), y: new THREE.Vector3(0,1,0), z: new THREE.Vector3(0,0,1) })[axis]!;
                const worldAxis = localAxis.clone().applyQuaternion(worldQuat).multiplyScalar(0.45);

                const lineGeo = new THREE.BufferGeometry().setFromPoints([
                    worldPos.clone().sub(worldAxis),
                    worldPos.clone().add(worldAxis),
                ]);
                const line = new THREE.Line(
                    lineGeo,
                    new THREE.LineBasicMaterial({ color: axisColors[axis] ?? 0xffffff, depthTest: false }),
                );
                line.renderOrder = 998;
                line.userData['nodeId'] = node.id;

                this.jointMarkersGroup.add(sphere, line);
            }
            for (const child of node.children) traverse(child);
        };
        traverse(this.sceneRootNode);
        this.jointMarkersGroup.visible = this.showJointMarkers;
    }
}
