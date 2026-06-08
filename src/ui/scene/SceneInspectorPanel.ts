import { SceneNode, NodeType } from '../../core/SceneNode';
import { AnchorLayout } from '../../core/NodeAssembler';

type Axis = 'x' | 'y' | 'z';

const RAD2DEG = 180 / Math.PI;
const DEG2RAD = Math.PI / 180;

export class SceneInspectorPanel {
    private container: HTMLElement;
    private onAnchorLayoutChange?: (anchor: SceneNode, layout: AnchorLayout) => void;

    constructor(
        container: HTMLElement,
        onAnchorLayoutChange?: (anchor: SceneNode, layout: AnchorLayout) => void,
    ) {
        this.container = container;
        this.onAnchorLayoutChange = onAnchorLayoutChange;
    }

    show(node: SceneNode): void {
        this.container.innerHTML = '';
        const section = this._section('SCENE INSPECTOR');

        section.appendChild(this._propRow('id', node.id));
        section.appendChild(this._propRow('type', node.type));
        section.appendChild(this._propRow('label', node.label));

        const modelName = this._findModelName(node);
        if (modelName) {
            section.appendChild(this._propRow('asset', modelName));
        }

        section.appendChild(this._divider());

        if (node.type === NodeType.JOINT) {
            this._renderJoint(section, node);
        } else if (node.type === NodeType.ANCHOR) {
            this._renderAnchorLayout(section, node);
            section.appendChild(this._divider());
            this._renderTransform(section, node);
        } else {
            this._renderTransform(section, node);
        }

        this.container.appendChild(section);
    }

    private _findModelName(node: SceneNode): string | null {
        let cur: SceneNode | null = node;
        while (cur) {
            if (cur.metadata['_modelName'] !== undefined) {
                return String(cur.metadata['_modelName']);
            }
            cur = cur.parent;
        }
        return null;
    }

    clear(): void {
        this.container.innerHTML = '';
        const section = this._section('SCENE INSPECTOR');
        const empty = document.createElement('div');
        empty.style.cssText = 'color:#7a8494; padding:8px 0; font-size:11px;';
        empty.textContent = 'No node selected.';
        section.appendChild(empty);
        this.container.appendChild(section);
    }

    private _renderJoint(parent: HTMLElement, node: SceneNode): void {
        const axis = (node.metadata['axis'] as Axis) ?? 'y';
        const minRad = (node.metadata['min'] as number) ?? -Math.PI;
        const maxRad = (node.metadata['max'] as number) ?? Math.PI;

        parent.appendChild(this._slider(
            `rotation.${axis} (°)`,
            minRad * RAD2DEG,
            maxRad * RAD2DEG,
            node.object3D.rotation[axis] * RAD2DEG,
            v => { node.object3D.rotation[axis] = v * DEG2RAD; },
        ));

        const hint = document.createElement('div');
        hint.style.cssText = 'color:#7a8494; font-size:10px; margin-top:4px;';
        hint.textContent = `axis: ${axis}  |  range: ${(minRad * RAD2DEG).toFixed(1)}° ~ ${(maxRad * RAD2DEG).toFixed(1)}°`;
        parent.appendChild(hint);
    }

    private _renderTransform(parent: HTMLElement, node: SceneNode): void {
        const pos = node.object3D.position;
        const rot = node.object3D.rotation;
        for (const ax of ['x', 'y', 'z'] as Axis[]) {
            parent.appendChild(this._numberField(`pos.${ax}`, pos[ax], -1000, 1000, 0.1, v => { pos[ax] = v; }));
        }
        parent.appendChild(this._divider());
        for (const ax of ['x', 'y', 'z'] as Axis[]) {
            parent.appendChild(this._numberField(`rot.${ax} (°)`, rot[ax] * RAD2DEG, -360, 360, 0.1, v => { rot[ax] = v * DEG2RAD; }));
        }
    }

