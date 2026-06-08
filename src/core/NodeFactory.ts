import * as THREE from 'three';
import { CADUtils } from './CADUtils';
import { NodeRegistry } from './NodeRegistry';
import type { AnchorLayout } from './NodeAssembler';

export interface GeometryDescriptor {
    shape: string;
    color?: string;
    [key: string]: unknown;
}

export class NodeFactory {
    /**
     * 기존 Group의 메쉬 자식들을 새 shape descriptor로 교체한다.
     * userData.nodeId 가 있는 자식(= 자식 SceneNode)은 건드리지 않는다.
     * 레이아웃은 별도 메서드(applyLayout)에서 처리한다.
     */
    static rebuildInPlace(group: THREE.Group, descriptor: GeometryDescriptor | null | undefined): void {
        // 1. 기존 메쉬 제거 + dispose
        [...group.children]
            .filter(c => !c.userData['nodeId'])
            .forEach(c => {
                group.remove(c);
                c.traverse(child => {
                    if (child instanceof THREE.Mesh) {
                        child.geometry.dispose();
                        const mats = Array.isArray(child.material) ? child.material : [child.material];
                        mats.forEach(m => (m as THREE.Material).dispose());
                    }
                });
            });

        // 2. 새 메쉬 추가
        const newGroup = this.build(descriptor);
        [...newGroup.children].forEach(c => group.add(c));
    }

    static build(descriptor: GeometryDescriptor | null | undefined): THREE.Group {
        if (!descriptor) return new THREE.Group();

        const { shape, color = '#cccccc', opacity = 1, ...params } = descriptor;
        const op = opacity as number;

        switch (shape) {
            case 'Box': {
                const bw = params.width  as number ?? 1;
                const bh = params.height as number ?? 1;
                const bd = params.depth  as number ?? 1;
                const geo = new THREE.BoxGeometry(bw, bh, bd);
                geo.translate(0, bh / 2, 0); // 바닥면이 원점
                const group = new THREE.Group();
                group.add(CADUtils.createMesh(geo, color, null, op));
                return group;
            }
            case 'Cylinder': {
                const ch = params.height as number ?? 1;
                const geo = new THREE.CylinderGeometry(
                    params.radiusTop    as number ?? 0.5,
                    params.radiusBottom as number ?? 0.5,
                    ch,
                    32,
                );
                geo.translate(0, ch / 2, 0); // 바닥면이 원점
                const group = new THREE.Group();
                group.add(CADUtils.createMesh(geo, color, null, op));
                return group;
            }
            case 'Sphere': {
                const geo = new THREE.SphereGeometry(params.radius as number ?? 0.5, 32, 16);
                const group = new THREE.Group();
                group.add(CADUtils.createMesh(geo, color, null, op));
                return group;
            }
            case 'Capsule':
                return CADUtils.createCapsule(
                    params.radius as number ?? 0.3,
                    params.length as number ?? 1,
                    color,
                    op,
                );
            case 'JointCapsule':
                return CADUtils.createJointCapsule(
                    params.radius    as number ?? 0.3,
                    params.length    as number ?? 1,
                    params.bodyColor as string ?? color,
                    params.capColor  as string ?? '#00bcd4',
                    op,
                );
            case 'Elbow':
                return CADUtils.createElbow(
                    color,
                    op,
                    params.pathRadius  as number ?? 1.2,
                    params.outerRadius as number ?? 0.6,
                    params.innerRadius as number ?? 0.45
                );
            case 'ConveyorBody':
                return CADUtils.buildConveyorBody(params.length as number ?? 10);
            default:
                console.warn(`NodeFactory: unknown shape "${shape}", returning empty Group`);
                return new THREE.Group();
        }
    }

