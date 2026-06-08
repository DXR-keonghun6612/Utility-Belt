import { SceneNode } from './SceneNode';
import { NodeAssembler, AnchorLayout, NodeDescriptor } from './NodeAssembler';
import { NodeRegistry } from './NodeRegistry';

type ModelLoader = (name: string) => NodeDescriptor | Promise<NodeDescriptor>;

export class AnchorPopulator {
    /**
     * ANCHOR 노드에 자식이 없고 defaultModel/defaultNode가 있을 때 최초 populate.
     * 기존 자식은 모두 제거 후 재생성한다.
     */
    static async populate(anchor: SceneNode, modelLoader: ModelLoader): Promise<void> {
        const layout = anchor.metadata['_layoutDescriptor'] as AnchorLayout | null;
        if (!layout || !this._hasDefaultSource(layout)) return;

        this._clearChildren(anchor);
        await this._buildSlots(anchor, layout, modelLoader);
    }

    /**
     * Re-randomize: layout.slots[i].locked === true 슬롯은 기존 자식을 유지하고
     * 나머지 슬롯만 재생성한다.
     */
    static async repopulate(anchor: SceneNode, modelLoader: ModelLoader): Promise<void> {
        const layout = anchor.metadata['_layoutDescriptor'] as AnchorLayout | null;
        if (!layout || !this._hasDefaultSource(layout)) return;

        const count = layout.kind === 'array' ? Number(layout.count ?? 1) : 1;

        // 슬롯 인덱스 → 기존 자식 노드 매핑 (locked 슬롯만 보존)
        const lockedByIndex = new Map<number, SceneNode>();
        for (const child of anchor.children) {
            const idx = child.metadata['_slotIndex'] as number | undefined;
            if (idx !== undefined && layout.slots?.[idx]?.locked) {
                lockedByIndex.set(idx, child);
            }
        }

        // locked 가 아닌 자식 전체 제거
        for (const child of [...anchor.children]) {
            const idx = child.metadata['_slotIndex'] as number | undefined;
            if (idx === undefined || !lockedByIndex.has(idx)) {
                for (const n of child.flatten()) NodeRegistry.unregister(n);
                anchor.removeChild(child);
            }
        }

        await this._buildSlots(anchor, layout, modelLoader, lockedByIndex, count);
    }

    // ── 내부 ────────────────────────────────────────────────

    private static async _buildSlots(
        anchor: SceneNode,
        layout: AnchorLayout,
        modelLoader: ModelLoader,
        lockedByIndex?: Map<number, SceneNode>,
        count?: number,
    ): Promise<void> {
        const slotCount = count ?? (layout.kind === 'array' ? Number(layout.count ?? 1) : 1);
        const gap       = Number(layout.gap ?? 2.0);
        const start     = Number(layout.start ?? 0);
        const axis      = layout.axis ?? 'x';
        const axisIdx   = axis === 'x' ? 0 : (axis === 'y' ? 1 : 2);

        for (let i = 0; i < slotCount; i++) {
            // locked 슬롯: 기존 노드를 순서에 맞게 다시 붙인다
            if (lockedByIndex?.has(i)) {
                anchor.addChild(lockedByIndex.get(i)!);
                continue;
            }

            const slotCfg   = layout.slots?.[i];
            const modelName = slotCfg?.model ?? layout.defaultModel;
            const descriptor = modelName
                ? await modelLoader(modelName)
                : layout.defaultNode!;
            const instanceId = `${anchor.id}_s${i}_${(Math.random() * 0xfffff | 0).toString(16)}`;
            const child      = NodeAssembler.load(descriptor, instanceId);

            if (modelName) child.metadata['_modelName'] = modelName;
            child.metadata['_slotIndex'] = i;

            // 슬롯 기본 위치 (배열 offset)
            const basePos: [number, number, number] = [0, 0, 0];
            basePos[axisIdx] = start + i * gap;

            if (slotCfg?.transform) {
                // 명시된 transform이 있으면 그대로 사용 (position은 basePos 기준 상대)
                const p = slotCfg.transform.position ?? basePos;
                const r = slotCfg.transform.rotation ?? [0, 0, 0];
                child.object3D.position.set(...p);
                child.object3D.rotation.set(...r);
            } else {
                // randomize 적용
                const pos: [number, number, number] = [...basePos];
                const rot: [number, number, number] = [0, 0, 0];
                if (layout.randomize) this._applyRandomize(pos, rot, basePos, layout.randomize);
                child.object3D.position.set(...pos);
                child.object3D.rotation.set(...rot);
            }

            anchor.addChild(child);
        }
    }

    private static _applyRandomize(
        pos: [number, number, number],
        rot: [number, number, number],
        basePos: [number, number, number],
        randomize: NonNullable<AnchorLayout['randomize']>,
    ): void {
        for (const comp of randomize.components) {
            const range = randomize.ranges[comp];
            if (!range) continue;
            const val = range[0] + Math.random() * (range[1] - range[0]);
            switch (comp) {
                case 'px': pos[0] = basePos[0] + val; break;
                case 'py': pos[1] = basePos[1] + val; break;
                case 'pz': pos[2] = basePos[2] + val; break;
                case 'rx': rot[0] = val; break;
                case 'ry': rot[1] = val; break;
                case 'rz': rot[2] = val; break;
            }
        }
    }

    private static _clearChildren(anchor: SceneNode): void {
        for (const child of [...anchor.children]) {
            for (const n of child.flatten()) NodeRegistry.unregister(n);
            anchor.removeChild(child);
        }
    }

    private static _hasDefaultSource(layout: AnchorLayout): boolean {
        return !!(layout.defaultModel || layout.defaultNode);
    }
}
