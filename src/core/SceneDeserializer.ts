import * as THREE from 'three';
import { NodeAssembler, NodeDescriptor, SceneSnapshot, SceneEntry } from './NodeAssembler';
import { NodeRegistry } from './NodeRegistry';
import { SceneNode, NodeType } from './SceneNode';

/** 모델 이름 → NodeDescriptor 반환. 동기/비동기 모두 허용 */
export type ModelLoader = (name: string) => NodeDescriptor | Promise<NodeDescriptor>;

export class SceneDeserializer {
    /**
     * SceneSnapshot을 읽어 single scene root SceneNode를 반환한다.
     * 모든 최상위 모델은 이 root의 children으로 붙는다.
     */
    static async load(snapshot: SceneSnapshot, modelLoader: ModelLoader): Promise<SceneNode> {
        const sceneGroup = new THREE.Group();
        const sceneRoot = new SceneNode('scene', 'Scene', NodeType.GROUP, sceneGroup);
        NodeRegistry.register(sceneRoot);

        for (const entry of snapshot.scene) {
            const modelRoot = await this._loadEntry(entry, modelLoader);
            sceneRoot.addChild(modelRoot);
        }

        return sceneRoot;
    }

    private static async _loadEntry(
        entry: SceneEntry,
        modelLoader: ModelLoader,
    ): Promise<SceneNode> {
        const descriptor = await modelLoader(entry.model);
        const root = NodeAssembler.load(descriptor, entry.instanceId);

        // 모델 출처 기록 — SceneSerializer가 역직렬화에 사용
        root.metadata._modelName = entry.model;

        // 씬 레벨 transform (모델 JSON의 루트 transform을 덮어씀)
        if (entry.transform) {
            const { position, rotation } = entry.transform;
            if (position) root.object3D.position.set(...position);
            if (rotation) root.object3D.rotation.set(...rotation);
        }

        // 런타임 상태 overrides (조인트 각도 등)
        if (entry.overrides) {
            NodeAssembler.applyOverrides(entry.overrides);
        }

        // 자식 모델 인스턴스 재귀 처리
        for (const childEntry of entry.children ?? []) {
            const childRoot = await this._loadEntry(childEntry, modelLoader);

            if (childEntry.attachTo) {
                const attachNode = NodeRegistry.get(childEntry.attachTo);
                if (attachNode) {
                    attachNode.addChild(childRoot);
                } else {
                    console.warn(
                        `SceneDeserializer: attachTo "${childEntry.attachTo}" not found — attaching to parent root`,
                    );
                    root.addChild(childRoot);
                }
            } else {
                root.addChild(childRoot);
            }
        }

        return root;
    }
}
