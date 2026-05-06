import { SceneNode, NodeType } from '../core/SceneNode';
import { AssetManager } from '../core/AssetManager';
import { AnchorLayout, NodeAssembler } from '../core/NodeAssembler';
import { AnchorPopulator } from '../core/AnchorPopulator';
import { NodeRegistry } from '../core/NodeRegistry';

type Axis = 'x' | 'y' | 'z';

export class InstancePanel {
    private container: HTMLElement;
    private assetManager: AssetManager;
    private onChanged?: () => void;

    constructor(container: HTMLElement, assetManager: AssetManager, onChanged?: () => void) {
        this.container   = container;
        this.assetManager = assetManager;
        this.onChanged   = onChanged;
    }

    show(node: SceneNode): void {
        this.container.innerHTML = '';
        const section = this._section('PROPERTIES');

        section.appendChild(this._propRow('id',    node.id));
        section.appendChild(this._propRow('type',  node.type));
        section.appendChild(this._propRow('label', node.label));
        section.appendChild(this._divider());

        switch (node.type) {
            case NodeType.GROUP:  this._renderTransform(section, node); break;
            case NodeType.ANCHOR: this._renderAnchor(section, node);    break;
            case NodeType.JOINT:  this._renderJoint(section, node);     break;
            case NodeType.LINK:   this._renderTransform(section, node); break;
        }

        this.container.appendChild(section);
    }

    clear(): void {
        this.container.innerHTML = '';
        const section = this._section('PROPERTIES');
        const empty = document.createElement('div');
        empty.style.cssText = 'color:#7a8494; padding:8px 0; font-size:11px;';
        empty.textContent = 'No node selected.';
        section.appendChild(empty);
        this.container.appendChild(section);
    }

    // ── 타입별 렌더 ──────────────────────────────────────

    private _renderAnchor(parent: HTMLElement, anchor: SceneNode): void {
        this._renderTransform(parent, anchor);

        const layout = anchor.metadata['_layoutDescriptor'] as AnchorLayout | null;
        if (!layout) return;

        parent.appendChild(this._divider());

        if (layout.kind === 'single') {
            this._renderAnchorSingle(parent, anchor);
        } else {
            this._renderAnchorArray(parent, anchor, layout);
        }
    }

    private _renderAnchorSingle(parent: HTMLElement, anchor: SceneNode): void {
        const title = document.createElement('div');
        title.className = 'panel-section-title';
        title.textContent = 'ATTACHED MODEL';
        title.style.marginTop = '10px';
        parent.appendChild(title);

        // Only count externally-attached models (have _modelName); ignore structural LINK children
        const child = anchor.children.find(c => c.metadata['_modelName'] !== undefined) ?? null;
        if (child) {
            const row = document.createElement('div');
            row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:4px 0; font-size:11px;';
            const name = document.createElement('span');
            name.textContent = String(child.metadata['_modelName'] ?? child.label);
            name.style.color = '#dde1e7';
            const detachBtn = document.createElement('button');
            detachBtn.className = 'preset-btn';
            detachBtn.style.cssText = 'flex:0; padding:3px 8px; font-size:10px; color:#ef9a9a; border-color:#ef9a9a;';
            detachBtn.textContent = 'Detach';
            detachBtn.addEventListener('click', () => {
                for (const n of child.flatten()) NodeRegistry.unregister(n);
                anchor.removeChild(child);
                this.onChanged?.();
                this.show(anchor);
            });
            row.appendChild(name);
            row.appendChild(detachBtn);
            parent.appendChild(row);
        } else {
            this._renderAttachForm(parent, anchor);
        }
    }

