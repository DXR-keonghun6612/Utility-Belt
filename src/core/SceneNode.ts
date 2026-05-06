import * as THREE from 'three';

export enum NodeType {
    GROUP  = 'GROUP',
    ANCHOR = 'ANCHOR',
    JOINT  = 'JOINT',
    LINK   = 'LINK',
}

export class SceneNode {
    readonly id: string;
    label: string;
    type: NodeType;
    object3D: THREE.Group;
    parent: SceneNode | null = null;
    children: SceneNode[] = [];
    metadata: Record<string, unknown> = {};

    constructor(id: string, label: string, type: NodeType, object3D: THREE.Group) {
        this.id    = id;
        this.label = label;
        this.type  = type;
        this.object3D = object3D;
        object3D.userData['nodeId'] = id;
    }

    addChild(child: SceneNode): void {
        child.parent = this;
        this.children.push(child);
        this.object3D.add(child.object3D);
    }

    removeChild(child: SceneNode): void {
        this.children = this.children.filter(c => c !== child);
        this.object3D.remove(child.object3D);
        child.parent = null;
    }

    /** 자신을 포함한 전체 하위 노드를 DFS 순서로 반환 */
    flatten(): SceneNode[] {
        const result: SceneNode[] = [this];
        for (const child of this.children) {
            result.push(...child.flatten());
        }
        return result;
    }
}
