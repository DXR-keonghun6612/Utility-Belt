import * as THREE from 'three';
import { CADUtils } from './CADUtils';

export interface GeometryDescriptor {
    shape: string;
    color?: string;
    [key: string]: unknown;
}

export type LayoutKind = 'single' | 'array';

export interface LayoutDescriptor {
    kind: LayoutKind;
    count?: number;
    gap?: number;
    axis?: 'x' | 'y' | 'z';
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
                const geo = new THREE.BoxGeometry(
                    params.width  as number ?? 1,
                    params.height as number ?? 1,
                    params.depth  as number ?? 1,
                );
                const group = new THREE.Group();
                group.add(CADUtils.createMesh(geo, color, null, op));
                return group;
            }
            case 'Cylinder': {
                const geo = new THREE.CylinderGeometry(
                    params.radiusTop    as number ?? 0.5,
                    params.radiusBottom as number ?? 0.5,
                    params.height       as number ?? 1,
                    32,
                );
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
            case 'LegArray':
                return CADUtils.buildLegArray(
                    params.length as number ?? 10,
                    params.height as number ?? 4.15,
                    params.width  as number ?? 4.3,
                    params.gap    as number ?? 5,
                    color,
                    op
                );
            default:
                console.warn(`NodeFactory: unknown shape "${shape}", returning empty Group`);
                return new THREE.Group();
        }
    }

    /**
     * GROUP 노드의 자식 SceneNode들을 layout descriptor에 따라 배치한다.
     * - 'single' : 자식들의 위치를 건드리지 않는다(개별 transform 유지).
     * - 'array'  : 지정 축으로 count 만큼 일렬 배치, 초과분은 숨긴다.
     */
    static applyLayout(group: THREE.Group, layout: LayoutDescriptor | null | undefined): void {
        if (!layout || layout.kind === 'single') return;

        if (layout.kind === 'array') {
            const count = layout.count ?? 5;
            const gap   = layout.gap   ?? 2.0;
            const axis  = layout.axis  ?? 'x';

            const nodeChildren = group.children.filter(c => c.userData['nodeId']);
            const axisIdx = axis === 'x' ? 0 : (axis === 'y' ? 1 : 2);

            nodeChildren.forEach((child, i) => {
                if (i < count) {
                    child.visible = true;
                    const pos = [0, 0, 0];
                    pos[axisIdx] = i * gap;
                    child.position.set(pos[0], pos[1], pos[2]);
                } else {
                    child.visible = false;
                }
            });
        }
    }
}
