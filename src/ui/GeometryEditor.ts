import { SceneNode, NodeType } from '../core/SceneNode';
import { GeometryDescriptor, NodeFactory } from '../core/NodeFactory';
import { AnchorLayout } from '../core/NodeAssembler';

interface ParamDef { key: string; label: string; min: number; max: number; default: number }

const SHAPE_PARAMS: Record<string, ParamDef[]> = {
    Box:          [
        { key:'width',        label:'width',       min:0.01, max:20, default:1 },
        { key:'height',       label:'height',      min:0.01, max:20, default:1 },
        { key:'depth',        label:'depth',       min:0.01, max:20, default:1 },
    ],
    Cylinder:     [
        { key:'radiusTop',    label:'radius top',  min:0.01, max:5,  default:0.5 },
        { key:'radiusBottom', label:'radius bot',  min:0.01, max:5,  default:0.5 },
        { key:'height',       label:'height',      min:0.01, max:20, default:1 },
    ],
    Sphere:       [{ key:'radius', label:'radius', min:0.01, max:10, default:0.5 }],
    Capsule:      [
        { key:'radius', label:'radius', min:0.01, max:5,  default:0.3 },
        { key:'length', label:'length', min:0.01, max:20, default:1   },
    ],
    JointCapsule: [
        { key:'radius', label:'radius', min:0.01, max:5,  default:0.3 },
        { key:'length', label:'length', min:0.01, max:20, default:1   },
    ],
    ConveyorBody: [{ key:'length', label:'length', min:1, max:50, default:10 }],
    LegArray: [
        { key:'length', label:'length', min:1,    max:50, default:10   },
        { key:'height', label:'height', min:0.1,  max:10, default:4.15 },
        { key:'width',  label:'width',  min:0.1,  max:10, default:4.3  },
        { key:'gap',    label:'gap',    min:0.5,  max:20, default:5    },
    ],
    Elbow: [
        { key:'pathRadius',  label:'path radius',  min:0.1, max:5, default:1.2  },
        { key:'outerRadius', label:'outer radius', min:0.1, max:2, default:0.6  },
        { key:'innerRadius', label:'inner radius', min:0.0, max:2, default:0.45 },
    ],
};

const ALL_SHAPES = Object.keys(SHAPE_PARAMS);

const LAYOUT_ARRAY_PARAMS: ParamDef[] = [
    { key:'count', label:'count', min:1,   max:100, default:5 },
    { key:'gap',   label:'gap',   min:0.0, max:50,  default:2 },
];

export class GeometryEditor {
    private container: HTMLElement;
    private node: SceneNode | null = null;
    private geometryDraft: GeometryDescriptor = { shape: 'Box', color: '#cccccc' };
    private layoutDraft: AnchorLayout = { kind: 'single' };
    private onChange: (node: SceneNode) => void;

    constructor(container: HTMLElement, onChange: (node: SceneNode) => void) {
        this.container = container;
        this.onChange  = onChange;
    }

    show(node: SceneNode): void {
        this.node = node;

        if (node.type === NodeType.LINK) {
            const saved = node.metadata['_geometryDescriptor'] as GeometryDescriptor | null;
            this.geometryDraft = saved ? { ...saved } : { shape: 'Box', color: '#cccccc' };
        } else if (node.type === NodeType.ANCHOR) {
            const saved = node.metadata['_layoutDescriptor'] as AnchorLayout | null;
            this.layoutDraft = saved ? { ...saved } : { kind: 'single' };
        }
        this._render();
    }

    getGeometryDraft(): GeometryDescriptor { return { ...this.geometryDraft }; }
    getLayoutDraft():   AnchorLayout   { return { ...this.layoutDraft }; }

    private _render(): void {
        const node = this.node;
        if (!node) return;
        this.container.innerHTML = '';

        if (node.type === NodeType.LINK)   this._renderLink(node);
        if (node.type === NodeType.GROUP)  this._renderGroup(node);
        if (node.type === NodeType.ANCHOR) this._renderAnchor(node);
        if (node.type === NodeType.JOINT)  this._renderJoint(node);
    }

