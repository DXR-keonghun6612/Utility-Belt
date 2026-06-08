import * as THREE from 'three';

import { SceneNode, NodeType } from '../../core/SceneNode';
import { NodeRegistry } from '../../core/NodeRegistry';
import { ViewportBase } from '../shared/ViewportBase';

export class SceneViewport extends ViewportBase {
    constructor(
        container: HTMLElement,
        callbacks: {
            onNodeSelected: (nodeId: string | null) => void;
            onGizmoDragEnd: (nodeId: string, pos: THREE.Vector3, rot: THREE.Euler) => void;
        },
    ) {
        super(container, callbacks, {
            bgColor:        '#f4f6f9',
            cameraFov:      35,
            cameraPosition: [0, 10, 40],
            orbitTarget:    [0, 5, 0],
            gridSize:       150,
            gridDivisions:  150,
            gridColor:      0x000000,
            gridOpacity:    0.05,
            gridOffsetY:    -0.25,
        });
        this._addFloor();
    }

    // ── Public API ────────────────────────────────────────────────

    setSceneRoot(rootObj: THREE.Object3D, rootNode: SceneNode): void {
        this.setScene(rootObj, rootNode);
    }

    // ── ViewportBase override ─────────────────────────────────────

    /** 씬 에디터: GROUP / ANCHOR 노드만 선택 가능, snap 없음 */
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
        raycaster.setFromCamera(mouse, this.camera);

        for (const hit of raycaster.intersectObjects(targets, true)) {
            let obj: THREE.Object3D | null = hit.object;
            while (obj) {
                const nodeId = obj.userData['nodeId'] as string | undefined;
                if (nodeId) {
                    const node = NodeRegistry.get(nodeId);
                    if (node && (node.type === NodeType.GROUP || node.type === NodeType.ANCHOR)) {
                        this._selectNode(nodeId);
                        return;
                    }
                }
                obj = obj.parent;
            }
        }
        this._selectNode(null);
    }

    // ── Private ───────────────────────────────────────────────────

    private _addFloor(): void {
        const floor = new THREE.Mesh(
            new THREE.PlaneGeometry(150, 150),
            new THREE.MeshStandardMaterial({ color: '#ffffff', depthWrite: false }),
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -0.3;
        floor.receiveShadow = true;
        this.scene.add(floor);
    }
}
