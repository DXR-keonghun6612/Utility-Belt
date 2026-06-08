import { NodeDescriptor, AnchorLayout } from '../../core/NodeAssembler';
import { NodeType } from '../../core/SceneNode';
import {
    renderLinkProps,
    renderAnchorProps,
    renderJointProps,
    renderTransformProps,
} from './NodeFieldWidgets';

export class NodeTreeInspector {
    private container: HTMLElement;
    private descriptor: NodeDescriptor | null = null;
    private previewParams: Record<string, unknown> = {};
    private expanded = new Set<string>();
    private _selectedDescId: string | null = null;
    private onDescriptorChange: (d: NodeDescriptor) => void;

    // ── DnD ───────────────────────────────────────────────────────
    private _dragSrcId: string | null = null;
    private _dropInfo: { targetId: string; pos: 'before' | 'after' | 'into' } | null = null;
    private _dropRow: HTMLElement | null = null;

    constructor(container: HTMLElement, onDescriptorChange: (d: NodeDescriptor) => void) {
        this.container = container;
        this.onDescriptorChange = onDescriptorChange;
    }

    setDescriptor(descriptor: NodeDescriptor, previewParams: Record<string, unknown>): void {
        const isNew = this.descriptor?.id !== descriptor.id;
        this.descriptor = descriptor;
        this.previewParams = previewParams;
        if (isNew) {
            this.expanded = new Set<string>();
            this._expandAll(descriptor);
        } else {
            this.expanded.add(descriptor.id);
        }
        this._render();
    }

    private _expandAll(desc: NodeDescriptor): void {
        // JOINT는 접힌 상태로 시작 — 관절 단위 섹션으로 분리해서 보여줌
        if (desc.type !== 'JOINT') this.expanded.add(desc.id);
        for (const child of desc.children ?? []) {
            if (typeof child !== 'string') this._expandAll(child as NodeDescriptor);
        }
    }

    updatePreviewParams(previewParams: Record<string, unknown>): void {
        this.previewParams = previewParams;
    }

    selectById(id: string | null): void {
        this._selectedDescId = id;
        if (id && this.descriptor) {
            const path = this._findPath(this.descriptor, id);
            if (path) path.forEach(p => this.expanded.add(p));
        }
        this._render();
        if (id) {
            const el = this.container.querySelector<HTMLElement>(`[data-node-id="${CSS.escape(id)}"]`);
            el?.scrollIntoView({ block: 'nearest' });
        }
    }

    private _findPath(desc: NodeDescriptor, targetId: string): string[] | null {
        if (desc.id === targetId) return [desc.id];
        for (const child of desc.children ?? []) {
            if (typeof child === 'string') continue;
            const sub = this._findPath(child as NodeDescriptor, targetId);
            if (sub) return [desc.id, ...sub];
        }
        return null;
    }

    // ── Internal helpers ──────────────────────────────────────────

    private _bindings(): string[] {
        if (!this.descriptor) return [];
        const out: string[] = [];
        for (const k of Object.keys(this.descriptor.parameters ?? {})) out.push(`$params.${k}`);
        for (const k of Object.keys(this.descriptor.computed ?? {}))   out.push(`$computed.${k}`);
        return out;
    }

    private _emit(): void {
        if (this.descriptor) this.onDescriptorChange(this.descriptor);
    }

    // ── Render ────────────────────────────────────────────────────

    private _render(): void {
        this.container.innerHTML = '';
        if (this.descriptor) this._renderNode(this.descriptor, 0, null);
    }