    // ── LINK: shape 편집 ───────────────────────────────
    private _renderLink(node: SceneNode): void {
        this.container.appendChild(this._sectionTitle('Geometry'));

        const shapeRow = document.createElement('div');
        shapeRow.className = 'slider-group';
        const shapeLabel = document.createElement('div');
        shapeLabel.className = 'slider-label';
        shapeLabel.innerHTML = '<span>shape</span>';
        const shapeSelect = document.createElement('select');
        shapeSelect.className = 'builder-select';
        for (const s of ALL_SHAPES) {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            if (s === this.geometryDraft.shape) opt.selected = true;
            shapeSelect.appendChild(opt);
        }
        shapeSelect.addEventListener('change', () => {
            this.geometryDraft = { ...this.geometryDraft, shape: shapeSelect.value };
            this.onChange(node);
            this._render();
        });
        shapeRow.appendChild(shapeLabel);
        shapeRow.appendChild(shapeSelect);
        this.container.appendChild(shapeRow);

        if (this.geometryDraft.shape === 'JointCapsule') {
            this.container.appendChild(this._colorRow('bodyColor', this.geometryDraft['bodyColor'] as string ?? '#cccccc'));
            this.container.appendChild(this._colorRow('capColor',  this.geometryDraft['capColor']  as string ?? '#00bcd4'));
        } else {
            this.container.appendChild(this._colorRow('color', this.geometryDraft.color ?? '#cccccc'));
        }

        const opacityVal = (this.geometryDraft['opacity'] as number) ?? 1;
        this.container.appendChild(this._slider('opacity', 0, 1, opacityVal, (v) => {
            this.geometryDraft = { ...this.geometryDraft, opacity: v };
            this.onChange(node);
        }));

        const params = SHAPE_PARAMS[this.geometryDraft.shape] ?? [];
        for (const p of params) {
            const val = (this.geometryDraft[p.key] as number) ?? p.default;
            this.container.appendChild(this._slider(p.label, p.min, p.max, val, (v) => {
                this.geometryDraft = { ...this.geometryDraft, [p.key]: v };
                this.onChange(node);
            }));
        }

        this._renderTransform(node);
    }

    // ── GROUP: transform만 (geometry/layout 둘 다 없음) ──
    private _renderGroup(node: SceneNode): void {
        this._renderTransform(node);
    }

    // ── ANCHOR: layout (kind/count/gap/axis) + transform ──
    private _renderAnchor(node: SceneNode): void {
        this.container.appendChild(this._sectionTitle('Layout'));

        const kindRow = document.createElement('div');
        kindRow.className = 'slider-group';
        const kindLabel = document.createElement('div');
        kindLabel.className = 'slider-label';
        kindLabel.innerHTML = '<span>kind</span>';
        const kindSelect = document.createElement('select');
        kindSelect.className = 'builder-select';
        for (const k of ['single', 'array']) {
            const opt = document.createElement('option');
            opt.value = k; opt.textContent = k;
            if (k === this.layoutDraft.kind) opt.selected = true;
            kindSelect.appendChild(opt);
        }
        kindSelect.addEventListener('change', () => {
            this.layoutDraft = { ...this.layoutDraft, kind: kindSelect.value as 'single' | 'array' };
            NodeFactory.applyLayout(node.object3D, this.layoutDraft);
            this.onChange(node);
            this._render();
        });
        kindRow.appendChild(kindLabel);
        kindRow.appendChild(kindSelect);
        this.container.appendChild(kindRow);

        if (this.layoutDraft.kind === 'array') {
            this.container.appendChild(this._axisRow(
                this.layoutDraft.axis ?? 'x',
                (ax) => {
                    this.layoutDraft = { ...this.layoutDraft, axis: ax as 'x' | 'y' | 'z' };
                    NodeFactory.applyLayout(node.object3D, this.layoutDraft);
                    this.onChange(node);
                },
                'axis',
            ));
            for (const p of LAYOUT_ARRAY_PARAMS) {
                const val = (this.layoutDraft[p.key as 'count' | 'gap'] as number) ?? p.default;
                this.container.appendChild(this._slider(p.label, p.min, p.max, val, (v) => {
                    this.layoutDraft = { ...this.layoutDraft, [p.key]: v };
                    NodeFactory.applyLayout(node.object3D, this.layoutDraft);
                    this.onChange(node);
                }));
            }
        }

        this._renderTransform(node);
    }

