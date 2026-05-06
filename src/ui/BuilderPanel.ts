import * as THREE from 'three';
import { SceneNode, NodeType } from '../core/SceneNode';
import { NodeRegistry } from '../core/NodeRegistry';
import { NodeFactory } from '../core/NodeFactory';
import { AnchorLayout } from '../core/NodeAssembler';
import { AnchorPopulator } from '../core/AnchorPopulator';
import { AssetManager } from '../core/AssetManager';

type RandomizeComp = 'px' | 'py' | 'pz' | 'rx' | 'ry' | 'rz';
const ALL_COMPS: RandomizeComp[] = ['px', 'py', 'pz', 'rx', 'ry', 'rz'];

export class BuilderPanel {
    private container:    HTMLElement;
    private assetManager: AssetManager;
    private onChanged:    () => void;
    private roots:        SceneNode[] = [];
    private targetNode:   SceneNode | null = null;

    private targetEl!: HTMLElement;
    private formEl!:   HTMLElement;

    constructor(container: HTMLElement, assetManager: AssetManager, onChanged: () => void) {
        this.container    = container;
        this.assetManager = assetManager;
        this.onChanged    = onChanged;
        this._build();
    }

    setRoots(roots: SceneNode[]): void {
        this.roots = roots;
        this._refreshTargetSelector();
    }

    // ── 초기 DOM 구조 ────────────────────────────────────

    private _build(): void {
        this.container.innerHTML = '';

        const targetSection = document.createElement('div');
        targetSection.className = 'panel-section';
        const targetTitle = document.createElement('div');
        targetTitle.className = 'panel-section-title';
        targetTitle.textContent = 'TARGET NODE';
        this.targetEl = document.createElement('div');
        targetSection.appendChild(targetTitle);
        targetSection.appendChild(this.targetEl);
        this.container.appendChild(targetSection);

        this.formEl = document.createElement('div');
        this.formEl.style.overflowY = 'auto';
        this.formEl.style.flex = '1';
        this.container.appendChild(this.formEl);
    }

    // ── 타겟 셀렉터 ──────────────────────────────────────

    private _refreshTargetSelector(): void {
        const oldId = this.targetNode?.id;
        this.targetEl.innerHTML = '';
        if (this.roots.length === 0) return;

        const candidates: SceneNode[] = [];
        for (const root of this.roots) {
            for (const n of root.flatten()) {
                if (n.type === NodeType.GROUP || n.type === NodeType.ANCHOR) candidates.push(n);
            }
        }

        const sel = document.createElement('select');
        sel.className = 'builder-select';
        candidates.forEach(n => {
            const opt = document.createElement('option');
            opt.value = n.id;
            opt.textContent = `[${n.type}] ${n.label}`;
            sel.appendChild(opt);
        });
        sel.addEventListener('change', () => {
            const node = candidates.find(n => n.id === sel.value) ?? null;
            this._setTarget(node);
        });
        this.targetEl.appendChild(sel);

        const preserved = candidates.find(n => n.id === oldId);
        if (preserved) {
            sel.value = preserved.id;
            this._setTarget(preserved);
        } else if (candidates.length > 0) {
            this._setTarget(candidates[0]);
        }
    }

    private _setTarget(node: SceneNode | null): void {
        this.targetNode = node;
        this._renderForm();
    }

    // ── 폼 렌더링 ────────────────────────────────────────

    private _renderForm(): void {
        this.formEl.innerHTML = '';
        if (!this.targetNode) return;

        if (this.targetNode.type === NodeType.GROUP) {
            this._renderAddAnchorForm();
        } else if (this.targetNode.type === NodeType.ANCHOR) {
            this._renderEditAnchorForm(this.targetNode);
        }
    }

