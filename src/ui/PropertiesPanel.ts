import { SceneNode, NodeType } from '../core/SceneNode';

type Axis = 'x' | 'y' | 'z';

export class PropertiesPanel {
    private container: HTMLElement;

    constructor(container: HTMLElement) {
        this.container = container;
    }

    show(node: SceneNode): void {
        this.container.innerHTML = '';

        const section = this._section('PROPERTIES');

        section.appendChild(this._propRow('id',    node.id));
        section.appendChild(this._propRow('type',  node.type));
        section.appendChild(this._propRow('label', node.label));

        section.appendChild(this._divider());

        if (node.type === NodeType.JOINT) {
            this._buildJointControls(section, node);
        } else if (node.type === NodeType.GROUP) {
            this._buildTransformControls(section, node);
            
            const joints = this._getGroupJoints(node);
            if (joints.length > 0) {
                section.appendChild(this._divider());
                
                const jointsTitle = document.createElement('div');
                jointsTitle.className = 'panel-section-title';
                jointsTitle.textContent = 'GROUP JOINTS';
                jointsTitle.style.marginTop = '12px';
                section.appendChild(jointsTitle);

                for (const joint of joints) {
                    const jointBox = document.createElement('div');
                    jointBox.style.cssText = 'margin-top: 10px; padding-left: 10px; border-left: 2px solid #2a2040;';
                    
                    const jHeader = document.createElement('div');
                    jHeader.style.cssText = 'color:#b39ddb; font-size:11px; margin-bottom:6px; display:flex; justify-content:space-between;';
                    
                    const jLabel = document.createElement('span');
                    jLabel.textContent = joint.label;
                    jLabel.style.fontWeight = 'bold';
                    
                    const jId = document.createElement('span');
                    jId.textContent = joint.id;
                    jId.style.color = '#7a8494';
                    jId.style.fontSize = '9px';

                    jHeader.appendChild(jLabel);
                    jHeader.appendChild(jId);
                    jointBox.appendChild(jHeader);

                    this._buildJointControls(jointBox, joint);
                    section.appendChild(jointBox);
                }
            }
        } else {
            this._buildTransformControls(section, node);
        }

        this.container.appendChild(section);
    }

    private _getGroupJoints(group: SceneNode): SceneNode[] {
        const joints: SceneNode[] = [];
        const traverse = (n: SceneNode) => {
            for (const child of n.children) {
                if (child.type === NodeType.GROUP) continue;
                if (child.type === NodeType.JOINT) joints.push(child);
                traverse(child);
            }
        };
        traverse(group);
        return joints;
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

    private _buildJointControls(parent: HTMLElement, node: SceneNode): void {
        const axis  = (node.metadata['axis']  as Axis)   ?? 'y';
        const min   = (node.metadata['min']   as number) ?? -Math.PI;
        const max   = (node.metadata['max']   as number) ??  Math.PI;

        parent.appendChild(
            this._slider(
                `rotation.${axis}`,
                min, max,
                node.object3D.rotation[axis],
                (v) => { node.object3D.rotation[axis] = v; },
            ),
        );

        const hint = document.createElement('div');
        hint.style.cssText = 'color:#7a8494; font-size:10px; margin-top:4px;';
        hint.textContent = `axis: ${axis}  |  range: ${min.toFixed(2)} ~ ${max.toFixed(2)}`;
        parent.appendChild(hint);
    }

    private _buildTransformControls(parent: HTMLElement, node: SceneNode): void {
        const pos = node.object3D.position;
        const rot = node.object3D.rotation;
        const range = 20;

        for (const axis of ['x', 'y', 'z'] as Axis[]) {
            parent.appendChild(
                this._slider(
                    `pos.${axis}`,
                    -range, range,
                    pos[axis],
                    (v) => { pos[axis] = v; },
                ),
            );
        }
        parent.appendChild(this._divider());
        for (const axis of ['x', 'y', 'z'] as Axis[]) {
            parent.appendChild(
                this._slider(
                    `rot.${axis}`,
                    -Math.PI, Math.PI,
                    rot[axis],
                    (v) => { rot[axis] = v; },
                ),
            );
        }
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
        input.min  = String(min);
        input.max  = String(max);
        input.step = String((max - min) / 500);
        input.value = String(initial);

        // Sync slider -> input
        input.addEventListener('input', () => {
            const v = parseFloat(input.value);
            valueInput.value = v.toFixed(3);
            onChange(v);
        });

        // Sync input -> slider
        valueInput.addEventListener('change', () => {
            let v = parseFloat(valueInput.value);
            if (isNaN(v)) v = initial;
            // clamp
            v = Math.max(min, Math.min(max, v));
            valueInput.value = v.toFixed(3);
            input.value = String(v);
            onChange(v);
        });

        group.appendChild(labelRow);
        group.appendChild(input);
        return group;
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

    private _divider(): HTMLElement {
        const hr = document.createElement('hr');
        hr.className = 'prop-divider';
        return hr;
    }
}