    private _renderAnchorLayout(parent: HTMLElement, node: SceneNode): void {
        const layout = this._cloneLayout(
            (node.metadata['_layoutDescriptor'] as AnchorLayout | null) ?? { kind: 'single' },
        );

        parent.appendChild(this._subTitle('Anchor Layout'));

        const kind = document.createElement('select');
        kind.className = 'builder-select';
        kind.style.width = '100px';
        for (const value of ['single', 'array']) {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = value;
            if (layout.kind === value) opt.selected = true;
            kind.appendChild(opt);
        }
        kind.addEventListener('change', () => {
            layout.kind = kind.value as 'single' | 'array';
            this._commitAnchorLayout(node, layout);
            this.show(node);
        });
        parent.appendChild(this._field('kind', kind));

        const axis = document.createElement('select');
        axis.className = 'builder-select';
        axis.style.width = '80px';
        for (const value of ['x', 'y', 'z']) {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = value;
            if ((layout.axis ?? 'x') === value) opt.selected = true;
            axis.appendChild(opt);
        }
        axis.addEventListener('change', () => {
            layout.axis = axis.value as Axis;
            this._commitAnchorLayout(node, layout);
        });

        if (layout.kind === 'array') {
            parent.appendChild(this._field('axis', axis));
            parent.appendChild(this._numberField('count', Number(layout.count ?? 1), 1, 100, 1, value => {
                layout.count = Math.max(1, Math.round(value));
                this._commitAnchorLayout(node, layout);
            }));
            parent.appendChild(this._numberField('gap', Number(layout.gap ?? 2), 0, 50, 0.1, value => {
                layout.gap = value;
                this._commitAnchorLayout(node, layout);
            }));
            parent.appendChild(this._numberField('start', Number(layout.start ?? 0), -50, 50, 0.1, value => {
                layout.start = value;
                this._commitAnchorLayout(node, layout);
            }));
        }
    }

    private _commitAnchorLayout(node: SceneNode, layout: AnchorLayout): void {
        const next = this._cloneLayout(layout);
        node.metadata['_layoutDescriptor'] = next;
        this.onAnchorLayoutChange?.(node, next);
    }

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
        const k = document.createElement('span');
        k.textContent = key;
        const v = document.createElement('span');
        v.textContent = value;
        row.appendChild(k);
        row.appendChild(v);
        return row;
    }

    private _subTitle(text: string): HTMLElement {
        const el = document.createElement('div');
        el.className = 'panel-section-title';
        el.style.marginTop = '8px';
        el.textContent = text;
        return el;
    }

    private _field(labelText: string, control: HTMLElement): HTMLElement {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px;';
        const label = document.createElement('span');
        label.textContent = labelText;
        label.style.color = '#8899aa';
        row.appendChild(label);
        row.appendChild(control);
        return row;
    }

    private _numberField(
        label: string,
        initial: number,
        min: number,
        max: number,
        step: number,
        onChange: (value: number) => void,
    ): HTMLElement {
        const input = document.createElement('input');
        input.type = 'number';
        input.className = 'slider-value-input';
        input.style.width = '80px';
        input.value = String(initial);
        input.min = String(min);
        input.max = String(max);
        input.step = String(step);
        input.addEventListener('change', () => {
            const value = parseFloat(input.value);
            if (!Number.isNaN(value)) onChange(Math.min(max, Math.max(min, value)));
        });
        return this._field(label, input);
    }

    private _cloneLayout(layout: AnchorLayout): AnchorLayout {
        return JSON.parse(JSON.stringify(layout)) as AnchorLayout;
    }

    private _divider(): HTMLElement {
        const hr = document.createElement('hr');
        hr.className = 'prop-divider';
        return hr;
    }

    private _slider(
        name: string,
        min: number,
        max: number,
        initial: number,
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
        input.min = String(min);
        input.max = String(max);
        input.step = String((max - min) / 500);
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
