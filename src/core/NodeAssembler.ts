import * as THREE from 'three';
import { SceneNode, NodeType } from './SceneNode';
import { NodeFactory, GeometryDescriptor } from './NodeFactory';
import { NodeRegistry } from './NodeRegistry';

export interface SlotConfig {
    model?: string;
    transform?: {
        position?: [number, number, number];
        rotation?: [number, number, number];
    };
    locked?: boolean;
}

export interface AnchorLayout {
    kind: 'single' | 'array';
    exposed?: boolean;
    count?: number | string;
    gap?: number | string;
    start?: number | string;
    axis?: 'x' | 'y' | 'z';
    defaultModel?: string;
    defaultNode?: NodeDescriptor;
    randomize?: {
        components: ('px' | 'py' | 'pz' | 'rx' | 'ry' | 'rz')[];
        ranges: Partial<Record<'px' | 'py' | 'pz' | 'rx' | 'ry' | 'rz', [number, number]>>;
    };
    slots?: Record<number, SlotConfig>;
}

export type InstanceParams = Record<string, unknown>;

export interface ParameterDescriptor {
    type: 'number' | 'integer' | 'string' | 'boolean';
    default: unknown;
    label?: string;
    min?: number;
    max?: number;
    step?: number;
    unit?: string;
}

export type ParameterSchema = Record<string, ParameterDescriptor>;
export type ComputedSchema = Record<string, number | string>;

export interface AnchorInstanceOverride {
    layout?: AnchorLayout;
    params?: InstanceParams;
}

export interface SceneInstanceState {
    params?: InstanceParams;
    anchorOverrides?: Record<string, AnchorInstanceOverride>;
}

export interface NodeTransform {
    position?: [number, number, number];
    rotation?: [number, number, number];
}

export interface InstanceBuildOptions {
    modelName?: string;
    state?: SceneInstanceState;
    transform?: NodeTransform;
}

export interface NodeDescriptor {
    id: string;
    type: string;
    label?: string;
    parameters?: ParameterSchema;
    computed?: ComputedSchema;
    definitions?: Record<string, NodeDescriptor>;
    /** LINK 전용 */
    geometry?: GeometryDescriptor | null;
    /** ANCHOR 전용 */
    layout?: AnchorLayout | null;
    transform?: NodeTransform;
    metadata?: Record<string, unknown>;
    children?: Array<NodeDescriptor | string>;
}