    private _renderNode(desc: NodeDescriptor, depth: number, parentDesc: NodeDescriptor | null): void {
        const isExpanded = this.expanded.has(desc.id);
        const isRoot = !parentDesc;

        // ── header row ────────────────────────────────────────────
        const row = document.createElement('div');
        row.className = 'nti-row' + (desc.id === this._selectedDescId ? ' nti-selected' : '');
        row.dataset['nodeId'] = desc.id;
        row.style.paddingLeft = `${8 + depth * 14}px`;

        // drag handle (루트 제외)
        if (!isRoot) {
            const dh = document.createElement('span');
            dh.className = 'nti-drag-handle';
            dh.textContent = '⠿';
            dh.title = 'Drag to reorder / reparent';
            dh.draggable = true;
            dh.addEventListener('dragstart', (e) => {
                this._dragSrcId = desc.id;
                e.dataTransfer!.setData('text/plain', desc.id);
                e.dataTransfer!.effectAllowed = 'move';
                requestAnimationFrame(() => row.classList.add('nti-dragging'));
            });
            dh.addEventListener('dragend', () => {
                row.classList.remove('nti-dragging');
                this._clearDropIndicator();
                this._dragSrcId = null;
                this._dropInfo   = null;
            });
            row.appendChild(dh);
        }

        // toggle
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'nti-toggle';
        toggleBtn.textContent = isExpanded ? '▼' : '▶';
        toggleBtn.addEventListener('click', e => {
            e.stopPropagation();
            this.expanded.has(desc.id) ? this.expanded.delete(desc.id) : this.expanded.add(desc.id);
            this._render();
        });
        row.appendChild(toggleBtn);

        // type badge
        const badge = document.createElement('span');
        badge.className = `tree-badge badge-${desc.type}`;
        badge.textContent = desc.type;
        row.appendChild(badge);

        // exposed anchor dot (badge 오른쪽)
        if (desc.type === NodeType.ANCHOR &&
            (desc.layout as AnchorLayout | undefined)?.exposed !== false) {
            const dot = document.createElement('span');
            dot.className = 'nti-exposed-dot';
            dot.title = 'Exposed connection point';
            row.appendChild(dot);
        }

        // label (편집 가능)
        const labelEl = document.createElement('span');
        labelEl.className = 'nti-node-label';
        labelEl.textContent = desc.label ?? desc.id;
        labelEl.contentEditable = 'true';
        labelEl.spellcheck = false;
        labelEl.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); labelEl.blur(); } });
        labelEl.addEventListener('blur', () => {
            const v = labelEl.textContent?.trim() || (desc.label ?? desc.id);
            if (v !== desc.label) { desc.label = v; this._emit(); }
        });
        row.appendChild(labelEl);

        // + 자식 추가 버튼 (LINK 제외)
        if (desc.type !== 'LINK') {
            const addBtn = document.createElement('button');
            addBtn.className = 'nti-icon-btn nti-add-child-btn';
            addBtn.textContent = '+';
            addBtn.title = 'Add child node';
            addBtn.addEventListener('click', e => {
                e.stopPropagation();
                this.expanded.add(desc.id);
                this._render();
                requestAnimationFrame(() => {
                    const addRow = this.container.querySelector<HTMLElement>(
                        `[data-add-for="${CSS.escape(desc.id)}"]`
                    );
                    addRow?.scrollIntoView({ block: 'nearest' });
                    addRow?.querySelector<HTMLInputElement>('.nti-label-input')?.focus();
                });
            });
            row.appendChild(addBtn);
        }

        // × 삭제 버튼 (루트 제외)
        if (!isRoot) {
            const rmBtn = document.createElement('button');
            rmBtn.className = 'nti-icon-btn remove';
            rmBtn.textContent = '×';
            rmBtn.addEventListener('click', e => {
                e.stopPropagation();
                const kids = parentDesc!.children as NodeDescriptor[];
                const i = kids.indexOf(desc);
                if (i >= 0) { kids.splice(i, 1); this._emit(); this._render(); }
            });
            row.appendChild(rmBtn);
        }

        // ── drop target events ────────────────────────────────────
        row.addEventListener('dragover', (e) => {
            if (!this._dragSrcId || this._dragSrcId === desc.id) return;
            const srcNode = this._findById(this._dragSrcId);
            if (srcNode && this._isDescendant(desc.id, srcNode)) return;
            e.preventDefault();
            e.dataTransfer!.dropEffect = 'move';

            const rect = row.getBoundingClientRect();
            const ratio = (e.clientY - rect.top) / rect.height;
            const canHaveChildren = desc.type !== 'LINK';
            let pos: 'before' | 'after' | 'into';
            if (canHaveChildren && ratio > 0.25 && ratio < 0.75) pos = 'into';
            else pos = ratio < 0.5 ? 'before' : 'after';

            this._dropInfo = { targetId: desc.id, pos };
            this._setDropIndicator(row, pos);
        });
        row.addEventListener('drop', (e) => {
            e.preventDefault();
            if (this._dragSrcId && this._dropInfo) this._applyDrop();
        });

        this.container.appendChild(row);

        if (!isExpanded) return;

        // properties
        const propsWrap = document.createElement('div');
        propsWrap.className = 'nti-props';
        propsWrap.style.paddingLeft = `${8 + (depth + 1) * 14}px`;
        this._renderProps(desc, propsWrap);
        this.container.appendChild(propsWrap);

        // children
        for (const child of (desc.children ?? [])) {
            if (typeof child === 'string') {
                const refRow = document.createElement('div');
                refRow.className = 'nti-ref-row';
                refRow.style.paddingLeft = `${8 + (depth + 1) * 14}px`;
                refRow.textContent = `ref: ${child}`;
                this.container.appendChild(refRow);
            } else {
                this._renderNode(child as NodeDescriptor, depth + 1, desc);
            }
        }

        // add child row
        this.container.appendChild(this._buildAddRow(desc, depth + 1));
    }

    private _renderProps(desc: NodeDescriptor, container: HTMLElement): void {
        const bindings = this._bindings();
        const emit = () => this._emit();
        const rerender = () => this._render();

        if (desc.type === 'LINK') {
            renderLinkProps(desc, container, bindings, this.previewParams, emit, rerender);
        }
        if (desc.type === 'ANCHOR') {
            renderAnchorProps(desc, container, bindings, this.previewParams, emit, rerender);
        }
        if (desc.type === 'JOINT') {
            renderJointProps(desc, container, bindings, this.previewParams, emit);
        }
        renderTransformProps(desc, container, bindings, this.previewParams, emit);
    }

    // ── DnD helpers ───────────────────────────────────────────────

    private _setDropIndicator(row: HTMLElement, pos: 'before' | 'after' | 'into'): void {
        if (this._dropRow && this._dropRow !== row) {
            this._dropRow.classList.remove('nti-drop-before', 'nti-drop-after', 'nti-drop-into');
        }
        row.classList.remove('nti-drop-before', 'nti-drop-after', 'nti-drop-into');
        row.classList.add(`nti-drop-${pos}`);
        this._dropRow = row;
    }

    private _clearDropIndicator(): void {
        this._dropRow?.classList.remove('nti-drop-before', 'nti-drop-after', 'nti-drop-into');
        this._dropRow = null;
    }

    private _applyDrop(): void {
        if (!this.descriptor || !this._dragSrcId || !this._dropInfo) return;
        const { targetId, pos } = this._dropInfo;

        const srcNode = this._findAndRemove(this._dragSrcId, this.descriptor);
        if (!srcNode) return;

        if (pos === 'into') {
            const target = this._findById(targetId);
            if (!target) return;
            (target.children ??= []).push(srcNode);
            this.expanded.add(target.id);
        } else {
            if (!this._insertAdjacent(srcNode, targetId, pos === 'before', this.descriptor)) return;
        }

        this._clearDropIndicator();
        this._dragSrcId = null;
        this._dropInfo = null;
        this._emit();
        this._render();
    }

    private _findById(id: string, desc: NodeDescriptor = this.descriptor!): NodeDescriptor | null {
        if (!desc) return null;
        if (desc.id === id) return desc;
        for (const c of desc.children ?? []) {
            if (typeof c === 'string') continue;
            const found = this._findById(id, c as NodeDescriptor);
            if (found) return found;
        }
        return null;
    }

    private _findAndRemove(id: string, desc: NodeDescriptor): NodeDescriptor | null {
        const kids = desc.children as NodeDescriptor[] | undefined;
        if (!kids) return null;
        const idx = kids.findIndex(c => typeof c !== 'string' && (c as NodeDescriptor).id === id);
        if (idx >= 0) { const [n] = kids.splice(idx, 1); return n as NodeDescriptor; }
        for (const c of kids) {
            if (typeof c === 'string') continue;
            const found = this._findAndRemove(id, c as NodeDescriptor);
            if (found) return found;
        }
        return null;
    }

    private _insertAdjacent(
        node: NodeDescriptor, targetId: string, before: boolean, desc: NodeDescriptor,
    ): boolean {
        const kids = desc.children as NodeDescriptor[] | undefined;
        if (!kids) return false;
        const idx = kids.findIndex(c => typeof c !== 'string' && (c as NodeDescriptor).id === targetId);
        if (idx >= 0) { kids.splice(before ? idx : idx + 1, 0, node); return true; }
        for (const c of kids) {
            if (typeof c === 'string') continue;
            if (this._insertAdjacent(node, targetId, before, c as NodeDescriptor)) return true;
        }
        return false;
    }

    private _isDescendant(id: string, ancestor: NodeDescriptor): boolean {
        for (const c of ancestor.children ?? []) {
            if (typeof c === 'string') continue;
            const cd = c as NodeDescriptor;
            if (cd.id === id || this._isDescendant(id, cd)) return true;
        }
        return false;
    }

    private _buildAddRow(parent: NodeDescriptor, depth: number): HTMLElement {
        const row = document.createElement('div');
        row.className = 'nti-add-row';
        row.dataset['addFor'] = parent.id;
        row.style.paddingLeft = `${8 + depth * 14}px`;

        const sel = document.createElement('select');
        sel.className = 'builder-select';
        sel.style.width = '100px';
        for (const t of ['ANCHOR', 'JOINT', 'LINK']) {
            const opt = document.createElement('option'); opt.value = t; opt.textContent = t;
            sel.appendChild(opt);
        }

        const inp = document.createElement('input');
        inp.className = 'nti-label-input';
        inp.placeholder = 'label';

        const btn = document.createElement('button');
        btn.className = 'nti-icon-btn';
        btn.textContent = '+';
        btn.addEventListener('click', () => {
            const type  = sel.value;
            const label = inp.value.trim() || type.toLowerCase();
            const baseId = `${parent.id}.${label.replace(/[^a-zA-Z0-9_]/g, '_')}`;
            const siblingIds = new Set((parent.children ?? []).map(c => typeof c !== 'string' ? (c as NodeDescriptor).id : ''));
            let id = baseId;
            let n = 2;
            while (siblingIds.has(id)) id = `${baseId}_${n++}`;

            const child: NodeDescriptor = { id, type, label, transform: { position: [0, 0, 0], rotation: [0, 0, 0] } };
            if (type === 'LINK')   child.geometry = { shape: 'Box', color: '#cccccc' };
            if (type === 'ANCHOR') child.layout   = { kind: 'single', exposed: true };
            if (type === 'JOINT')  child.metadata = { axis: 'y', min: -Math.PI, max: Math.PI };

            (parent.children ??= []).push(child);
            this.expanded.add(id);
            inp.value = '';
            this._emit();
            this._render();
        });

        row.appendChild(sel);
        row.appendChild(inp);
        row.appendChild(btn);
        return row;
    }
}