    static getSnapPoints(descriptor: GeometryDescriptor): THREE.Vector3[] {
        const { shape } = descriptor;
        switch (shape) {
            case 'Box': {
                const bw = (descriptor['width']  as number) ?? 1;
                const bh = (descriptor['height'] as number) ?? 1;
                const bd = (descriptor['depth']  as number) ?? 1;
                const hw = bw / 2, hd = bd / 2;
                // geo.translate(0, bh/2, 0) → bottom at y=0, top at y=bh
                return [
                    new THREE.Vector3(0,   0,      0),    // bottom face
                    new THREE.Vector3(0,   bh,     0),    // top face
                    new THREE.Vector3(-hw, bh / 2, 0),    // left face
                    new THREE.Vector3(hw,  bh / 2, 0),    // right face
                    new THREE.Vector3(0,   bh / 2, -hd),  // back face
                    new THREE.Vector3(0,   bh / 2,  hd),  // front face
                    new THREE.Vector3(0,   bh / 2,  0),   // center
                    // bottom edge midpoints
                    new THREE.Vector3(0,   0, -hd),
                    new THREE.Vector3(hw,  0,   0),
                    new THREE.Vector3(0,   0,  hd),
                    new THREE.Vector3(-hw, 0,   0),
                    // top edge midpoints
                    new THREE.Vector3(0,   bh, -hd),
                    new THREE.Vector3(hw,  bh,   0),
                    new THREE.Vector3(0,   bh,  hd),
                    new THREE.Vector3(-hw, bh,   0),
                    // vertical edge midpoints
                    new THREE.Vector3(-hw, bh / 2, -hd),
                    new THREE.Vector3( hw, bh / 2, -hd),
                    new THREE.Vector3( hw, bh / 2,  hd),
                    new THREE.Vector3(-hw, bh / 2,  hd),
                ];
            }
            case 'Cylinder': {
                const ch = (descriptor['height'] as number) ?? 1;
                // geo.translate(0, ch/2, 0) → bottom at y=0, top at y=ch
                return [
                    new THREE.Vector3(0, 0,      0),
                    new THREE.Vector3(0, ch,     0),
                    new THREE.Vector3(0, ch / 2, 0),
                ];
            }
            case 'Sphere':
                return [new THREE.Vector3(0, 0, 0)];
            case 'Capsule': {
                const len = (descriptor['length'] as number) ?? 1;
                // createCapsule: centered at y=0
                return [
                    new THREE.Vector3(0,  len / 2, 0),
                    new THREE.Vector3(0, -len / 2, 0),
                    new THREE.Vector3(0,  0,       0),
                ];
            }
            case 'JointCapsule': {
                const len = (descriptor['length'] as number) ?? 1;
                return [
                    new THREE.Vector3(0,  len / 2, 0),
                    new THREE.Vector3(0, -len / 2, 0),
                    new THREE.Vector3(0,  0,       0),
                ];
            }
            case 'Elbow': {
                const pathRadius  = (descriptor['pathRadius']  as number) ?? 1.2;
                const outerRadius = (descriptor['outerRadius'] as number) ?? 0.6;
                const comOffset   = (2 * pathRadius) / Math.PI;
                return [
                    new THREE.Vector3(
                         pathRadius - 3 * comOffset / 4,
                         outerRadius / 2,
                         3 * comOffset / 4,
                    ),
                    new THREE.Vector3(
                        -3 * comOffset / 4,
                         outerRadius / 2,
                        -pathRadius + 3 * comOffset / 4,
                    ),
                ];
            }
            default:
                return [new THREE.Vector3(0, 0, 0)];
        }
    }

    /**
     * ANCHOR 노드의 자식 SceneNode들을 layout에 따라 배치한다.
     * - 'single' : 자식들의 위치를 건드리지 않는다.
     * - 'array'  : 지정 축으로 count 만큼 일렬 배치, 초과분은 숨긴다.
     *   slots의 transform override는 AnchorPopulator가 적용하므로 여기서는 base offset만 처리.
     */
    static applyLayout(group: THREE.Group, layout: AnchorLayout | null | undefined): void {
        if (!layout || layout.kind === 'single') return;

        if (layout.kind === 'array') {
            const count  = Number(layout.count ?? 5);
            const gap    = Number(layout.gap   ?? 2.0);
            const start  = Number(layout.start ?? 0);
            const axis   = layout.axis  ?? 'x';
            const axisIdx = axis === 'x' ? 0 : (axis === 'y' ? 1 : 2);

            const nodeChildren = group.children.filter(c => c.userData['nodeId']);

            nodeChildren.forEach((child, i) => {
                const nodeId = child.userData['nodeId'];
                const node = typeof nodeId === 'string' ? NodeRegistry.get(nodeId) : null;
                const slotIndex = Number(node?.metadata['_slotIndex'] ?? i);

                if (slotIndex < count) {
                    child.visible = true;
                    const pos = [0, 0, 0];
                    pos[axisIdx] = start + slotIndex * gap;
                    child.position.set(pos[0], pos[1], pos[2]);
                } else {
                    child.visible = false;
                }
            });
        }
    }
}