    // GROUP → ANCHOR 추가 폼
    private _renderAddAnchorForm(): void {
        const section = document.createElement('div');
        section.className = 'panel-section';
        const title = document.createElement('div');
        title.className = 'panel-section-title';
        title.textContent = 'ADD ANCHOR';
        section.appendChild(title);

        const labelInput = document.createElement('input');
        labelInput.placeholder = 'anchor label';
        labelInput.style.cssText = 'width:100%; background:#252a33; border:1px solid #2d3139; color:#dde1e7; font-family:inherit; font-size:11px; padding:4px 6px; border-radius:3px; margin-bottom:8px; box-sizing:border-box;';
        section.appendChild(labelInput);

        const layout: AnchorLayout = { kind: 'single' };
        this._renderLayoutFields(section, layout);

        const addBtn = document.createElement('button');
        addBtn.className = 'preset-btn primary';
        addBtn.style.cssText = 'width:100%; margin-top:10px;';
        addBtn.textContent = 'Add ANCHOR';
        addBtn.addEventListener('click', () => {
            const label = labelInput.value.trim();
            if (!label) { alert('Enter a label.'); return; }
            this._addAnchor(label, layout);
        });
        section.appendChild(addBtn);
        this.formEl.appendChild(section);
    }

    // ANCHOR 편집 폼
    private _renderEditAnchorForm(anchor: SceneNode): void {
        const section = document.createElement('div');
        section.className = 'panel-section';
        const title = document.createElement('div');
        title.className = 'panel-section-title';
        title.textContent = 'EDIT ANCHOR LAYOUT';
        section.appendChild(title);

        const layout: AnchorLayout = {
            ...((anchor.metadata['_layoutDescriptor'] as AnchorLayout) ?? { kind: 'single' }),
        };
        this._renderLayoutFields(section, layout);

        const btnRow = document.createElement('div');
        btnRow.className = 'builder-actions';

        const applyBtn = document.createElement('button');
        applyBtn.className = 'preset-btn primary';
        applyBtn.textContent = 'Apply Layout';
        applyBtn.addEventListener('click', () => {
            anchor.metadata['_layoutDescriptor'] = layout;
            NodeFactory.applyLayout(anchor.object3D, layout);
            this.onChanged();
        });
        btnRow.appendChild(applyBtn);

        if (layout.defaultModel) {
            const popBtn = document.createElement('button');
            popBtn.className = 'preset-btn';
            popBtn.textContent = 'Populate Slots';
            popBtn.addEventListener('click', async () => {
                anchor.metadata['_layoutDescriptor'] = layout;
                await AnchorPopulator.populate(anchor, n => this.assetManager.getModel(n));
                this.onChanged();
            });
            btnRow.appendChild(popBtn);
        }

        section.appendChild(btnRow);
        this.formEl.appendChild(section);
    }

    // ── 공용 레이아웃 필드 ───────────────────────────────

    private _renderLayoutFields(parent: HTMLElement, layout: AnchorLayout): void {
        // kind
        parent.appendChild(this._field('kind',
            this._select(['single', 'array'], layout.kind ?? 'single', v => {
                layout.kind = v as 'single' | 'array';
                this._renderForm(); // re-render to show/hide array fields
            }),
        ));

        if (layout.kind !== 'array') return;

        // count
        parent.appendChild(this._numField('count', 1, 50, layout.count ?? 5, v => { layout.count = v; }));
        // gap
        parent.appendChild(this._numField('gap', 0.1, 30, layout.gap ?? 2, v => { layout.gap = v; }));
        // axis
        parent.appendChild(this._field('axis',
            this._select(['x', 'y', 'z'], layout.axis ?? 'x', v => { layout.axis = v as 'x'|'y'|'z'; }),
        ));
        // defaultModel
        const models = this.assetManager.getAllModelNames();
        if (models.length > 0) {
            parent.appendChild(this._field('default model',
                this._select(models, layout.defaultModel ?? models[0], v => { layout.defaultModel = v; }),
            ));
            if (!layout.defaultModel) layout.defaultModel = models[0];
        }

        // randomize
        const rndTitle = document.createElement('div');
        rndTitle.className = 'panel-section-title';
        rndTitle.style.marginTop = '10px';
        rndTitle.textContent = 'RANDOMIZE';
        parent.appendChild(rndTitle);

        if (!layout.randomize) layout.randomize = { components: [], ranges: {} };

        ALL_COMPS.forEach(comp => {
            const isActive = layout.randomize!.components.includes(comp);
            const row = document.createElement('div');
            row.style.cssText = 'display:flex; align-items:center; gap:6px; margin-bottom:4px;';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = isActive;
            cb.style.cursor = 'pointer';

            const lbl = document.createElement('span');
            lbl.textContent = comp;
            lbl.style.cssText = 'color:#8899aa; font-size:11px; width:24px;';

            const rangeWrap = document.createElement('div');
            rangeWrap.style.cssText = 'display:flex; gap:4px; flex:1;';
            rangeWrap.style.display = isActive ? 'flex' : 'none';

            const existing = layout.randomize!.ranges[comp];
            const minIn = this._miniNum(existing?.[0] ?? -Math.PI, v => {
                layout.randomize!.ranges[comp] = [v, layout.randomize!.ranges[comp]?.[1] ?? Math.PI];
            });
            const maxIn = this._miniNum(existing?.[1] ?? Math.PI, v => {
                layout.randomize!.ranges[comp] = [layout.randomize!.ranges[comp]?.[0] ?? -Math.PI, v];
            });
            const sep = document.createElement('span');
            sep.textContent = '~';
            sep.style.color = '#7a8494';

            rangeWrap.appendChild(minIn);
            rangeWrap.appendChild(sep);
            rangeWrap.appendChild(maxIn);

            cb.addEventListener('change', () => {
                rangeWrap.style.display = cb.checked ? 'flex' : 'none';
                if (cb.checked) {
                    if (!layout.randomize!.components.includes(comp)) layout.randomize!.components.push(comp);
                    if (!layout.randomize!.ranges[comp]) layout.randomize!.ranges[comp] = [-Math.PI, Math.PI];
                } else {
                    layout.randomize!.components = layout.randomize!.components.filter(c => c !== comp);
                }
            });

            row.appendChild(cb);
            row.appendChild(lbl);
            row.appendChild(rangeWrap);
            parent.appendChild(row);
        });
    }