    private _renderAttachForm(parent: HTMLElement, anchor: SceneNode): void {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; gap:6px; align-items:center; margin-top:6px;';

        const models = this.assetManager.getAllModelNames();
        const sel = document.createElement('select');
        sel.className = 'builder-select';
        sel.style.flex = '1';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m; opt.textContent = m;
            sel.appendChild(opt);
        });

        const attachBtn = document.createElement('button');
        attachBtn.className = 'preset-btn primary';
        attachBtn.style.cssText = 'flex:0; padding:4px 10px; font-size:10px;';
        attachBtn.textContent = 'Attach';
        attachBtn.addEventListener('click', async () => {
            if (!sel.value) return;
            try {
                const descriptor = this.assetManager.getModel(sel.value);
                const instanceId  = `${anchor.id}_s0_${(Math.random() * 0xfffff | 0).toString(16)}`;
                const child       = NodeAssembler.load(descriptor, instanceId);
                child.metadata['_modelName'] = sel.value;
                child.metadata['_slotIndex'] = 0;
                anchor.addChild(child);
                this.onChanged?.();
                this.show(anchor);
            } catch (e) {
                alert((e as Error).message);
            }
        });

        row.appendChild(sel);
        row.appendChild(attachBtn);
        parent.appendChild(row);
    }

    private _renderAnchorArray(parent: HTMLElement, anchor: SceneNode, layout: AnchorLayout): void {
        const header = document.createElement('div');
        header.style.cssText = 'display:flex; justify-content:space-between; align-items:center; margin-top:10px;';
        const title = document.createElement('div');
        title.className = 'panel-section-title';
        title.textContent = `SLOTS  (${anchor.children.length} / ${layout.count ?? 1})`;
        const reRndBtn = document.createElement('button');
        reRndBtn.className = 'preset-btn primary';
        reRndBtn.style.cssText = 'padding:3px 8px; font-size:10px;';
        reRndBtn.textContent = 'Re-randomize';
        reRndBtn.addEventListener('click', async () => {
            await AnchorPopulator.repopulate(anchor, n => this.assetManager.getModel(n));
            this.onChanged?.();
            this.show(anchor);
        });
        header.appendChild(title);
        header.appendChild(reRndBtn);
        parent.appendChild(header);

        const slotList = document.createElement('div');
        slotList.className = 'slot-list';

        // children sorted by _slotIndex
        const sorted = [...anchor.children].sort((a, b) =>
            ((a.metadata['_slotIndex'] as number) ?? 0) - ((b.metadata['_slotIndex'] as number) ?? 0),
        );

        const models = this.assetManager.getAllModelNames();

        sorted.forEach(child => {
            const idx     = (child.metadata['_slotIndex'] as number) ?? 0;
            const isLocked = layout.slots?.[idx]?.locked ?? false;

            const row = document.createElement('div');
            row.className = 'slot-row';

            const badge = document.createElement('span');
            badge.className = 'slot-idx';
            badge.textContent = String(idx);
            row.appendChild(badge);

            const sel = document.createElement('select');
            sel.className = 'builder-select slot-select';
            models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m; opt.textContent = m;
                if (m === child.metadata['_modelName']) opt.selected = true;
                sel.appendChild(opt);
            });
            sel.addEventListener('change', async () => {
                await this._changeSlotModel(anchor, idx, sel.value, layout);
                this.onChanged?.();
                this.show(anchor);
            });
            row.appendChild(sel);

            const lockBtn = document.createElement('button');
            lockBtn.className = 'slot-lock-btn';
            lockBtn.textContent = isLocked ? '🔒' : '🔓';
            lockBtn.title = isLocked ? 'Unlock slot' : 'Lock slot';
            lockBtn.addEventListener('click', () => {
                if (!layout.slots) layout.slots = {};
                if (!layout.slots[idx]) layout.slots[idx] = {};
                layout.slots[idx].locked = !isLocked;
                this.show(anchor);
            });
            row.appendChild(lockBtn);

            slotList.appendChild(row);
        });

        parent.appendChild(slotList);
    }

    private _renderJoint(parent: HTMLElement, node: SceneNode): void {
        const axis  = (node.metadata['axis'] as Axis)   ?? 'y';
        const min   = (node.metadata['min']  as number) ?? -Math.PI;
        const max   = (node.metadata['max']  as number) ??  Math.PI;

        parent.appendChild(this._slider(
            `rotation.${axis}`, min, max,
            node.object3D.rotation[axis],
            v => { node.object3D.rotation[axis] = v; },
        ));

        const hint = document.createElement('div');
        hint.style.cssText = 'color:#7a8494; font-size:10px; margin-top:4px;';
        hint.textContent = `axis: ${axis}  |  range: ${min.toFixed(2)} ~ ${max.toFixed(2)}`;
        parent.appendChild(hint);
    }

    private _renderTransform(parent: HTMLElement, node: SceneNode): void {
        const pos   = node.object3D.position;
        const rot   = node.object3D.rotation;
        const range = 50;
        for (const ax of ['x', 'y', 'z'] as Axis[]) {
            parent.appendChild(this._slider(`pos.${ax}`, -range, range, pos[ax], v => { pos[ax] = v; }));
        }
        parent.appendChild(this._divider());
        for (const ax of ['x', 'y', 'z'] as Axis[]) {
            parent.appendChild(this._slider(`rot.${ax}`, -Math.PI, Math.PI, rot[ax], v => { rot[ax] = v; }));
        }
    }

    // ── 슬롯 모델 교체 ───────────────────────────────────

    private async _changeSlotModel(
        anchor: SceneNode,
        slotIdx: number,
        newModelName: string,
        layout: AnchorLayout,
    ): Promise<void> {
        const existing = anchor.children.find(c => c.metadata['_slotIndex'] === slotIdx);
        if (existing) {
            for (const n of existing.flatten()) NodeRegistry.unregister(n);
            anchor.removeChild(existing);
        }

        const descriptor = this.assetManager.getModel(newModelName);
        const instanceId  = `${anchor.id}_s${slotIdx}_${(Math.random() * 0xfffff | 0).toString(16)}`;
        const child       = NodeAssembler.load(descriptor, instanceId);
        child.metadata['_modelName'] = newModelName;
        child.metadata['_slotIndex'] = slotIdx;

        // 기존 slot transform 유지
        const gap     = layout.gap  ?? 2.0;
        const axis    = layout.axis ?? 'x';
        const axisIdx = axis === 'x' ? 0 : (axis === 'y' ? 1 : 2);
        const basePos: [number, number, number] = [0, 0, 0];
        basePos[axisIdx] = slotIdx * gap;

        const slotCfg = layout.slots?.[slotIdx];
        if (slotCfg?.transform?.position) child.object3D.position.set(...slotCfg.transform.position);
        else                               child.object3D.position.set(...basePos);
        if (slotCfg?.transform?.rotation)  child.object3D.rotation.set(...slotCfg.transform.rotation);

        anchor.addChild(child);

        // layout slots 업데이트
        if (!layout.slots) layout.slots = {};
        if (!layout.slots[slotIdx]) layout.slots[slotIdx] = {};
        layout.slots[slotIdx].model = newModelName;

        // _slotIndex 순 재정렬
        anchor.children.sort((a, b) =>
            ((a.metadata['_slotIndex'] as number) ?? 0) - ((b.metadata['_slotIndex'] as number) ?? 0),
        );
        anchor.children.forEach(c => { anchor.object3D.remove(c.object3D); anchor.object3D.add(c.object3D); });
    }

    // ── 공용 헬퍼 ────────────────────────────────────────

    private _section(title: string): HTMLElement {
        const section = document.createElement('div');
        section.className = 'panel-section';
        const t = document.createElement('div');
        t.className = 'panel-section-title';
        t.textContent = title;
        section.appendChild(t);
        return section;
    }

    private _propRow(key: string, value: string): HTMLElement {
        const row = document.createElement('div');
        row.className = 'prop-row';
        const k = document.createElement('span'); k.textContent = key;
        const v = document.createElement('span'); v.textContent = value;
        row.appendChild(k); row.appendChild(v);
        return row;
    }

    private _divider(): HTMLElement {
        const hr = document.createElement('hr');
        hr.className = 'prop-divider';
        return hr;
    }

    private _slider(
        name: string, min: number, max: number, initial: number,
        onChange: (v: number) => void,
    ): HTMLElement {
        const group = document.createElement('div');
        group.className = 'slider-group';
        const labelRow = document.createElement('div');
        labelRow.className = 'slider-label';
        const nameEl = document.createElement('span');
        nameEl.textContent = name;
        const valueInput = document.createElement('input');
        valueInput.type = 'number';
        valueInput.className = 'slider-value-input';
        valueInput.value = initial.toFixed(3);
        valueInput.step = '0.001';
        labelRow.appendChild(nameEl);
        labelRow.appendChild(valueInput);

        const input = document.createElement('input');
        input.type = 'range';
        input.min   = String(min);
        input.max   = String(max);
        input.step  = String((max - min) / 500);
        input.value = String(initial);

        input.addEventListener('input', () => {
            const v = parseFloat(input.value);
            valueInput.value = v.toFixed(3);
            onChange(v);
        });
        valueInput.addEventListener('change', () => {
            let v = parseFloat(valueInput.value);
            if (isNaN(v)) v = initial;
            v = Math.max(min, Math.min(max, v));
            valueInput.value = v.toFixed(3);
            input.value = String(v);
            onChange(v);
        });

        group.appendChild(labelRow);
        group.appendChild(input);
        return group;
    }
}
