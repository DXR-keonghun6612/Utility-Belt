import * as THREE from 'three';
import { SceneNode, NodeType } from './SceneNode';
import { NodeFactory, GeometryDescriptor, LayoutDescriptor } from './NodeFactory';
import { NodeRegistry } from './NodeRegistry';

export interface NodeDescriptor {
    id: string;
    type: string;
    label?: string;
    /** LINK 전용 — 다른 타입에서는 무시된다. */
    geometry?: GeometryDescriptor | null;
    /** JOINT 전용 — 다른 타입에서는 무시된다. */
    layout?: LayoutDescriptor | null;
    transform?: {
        position?: [number, number, number];
        rotation?: [number, number, number];
    };
    metadata?: Record<string, unknown>;
    children?: NodeDescriptor[];
}

export interface SceneEntry {
    model: string;
    instanceId: string;
    attachTo?: string;
    transform?: {
        position?: [number, number, number];
        rotation?: [number, number, number];
    };
    overrides?: Record<string, {
        position?: [number, number, number];
        rotation?: [number, number, number];
    }>;
    children?: SceneEntry[];
}

export interface SceneSnapshot {
    version: number;
    scene: SceneEntry[];
}

export class NodeAssembler {
    /**
     * JSON descriptor 하나를 SceneNode 트리로 조립하여 루트 노드를 반환.
     * instanceId를 지정하면 모델 내부의 모든 노드 id가
     * "<model_root_id>.*" → "<instanceId>.*" 로 치환된다.
     */
    static load(descriptor: NodeDescriptor, instanceId?: string): SceneNode {
        const rootId = instanceId ?? descriptor.id;
        return this._build(descriptor, descriptor.id, rootId);
    }

    private static _build(
        desc: NodeDescriptor,
        modelRootId: string,
        instanceRootId: string,
    ): SceneNode {
        const nodeId = this._remapId(desc.id, modelRootId, instanceRootId);
        const type   = NodeType[desc.type as keyof typeof NodeType] ?? NodeType.LINK;

        // 타입별 object3D 생성 규칙:
        //   LINK  → geometry shape 빌드
        //   JOINT → 빈 컨테이너 (layout으로 자식 배치)
        //   GROUP → 빈 컨테이너 (geometry/layout 모두 무시)
        const object3D = type === NodeType.LINK
            ? NodeFactory.build(desc.geometry ?? null)
            : new THREE.Group();

        const label = desc.label ?? nodeId;
        const node  = new SceneNode(nodeId, label, type, object3D);

        if (desc.metadata) node.metadata = { ...desc.metadata };

        if (desc.transform) {
            const { position, rotation } = desc.transform;
            if (position) object3D.position.set(...position);
            if (rotation) object3D.rotation.set(...rotation);
        }
        // Store defaults so SceneSerializer can detect runtime changes
        node.metadata._defaultRotation = desc.transform?.rotation ?? [0, 0, 0];
        node.metadata._defaultPosition = desc.transform?.position ?? [0, 0, 0];

        // 타입에 따라 적절한 디스크립터만 보존한다.
        if (type === NodeType.LINK) {
            node.metadata._geometryDescriptor = desc.geometry ?? null;
        } else if (type === NodeType.JOINT) {
            node.metadata._layoutDescriptor = desc.layout ?? { kind: 'single' };
        }

        NodeRegistry.register(node);

        for (const childDesc of desc.children ?? []) {
            const child = this._build(childDesc, modelRootId, instanceRootId);
            node.addChild(child);
        }

        // JOINT만 자식 배치 적용 (자식이 모두 붙은 뒤)
        if (type === NodeType.JOINT) {
            NodeFactory.applyLayout(
                node.object3D,
                node.metadata._layoutDescriptor as LayoutDescriptor | null,
            );
        }

        return node;
    }

    /** "<modelRootId>" 또는 "<modelRootId>.X.Y" 패턴을 instanceRootId 기준으로 치환 */
    private static _remapId(id: string, modelRootId: string, instanceRootId: string): string {
        if (id === modelRootId) return instanceRootId;
        if (id.startsWith(modelRootId + '.')) {
            return instanceRootId + id.slice(modelRootId.length);
        }
        // 규칙을 따르지 않는 ID인 경우에도 충돌 방지를 위해 인스턴스 ID를 접두어로 추가
        return `${instanceRootId}.${id}`;
    }

    /**
     * 씬 스냅샷의 overrides를 기존 SceneNode 트리에 적용한다.
     * overrides key는 instanceId 기준 노드 id (e.g. "robot_0.j1")
     */
    static applyOverrides(
        overrides: Record<string, {
            position?: [number, number, number];
            rotation?: [number, number, number];
        }>,
    ): void {
        for (const [id, transform] of Object.entries(overrides)) {
            const node = NodeRegistry.get(id);
            if (!node) {
                console.warn(`NodeAssembler.applyOverrides: node "${id}" not found`);
                continue;
            }
            if (transform.position) node.object3D.position.set(...transform.position);
            if (transform.rotation) node.object3D.rotation.set(...transform.rotation);
        }
    }
}