    // ── JOINT: transform + kinematic config (layout 없음) ──
    private _renderJoint(node: SceneNode): void {
        this._renderTransform(node);

        this.container.appendChild(this._sectionTitle('Joint Config'));
        this.container.appendChild(this._axisRow(
            (node.metadata['axis'] as string) ?? 'y',
            (ax) => { node.metadata['axis'] = ax; },
            'Joint Axis',
        ));
        this.container.appendChild(this._slider('min', -Math.PI * 2, 0,
            (node.metadata['min'] as number) ?? -Math.PI,
            v => { node.metadata['min'] = v; },
        ));
        this.container.appendChild(this._slider('max', 0, Math.PI * 2,
            (node.metadata['max'] as number) ?? Math.PI,
            v => { node.metadata['max'] = v; },
        ));
    }

    private _renderTransform(node: SceneNode): void {
        this.container.appendChild(this._sectionTitle('Transform'));
        const pos = node.object3D.position;
        const rot = node.object3D.rotation;
        type Axis = 'x' | 'y' | 'z';
        for (const ax of ['x','y','z'] as Axis[]) {
            this.container.appendChild(this._slider(`pos.${ax}`, -20, 20, pos[ax], v => { pos[ax] = v; }));
        }
        for (const ax of ['x','y','z'] as Axis[]) {
            this.container.appendChild(this._slider(`rot.${ax}`, -Math.PI, Math.PI, rot[ax], v => { rot[ax] = v; }));
        }
    }

    private _colorRow(key: string, initial: string): HTMLElement {
        const row = document.createElement('div');
        row.className = 'color-row';
        const label = document.createElement('label');
        label.textContent = key;
        const input = document.createElement('input');
        input.type = 'color';
        input.value = initial.startsWith('#') ? initial : '#cccccc';
        input.addEventListener('input', () => {
            this.geometryDraft = { ...this.geometryDraft, [key]: input.value };
            if (this.node) this.onChange(this.node);
        });
        row.appendChild(label);
        row.appendChild(input);
        return row;
    }

    private _axisRow(initial: string, onchange: (ax: string) => void, labelText: string = 'axis'): HTMLElement {
        const row = document.createElement('div');
        row.className = 'axis-row';
        const label = document.createElement('label');
        label.textContent = labelText;
        const sel = document.createElement('select');
        sel.className = 'builder-select';
        sel.style.width = '80px';
        for (const ax of ['x','y','z']) {
            const opt = document.createElement('option');
            opt.value = ax; opt.textContent = ax;
            if (ax === initial) opt.selected = true;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', () => onchange(sel.value));
        row.appendChild(label);
        row.appendChild(sel);
        return row;
    }

    private _slider(name: string, min: number, max: number, initial: number, onChange: (v: number) => void): HTMLElement {
        const group = document.createElement('div');
        group.className = 'slider-group';
        const labelRow = document.createElement('div');
        labelRow.className = 'slider-label';
        const nameEl  = document.createElement('span');
        nameEl.textContent = name;

        const valueInput = document.createElement('input');
        valueInput.type = 'number';
        valueInput.className = 'slider-value-input';
        valueInput.value = initial.toFixed(3);
        valueInput.step = '0.001';

        labelRow.appendChild(nameEl);
        labelRow.appendChild(valueInput);

        const input = document.createElement('input');
        input.type  = 'range';
        input.min   = String(min);
        input.max   = String(max);
        input.step  = String((max - min) / 500);
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

    private _sectionTitle(text: string): HTMLElement {
        const el = document.createElement('div');
        el.className = 'geo-section-title';
        el.textContent = text;
        return el;
    }
}