    // ── ANCHOR 추가 ──────────────────────────────────────

    private _addAnchor(label: string, layout: AnchorLayout): void {
        const group = this.targetNode;
        if (!group || group.type !== NodeType.GROUP) return;

        let id = `${group.id}.${label}`;
        let suffix = 1;
        while (NodeRegistry.has(id)) id = `${group.id}.${label}_${suffix++}`;

        const anchor = new SceneNode(id, label, NodeType.ANCHOR, new THREE.Group());
        anchor.metadata['_layoutDescriptor']  = { ...layout };
        anchor.metadata['_defaultPosition']   = [0, 0, 0];
        anchor.metadata['_defaultRotation']   = [0, 0, 0];
        NodeRegistry.register(anchor);
        group.addChild(anchor);
        this.onChanged();
    }

    // ── 헬퍼 ─────────────────────────────────────────────

    private _field(label: string, control: HTMLElement): HTMLElement {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;';
        const lbl = document.createElement('span');
        lbl.textContent = label;
        lbl.style.color = '#8899aa';
        row.appendChild(lbl);
        row.appendChild(control);
        return row;
    }

    private _select(options: string[], current: string, onChange: (v: string) => void): HTMLSelectElement {
        const sel = document.createElement('select');
        sel.className = 'builder-select';
        sel.style.width = '130px';
        options.forEach(o => {
            const opt = document.createElement('option');
            opt.value = o; opt.textContent = o;
            if (o === current) opt.selected = true;
            sel.appendChild(opt);
        });
        sel.addEventListener('change', () => onChange(sel.value));
        return sel;
    }

    private _numField(label: string, min: number, max: number, initial: number, onChange: (v: number) => void): HTMLElement {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;';
        const lbl = document.createElement('span');
        lbl.textContent = label;
        lbl.style.color = '#8899aa';
        const inp = this._miniNum(initial, onChange);
        inp.setAttribute('min', String(min));
        inp.setAttribute('max', String(max));
        row.appendChild(lbl);
        row.appendChild(inp);
        return row;
    }

    private _miniNum(initial: number, onChange: (v: number) => void): HTMLInputElement {
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.className = 'slider-value-input';
        inp.style.width = '70px';
        inp.value = String(initial);
        inp.step = '0.1';
        inp.addEventListener('change', () => {
            const v = parseFloat(inp.value);
            if (!isNaN(v)) onChange(v);
        });
        return inp;
    }
}
