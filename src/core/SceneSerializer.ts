import { SceneNode, NodeType } from './SceneNode';
import { SceneSnapshot, SceneEntry } from './NodeAssembler';

export class SceneSerializer {
    /**
     * scene root SceneNode를 SceneSnapshot JSON으로 직렬화한다.
     */
    static serialize(sceneRoot: SceneNode): SceneSnapshot {
        return {
            version: 1,
            scene: sceneRoot.children
                .filter(c => c.metadata._modelName !== undefined)
                .map(root => this._serializeEntry(root, undefined)),
        };
    }

    private static _serializeEntry(modelRoot: SceneNode, attachTo: string | undefined): SceneEntry {
        const entry: SceneEntry = {
            model: String(modelRoot.metadata._modelName ?? modelRoot.id),
            instanceId: modelRoot.id,
            transform: {
                position: [
                    modelRoot.object3D.position.x,
                    modelRoot.object3D.position.y,
                    modelRoot.object3D.position.z,
                ],
                rotation: [
                    modelRoot.object3D.rotation.x,
                    modelRoot.object3D.rotation.y,
                    modelRoot.object3D.rotation.z,
                ],
            },
        };

        if (attachTo !== undefined) entry.attachTo = attachTo;

        // JOINT 노드 중 기본값에서 변경된 것만 overrides로 기록
        const overrides: NonNullable<SceneEntry['overrides']> = {};
        
        // 해당 모델 루트로부터 시작하되, 다른 모델 루트(_modelName이 있는 노드)를 만나면 그 하위는 무시
        const traverseForOverrides = (n: SceneNode) => {
            if (n !== modelRoot && n.metadata._modelName !== undefined) return;

            if (n !== modelRoot && n.type === NodeType.JOINT) {
                const dr = (n.metadata._defaultRotation as [number, number, number]) ?? [0, 0, 0];
                const cr: [number, number, number] = [
                    n.object3D.rotation.x,
                    n.object3D.rotation.y,
                    n.object3D.rotation.z,
                ];
                if (cr.some((v, i) => Math.abs(v - dr[i]) > 1e-6)) {
                    overrides[n.id] = { rotation: cr };
                }
            }

            for (const child of n.children) {
                traverseForOverrides(child);
            }
        };
        traverseForOverrides(modelRoot);
        
        if (Object.keys(overrides).length > 0) entry.overrides = overrides;

        // 직계 자식 모델 루트들만 수집
        const childEntries: SceneEntry[] = [];
        
        const traverseForChildren = (n: SceneNode) => {
            // 다른 모델 루트를 만나면, 해당 노드는 현재 모델의 '자식 모델'로 기록하고 더 이상 내려가지 않음
            if (n !== modelRoot && n.metadata._modelName !== undefined) {
                childEntries.push(this._serializeEntry(n, n.parent?.id));
                return;
            }

            for (const child of n.children) {
                traverseForChildren(child);
            }
        };
        traverseForChildren(modelRoot);

        if (childEntries.length > 0) entry.children = childEntries;

        return entry;
    }
}