export interface SceneEntry {
    model: string;
    instanceId: string;
    attachTo?: string;
    slotIndex?: number;
    params?: InstanceParams;
    anchorOverrides?: Record<string, AnchorInstanceOverride>;
    transform?: NodeTransform;
    overrides?: Record<string, NodeTransform>;
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
        const resolved = this._resolveDescriptor(descriptor);
        const rootId = instanceId ?? descriptor.id;
        return this._build(
            resolved,
            descriptor.id,
            rootId,
            descriptor,
            resolved.definitions ?? {},
            descriptor.definitions ?? {},
        );
    }

    static loadInstance(
        descriptor: NodeDescriptor,
        instanceId: string,
        state?: SceneInstanceState,
    ): SceneNode {
        return this.materializeInstance(descriptor, instanceId, { state });
    }

    static materializeInstance(
        descriptor: NodeDescriptor,
        instanceId: string,
        options: InstanceBuildOptions = {},
    ): SceneNode {
        const resolved = this._resolveDescriptor(descriptor, options.state);
        const root = this._build(
            resolved,
            descriptor.id,
            instanceId,
            descriptor,
            resolved.definitions ?? {},
            descriptor.definitions ?? {},
        );
        if (options.modelName) root.metadata._modelName = options.modelName;
        if (options.transform) this._applyTransform(root, options.transform);
        this.applyInstanceState(root, options.state);
        return root;
    }

    static applyInstanceState(root: SceneNode, state?: SceneInstanceState): void {
        const clonedState = this._cloneInstanceState(state);
        root.metadata._instanceState = clonedState;
        this._applyAnchorOverrides(clonedState.anchorOverrides);
    }

    static readInstanceState(root: SceneNode): SceneInstanceState {
        return this._cloneInstanceState(root.metadata._instanceState as SceneInstanceState | undefined);
    }

    static updateInstanceState(root: SceneNode, patch: SceneInstanceState): SceneInstanceState {
        const current = this.readInstanceState(root);
        const next: SceneInstanceState = {
            params: {
                ...(current.params ?? {}),
                ...(patch.params ?? {}),
            },
            anchorOverrides: {
                ...(current.anchorOverrides ?? {}),
                ...(patch.anchorOverrides ?? {}),
            },
        };

        if (Object.keys(next.params ?? {}).length === 0) delete next.params;
        if (Object.keys(next.anchorOverrides ?? {}).length === 0) delete next.anchorOverrides;

        this.applyInstanceState(root, next);
        return this.readInstanceState(root);
    }

    static rebuildInstance(
        currentRoot: SceneNode,
        descriptor: NodeDescriptor,
        state?: SceneInstanceState,
    ): SceneNode {
        const parent = currentRoot.parent;
        const index = parent ? parent.children.indexOf(currentRoot) : -1;
        const modelName = String(currentRoot.metadata._modelName ?? descriptor.id);
        const transform = this._readTransform(currentRoot);
        const attachedInstances = this._detachAttachedInstances(currentRoot);

        for (const node of currentRoot.flatten()) {
            NodeRegistry.unregister(node);
        }
        if (parent) parent.removeChild(currentRoot);

        const nextRoot = this.materializeInstance(descriptor, currentRoot.id, {
            modelName,
            state,
            transform,
        });

        if (parent) {
            if (index >= 0) {
                this._insertChildAt(parent, nextRoot, index);
            } else {
                parent.addChild(nextRoot);
            }
        }

        for (const item of attachedInstances) {
            const attachNode = NodeRegistry.get(item.attachTo) ?? nextRoot;
            attachNode.addChild(item.node);
        }

        return nextRoot;
    }

    private static _build(
        desc: NodeDescriptor,
        modelRootId: string,
        instanceRootId: string,
        sourceDesc: NodeDescriptor = desc,
        definitions: Record<string, NodeDescriptor> = {},
        sourceDefinitions: Record<string, NodeDescriptor> = definitions,
        resolving: Set<string> = new Set(),
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
        if (sourceDesc.parameters) node.metadata._parametersDescriptor = sourceDesc.parameters;
        if (sourceDesc.computed) node.metadata._computedDescriptor = sourceDesc.computed;

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
            node.metadata._geometryDescriptor = sourceDesc.geometry ?? desc.geometry ?? null;
        } else if (type === NodeType.ANCHOR) {
            node.metadata._layoutDescriptor = desc.layout ?? { kind: 'single' };
            node.metadata._sourceLayoutDescriptor = sourceDesc.layout ?? desc.layout ?? { kind: 'single' };
        }

        NodeRegistry.register(node);

        for (const [index, childRef] of (desc.children ?? []).entries()) {
            const refKey = typeof childRef === 'string' ? childRef : null;
            if (refKey) {
                if (resolving.has(refKey)) {
                    throw new Error(`NodeAssembler: circular definition reference "${refKey}"`);
                }
                resolving.add(refKey);
            }

            const childDesc = this._resolveChildRef(childRef, definitions);
            const sourceRef = sourceDesc.children?.[index] ?? childRef;
            const sourceChildDesc = this._resolveChildRef(sourceRef, sourceDefinitions);
            const child = this._build(
                childDesc,
                modelRootId,
                instanceRootId,
                sourceChildDesc,
                definitions,
                sourceDefinitions,
                resolving,
            );
            node.addChild(child);

            if (refKey) resolving.delete(refKey);
        }

        // ANCHOR만 자식 배치 적용 (자식이 모두 붙은 뒤)
        if (type === NodeType.ANCHOR) {
            NodeFactory.applyLayout(
                node.object3D,
                node.metadata._layoutDescriptor as AnchorLayout | null,
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

    private static _resolveChildRef(
        child: NodeDescriptor | string,
        definitions: Record<string, NodeDescriptor>,
    ): NodeDescriptor {
        if (typeof child !== 'string') return child;

        const descriptor = definitions[child];
        if (!descriptor) {
            throw new Error(`NodeAssembler: definition "${child}" not found`);
        }

        return descriptor;
    }

    /**
     * 씬 스냅샷의 overrides를 기존 SceneNode 트리에 적용한다.
     * overrides key는 instanceId 기준 노드 id (e.g. "robot_0.j1")
     */
    static applyOverrides(
        overrides: Record<string, NodeTransform>,
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

    private static _readTransform(node: SceneNode): Required<NodeTransform> {
        return {
            position: [
                node.object3D.position.x,
                node.object3D.position.y,
                node.object3D.position.z,
            ],
            rotation: [
                node.object3D.rotation.x,
                node.object3D.rotation.y,
                node.object3D.rotation.z,
            ],
        };
    }

    private static _applyTransform(node: SceneNode, transform: NodeTransform): void {
        if (transform.position) node.object3D.position.set(...transform.position);
        if (transform.rotation) node.object3D.rotation.set(...transform.rotation);
    }

    private static _insertChildAt(parent: SceneNode, child: SceneNode, index: number): void {
        child.parent = parent;
        parent.children.splice(index, 0, child);
        parent.object3D.add(child.object3D);
    }

    private static _detachAttachedInstances(root: SceneNode): { node: SceneNode; attachTo: string }[] {
        const attached: { node: SceneNode; attachTo: string }[] = [];

        const traverse = (node: SceneNode) => {
            for (const child of [...node.children]) {
                if (child.metadata._modelName !== undefined) {
                    const layout = node.metadata._layoutDescriptor as AnchorLayout | undefined;
                    if (node.type === NodeType.ANCHOR && layout?.exposed === false) {
                        for (const n of child.flatten()) NodeRegistry.unregister(n);
                        node.removeChild(child);
                        continue;
                    }

                    attached.push({ node: child, attachTo: node.id });
                    node.removeChild(child);
                    continue;
                }
                traverse(child);
            }
        };

        traverse(root);
        return attached;
    }

    private static _applyAnchorOverrides(
        anchorOverrides?: Record<string, AnchorInstanceOverride>,
    ): void {
        if (!anchorOverrides) return;

        for (const [anchorId, override] of Object.entries(anchorOverrides)) {
            const anchor = NodeRegistry.get(anchorId);
            if (!anchor || anchor.type !== NodeType.ANCHOR || !override.layout) continue;

            const layout = this._cloneAnchorLayout(override.layout);
            anchor.metadata._layoutDescriptor = layout;
            NodeFactory.applyLayout(anchor.object3D, layout);
        }
    }

    private static _cloneInstanceState(state?: SceneInstanceState): SceneInstanceState {
        if (!state) return {};

        const clone: SceneInstanceState = {};
        if (state.params && Object.keys(state.params).length > 0) {
            clone.params = { ...state.params };
        }
        if (state.anchorOverrides && Object.keys(state.anchorOverrides).length > 0) {
            clone.anchorOverrides = {};
            for (const [anchorId, override] of Object.entries(state.anchorOverrides)) {
                clone.anchorOverrides[anchorId] = {
                    ...override,
                    layout: override.layout ? this._cloneAnchorLayout(override.layout) : undefined,
                    params: override.params ? { ...override.params } : undefined,
                };
            }
        }
        return clone;
    }

    private static _cloneAnchorLayout(layout: AnchorLayout): AnchorLayout {
        const cloned: AnchorLayout = { ...layout };
        if (layout.randomize) {
            cloned.randomize = {
                components: [...layout.randomize.components],
                ranges: { ...layout.randomize.ranges },
            };
        }
        if (layout.slots) {
            cloned.slots = {};
            for (const [index, slot] of Object.entries(layout.slots)) {
                cloned.slots[Number(index)] = {
                    ...slot,
                    transform: slot.transform ? {
                        position: slot.transform.position ? [...slot.transform.position] : undefined,
                        rotation: slot.transform.rotation ? [...slot.transform.rotation] : undefined,
                    } : undefined,
                };
            }
        }
        return cloned;
    }

    private static _resolveDescriptor(
        descriptor: NodeDescriptor,
        state?: SceneInstanceState,
    ): NodeDescriptor {
        const params = this._resolveParams(descriptor.parameters, state?.params);
        const computed = this._resolveComputed(descriptor.computed, params);
        return this._resolveNodeDescriptor(descriptor, params, computed);
    }

    private static _resolveParams(
        schema?: ParameterSchema,
        instanceParams?: InstanceParams,
    ): InstanceParams {
        const params: InstanceParams = {};
        for (const [key, param] of Object.entries(schema ?? {})) {
            params[key] = instanceParams?.[key] ?? param.default;
        }
        return {
            ...params,
            ...(instanceParams ?? {}),
        };
    }

    private static _resolveNodeDescriptor(
        descriptor: NodeDescriptor,
        params: InstanceParams,
        computed: InstanceParams,
    ): NodeDescriptor {
        return {
            ...descriptor,
            parameters: descriptor.parameters,
            computed: descriptor.computed,
            geometry: descriptor.geometry
                ? this._resolveValue(descriptor.geometry, params, computed) as GeometryDescriptor
                : descriptor.geometry,
            layout: descriptor.layout
                ? this._resolveValue(descriptor.layout, params, computed) as AnchorLayout
                : descriptor.layout,
            transform: descriptor.transform
                ? this._resolveValue(descriptor.transform, params, computed) as NodeTransform
                : descriptor.transform,
            metadata: descriptor.metadata
                ? this._resolveValue(descriptor.metadata, params, computed) as Record<string, unknown>
                : descriptor.metadata,
            definitions: this._resolveDefinitions(descriptor.definitions, params, computed),
            children: descriptor.children?.map(child => typeof child === 'string'
                ? child
                : this._resolveNodeDescriptor(child, params, computed),
            ),
        };
    }

    private static _resolveDefinitions(
        definitions: Record<string, NodeDescriptor> | undefined,
        params: InstanceParams,
        computed: InstanceParams,
    ): Record<string, NodeDescriptor> | undefined {
        if (!definitions) return undefined;

        const resolved: Record<string, NodeDescriptor> = {};
        for (const [key, descriptor] of Object.entries(definitions)) {
            resolved[key] = this._resolveNodeDescriptor(descriptor, params, computed);
        }
        return resolved;
    }

    private static _resolveValue(value: unknown, params: InstanceParams, computed: InstanceParams): unknown {
        if (typeof value === 'string') {
            const match = /^\$(params|computed)\.([A-Za-z_][A-Za-z0-9_]*)$/.exec(value);
            if (match) {
                const scope = match[1] === 'params' ? params : computed;
                return scope[match[2]] ?? value;
            }
            return value;
        }

        if (Array.isArray(value)) {
            return value.map(item => this._resolveValue(item, params, computed));
        }

        if (value && typeof value === 'object') {
            const result: Record<string, unknown> = {};
            for (const [key, item] of Object.entries(value)) {
                result[key] = this._resolveValue(item, params, computed);
            }
            return result;
        }

        return value;
    }

    private static _resolveComputed(schema: ComputedSchema | undefined, params: InstanceParams): InstanceParams {
        const computed: InstanceParams = {};
        for (const [key, expression] of Object.entries(schema ?? {})) {
            computed[key] = typeof expression === 'number'
                ? expression
                : this._evaluateExpression(expression, { ...params, ...computed });
        }
        return computed;
    }

    private static _evaluateExpression(expression: string, scope: InstanceParams): number {
        if (!/^[0-9+\-*/().,\sA-Za-z_]+$/.test(expression)) {
            throw new Error(`Unsupported computed expression: ${expression}`);
        }

        const names = Object.keys(scope).filter(key => typeof scope[key] === 'number');
        const values = names.map(key => scope[key] as number);
        const fn = new Function(
            'floor',
            'ceil',
            'round',
            'min',
            'max',
            ...names,
            `return ${expression};`,
        ) as (...args: unknown[]) => number;
        const value = fn(Math.floor, Math.ceil, Math.round, Math.min, Math.max, ...values);
        return Number.isFinite(value) ? value : 0;
    }
}
