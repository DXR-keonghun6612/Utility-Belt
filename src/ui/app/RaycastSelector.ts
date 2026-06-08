import * as THREE from 'three';
import { SceneNode } from '../../core/SceneNode';
import { NodeRegistry } from '../../core/NodeRegistry';

export class RaycastSelector {
    private raycaster = new THREE.Raycaster();
    private pointer   = new THREE.Vector2();
    private scene: THREE.Scene;
    private camera: THREE.Camera;
    private renderer: THREE.WebGLRenderer;
    private onSelect: (node: SceneNode) => void;
    private _boundOnClick: (e: MouseEvent) => void;

    constructor(
        scene: THREE.Scene,
        camera: THREE.Camera,
        renderer: THREE.WebGLRenderer,
        onSelect: (node: SceneNode) => void,
    ) {
        this.scene          = scene;
        this.camera         = camera;
        this.renderer       = renderer;
        this.onSelect       = onSelect;
        this._boundOnClick  = this._onClick.bind(this);
        renderer.domElement.addEventListener('click', this._boundOnClick);
    }

    private _onClick(e: MouseEvent): void {
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.pointer.set(
            ((e.clientX - rect.left) / rect.width)  *  2 - 1,
            ((e.clientY - rect.top)  / rect.height) * -2 + 1,
        );
        this.raycaster.setFromCamera(this.pointer, this.camera);

        const intersects = this.raycaster.intersectObjects(this.scene.children, true);
        if (intersects.length === 0) return;

        // 교차된 mesh에서 위로 올라가며 nodeId를 가진 첫 번째 Group을 찾는다
        let obj: THREE.Object3D | null = intersects[0].object;
        while (obj) {
            const id = obj.userData['nodeId'] as string | undefined;
            if (id) {
                const node = NodeRegistry.get(id);
                if (node) {
                    this.onSelect(node);
                    return;
                }
            }
            obj = obj.parent;
        }
    }

    dispose(): void {
        this.renderer.domElement.removeEventListener('click', this._boundOnClick);
    }
}
