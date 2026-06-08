import { SceneNode, NodeType } from './SceneNode';
import { NodeDescriptor } from './NodeAssembler';

/**
 * SceneNode 트리를 NodeDescriptor JSON으로 직렬화한다.
 * 에셋 에디터 전용 — 모델 인스턴스(_modelName) 경계를 무시하고 전체 트리를 하나의 모델로 내보낸다.
 */
export class NodeDescriptorExporter {
    static export(root: SceneNode): NodeDescriptor {
        const exportId = root.label || root.id;
        return this._serialize(root, root.id, exportId);
    }

    private static _serialize(
        node: SceneNode,
        draftRootId: string,
        exportRootId: string,
    ): NodeDescriptor {
        // "draft.j1.body" → "my_robot.j1.body"
        const id = node.id === draftRootId
            ? exportRootId
            : exportRootId + node.id.slice(draftRootId.length);

        const pos = node.object3D.position;
        const rot = node.object3D.rotation;

        const descriptor: NodeDescriptor = {
            id,
            type: node.type,
            label: node.label,
            transform: {
                position: [
                    parseFloat(pos.x.toFixed(5)),
                    parseFloat(pos.y.toFixed(5)),
                    parseFloat(pos.z.toFixed(5)),
                ],
                rotation: [
                    parseFloat(rot.x.toFixed(5)),
                    parseFloat(rot.y.toFixed(5)),
                    parseFloat(rot.z.toFixed(5)),
                ],
            },
        };

        if (node.id === draftRootId && node.metadata['_parametersDescriptor']) {
            descriptor.parameters = node.metadata['_parametersDescriptor'] as any;
        }
        if (node.id === draftRootId && node.metadata['_computedDescriptor']) {
            descriptor.computed = node.metadata['_computedDescriptor'] as any;
        }

        if (node.type === NodeType.LINK) {
            const geo = node.metadata['_geometryDescriptor'];
            if (geo) descriptor.geometry = geo as any;
        } else if (node.type === NodeType.ANCHOR) {
            const layout = node.metadata['_sourceLayoutDescriptor'] ?? node.metadata['_layoutDescriptor'];
            if (layout) descriptor.layout = layout as any;
        }

        // JOINT kinematic metadata
        if (node.type === NodeType.JOINT) {
            const meta: Record<string, unknown> = {};
            if (node.metadata['axis'] !== undefined)  meta['axis'] = node.metadata['axis'];
            if (node.metadata['min']  !== undefined)  meta['min']  = node.metadata['min'];
            if (node.metadata['max']  !== undefined)  meta['max']  = node.metadata['max'];
            if (Object.keys(meta).length > 0) descriptor.metadata = meta;
        }

        const children = node.children.map(c =>
            this._serialize(c, draftRootId, exportRootId),
        );
        if (children.length > 0) descriptor.children = children;

        return descriptor;
    }
}
