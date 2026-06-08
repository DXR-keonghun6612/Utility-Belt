import { SceneNode, NodeType } from '../../core/SceneNode';
import { AssetManager } from '../../core/AssetManager';
import { AnchorLayout } from '../../core/NodeAssembler';
import { AssetSelect } from '../assets/AssetSelect';

const BADGE_CLASS: Record<NodeType, string> = {
    [NodeType.GROUP]:   'badge-GROUP',
    [NodeType.ANCHOR]:  'badge-ANCHOR',
    [NodeType.JOINT]:   'badge-JOINT',
    [NodeType.LINK]:    'badge-LINK',
};

export class SceneGraphPanel {
    private container: HTMLElement;
    private assetManager: AssetManager;
    private onSelect: (node: SceneNode) => void;
    private onRemoveNode?: (node: SceneNode) => void;
    private onReparentNode?: (node: SceneNode, newParent: SceneNode) => void;
    private onAddRoot?: (modelName: string) => void;
    private onAttachToAnchor?: (anchor: SceneNode, modelName: string, slotIndex?: number) => void;
    private onClearAnchor?: (anchor: SceneNode, slotIndex?: number) => void;
    private expanded = new Set<string>();
    private selectedId: string | null = null;
    private dragSourceNode: SceneNode | null = null;
    private activePicker: { nodeId: string; mode: 'root' | 'anchor'; root: SceneNode; slotIndex?: number } | null = null;
    private currentSceneRoot: SceneNode | null = null;

    constructor(
        container: HTMLElement,
        assetManager: AssetManager,
        onSelect: (node: SceneNode) => void,
        _onAddChild?: (node: SceneNode) => void,
        onRemoveNode?: (node: SceneNode) => void,
        onReparentNode?: (node: SceneNode, newParent: SceneNode) => void,
        onAddRoot?: (modelName: string) => void,
        onAttachToAnchor?: (anchor: SceneNode, modelName: string, slotIndex?: number) => void,
        onClearAnchor?: (anchor: SceneNode, slotIndex?: number) => void,
    ) {
        this.container = container;
        this.assetManager = assetManager;
        this.onSelect = onSelect;
        this.onRemoveNode = onRemoveNode;
        this.onReparentNode = onReparentNode;
        this.onAddRoot = onAddRoot;
        this.onAttachToAnchor = onAttachToAnchor;
        this.onClearAnchor = onClearAnchor;
    }

    render(roots: SceneNode[]): void {
        this.currentSceneRoot = roots[0] ?? null;
        this.container.innerHTML = '';
        const section = document.createElement('div');
        section.className = 'panel-section';
        const title = this._sectionTitle();
        section.appendChild(title);

        if (this.currentSceneRoot && this.activePicker?.mode === 'root') {
            section.appendChild(this._buildAssetPicker(this.currentSceneRoot, 'root'));
        }

        const instances = this.currentSceneRoot?.children.filter(c => c.metadata['_modelName'] !== undefined) ?? [];
        if (instances.length === 0) {
            const empty = document.createElement('div');
            empty.style.cssText = 'color:#7a8494; padding:8px 0; font-size:11px;';
            empty.textContent = 'No scene instances.';
            section.appendChild(empty);
        }

        for (const instance of instances) {
            section.appendChild(this._buildNode(instance, 0));
        }
        this.container.appendChild(section);
    }

    highlight(node: SceneNode): void {
        // JOINT/LINK는 트리에 표시되지 않으므로 가장 가까운 GROUP/ANCHOR 조상으로 대체
        const treeNode = this._nearestTreeNode(node);
        this.selectedId = treeNode.id;
        this.container.querySelectorAll<HTMLElement>('.tree-row').forEach(row => {
            row.classList.toggle('selected', row.dataset['nodeId'] === treeNode.id);
        });
        this._ensureVisible(treeNode);
    }

    private _nearestTreeNode(node: SceneNode): SceneNode {
        let cur: SceneNode | null = node;
        while (cur) {
            if (cur.type === NodeType.GROUP || cur.type === NodeType.ANCHOR) return cur;
            cur = cur.parent;
        }
        return node;
    }

    private _buildNode(node: SceneNode, _depth: number): HTMLElement {
        const wrapper = document.createElement('div');
        wrapper.className = 'tree-node';

        const row = document.createElement('div');
        row.className = 'tree-row' + (node.id === this.selectedId ? ' selected' : '');
        row.dataset['nodeId'] = node.id;

        const visibleChildren = this._getVisibleChildren(node);
        const slotRows = node.type === NodeType.ANCHOR ? this._buildSlotRows(node) : [];
        const hasChildren = visibleChildren.length > 0 || slotRows.length > 0;

        // Toggle arrow
        const toggle = document.createElement('span');
        toggle.className = 'tree-toggle';
        toggle.textContent = hasChildren
            ? (this.expanded.has(node.id) ? '▼' : '▶')
            : '·';
        row.appendChild(toggle);

        // Label
        const label = document.createElement('span');
        label.className = 'tree-label';
        label.textContent = node.label;
        row.appendChild(label);

        // Type badge
        const badge = document.createElement('span');
        badge.className = `tree-badge ${BADGE_CLASS[node.type]}`;
        badge.textContent = node.type;
        row.appendChild(badge);

        this._appendTreeActions(row, node);

        if (node.type === NodeType.GROUP && node.parent) {
            const removeBtn = document.createElement('span');
            removeBtn.className = 'tree-remove-btn';
            removeBtn.innerHTML = '&times;';
            removeBtn.title = 'Remove this group';
            removeBtn.style.cursor = 'pointer';
            removeBtn.style.marginLeft = '4px';
            removeBtn.style.color = '#ff6b6b';
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm(`Remove group "${node.label}"?`) && this.onRemoveNode) {
                    this.onRemoveNode(node);
                }
            });
            row.appendChild(removeBtn);
        }

        // Drag and Drop
        if (node.type === NodeType.GROUP && node.parent) {
            row.draggable = true;
            row.addEventListener('dragstart', (e) => {
                this.dragSourceNode = node;
                if (e.dataTransfer) {
                    e.dataTransfer.effectAllowed = 'move';
                    e.dataTransfer.setData('text/plain', node.id);
                }
                row.classList.add('dragging');
            });
            row.addEventListener('dragend', () => {
                this.dragSourceNode = null;
                row.classList.remove('dragging');
                this.container.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
            });
        }

        if (node.type === NodeType.GROUP || node.type === NodeType.ANCHOR || node.type === NodeType.JOINT) {
            row.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (this.dragSourceNode && this.dragSourceNode !== node && !this._isDescendant(this.dragSourceNode, node)) {
                    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
                    row.classList.add('drag-over');
                } else {
                    if (e.dataTransfer) e.dataTransfer.dropEffect = 'none';
                }
            });
            row.addEventListener('dragleave', () => {
                row.classList.remove('drag-over');
            });
            row.addEventListener('drop', (e) => {
                e.preventDefault();
                row.classList.remove('drag-over');
                if (this.dragSourceNode && this.dragSourceNode !== node && !this._isDescendant(this.dragSourceNode, node)) {
                    if (this.onReparentNode) {
                        this.onReparentNode(this.dragSourceNode, node);
                    }
                }
            });
        }

        wrapper.appendChild(row);

        if (
            this.activePicker?.nodeId === node.id &&
            this.activePicker.mode === 'anchor' &&
            this.activePicker.slotIndex === undefined
        ) {
            wrapper.appendChild(this._buildAssetPicker(node, this.activePicker.mode));
        }

        // Children container
        const childrenEl = document.createElement('div');
        childrenEl.className = 'tree-children';
        childrenEl.style.display = this.expanded.has(node.id) ? 'block' : 'none';
        for (const child of visibleChildren) {
            childrenEl.appendChild(this._buildNode(child, _depth + 1));
        }
        for (const slot of slotRows) childrenEl.appendChild(slot);
        wrapper.appendChild(childrenEl);

        // Events
        row.addEventListener('click', (e) => {
            e.stopPropagation();
            if (hasChildren) {
                const open = this.expanded.has(node.id);
                open ? this.expanded.delete(node.id) : this.expanded.add(node.id);
                toggle.textContent = open ? '▶' : '▼';
                childrenEl.style.display = open ? 'none' : 'block';
            }
            this.selectedId = node.id;
            this.container.querySelectorAll<HTMLElement>('.tree-row').forEach(r => {
                r.classList.toggle('selected', r.dataset['nodeId'] === node.id);
            });
            this.onSelect(node);
        });

        return wrapper;
    }

    private _appendTreeActions(row: HTMLElement, node: SceneNode): void {
        if (node.type === NodeType.ANCHOR) {
            const layout = node.metadata['_layoutDescriptor'] as AnchorLayout | null;
            if (layout?.kind === 'array') return;

            const attached = node.children.filter(c => c.metadata['_modelName'] !== undefined);
            if (attached.length === 0 && this.onAttachToAnchor) {
                row.appendChild(this._actionButton('+', 'Attach instance to anchor', () => {
                    const root = this._getRoot(node);
                    this.activePicker = { nodeId: node.id, mode: 'anchor', root };
                    this.render([root]);
                }));
            } else if (attached.length > 0 && this.onClearAnchor) {
                row.appendChild(this._actionButton('×', 'Remove attached instance(s)', () => {
                    if (!confirm(`Clear ${attached.length} attached instance(s) from "${node.label}"?`)) return;
                    this.onClearAnchor?.(node);
                }));
            }
        }
    }

    private _actionButton(text: string, title: string, onClick: () => void): HTMLElement {
        const btn = document.createElement('span');
        btn.className = 'tree-remove-btn';
        btn.textContent = text;
        btn.title = title;
        btn.style.cursor = 'pointer';
        btn.style.marginLeft = '4px';
        btn.style.color = text === '×' ? '#ef9a9a' : '#a5d6a7';
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            onClick();
        });
        return btn;
    }

    private _sectionTitle(): HTMLElement {
        const row = document.createElement('div');
        row.className = 'panel-section-title';
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.alignItems = 'center';
        const text = document.createElement('span');
        text.textContent = 'SCENE GRAPH';
        row.appendChild(text);

        if (this.currentSceneRoot && this.onAddRoot) {
            row.appendChild(this._actionButton('+', 'Add root instance', () => {
                this.activePicker = {
                    nodeId: this.currentSceneRoot!.id,
                    mode: 'root',
                    root: this.currentSceneRoot!,
                };
                this.render([this.currentSceneRoot!]);
            }));
        }

        return row;
    }

    private _buildSlotRows(anchor: SceneNode): HTMLElement[] {
        const layout = anchor.metadata['_layoutDescriptor'] as AnchorLayout | null;
        if (layout?.kind !== 'array') return [];

        const count = Math.max(0, Math.floor(Number(layout.count ?? 0)));
        const rows: HTMLElement[] = [];

        for (let index = 0; index < count; index += 1) {
            const attached = this._slotChild(anchor, index);
            const row = document.createElement('div');
            row.className = 'tree-action-row';
            row.style.cssText = 'display:flex; align-items:center; gap:4px; padding:3px 0 3px 22px; color:#8899aa; font-size:11px;';
            row.dataset['nodeId'] = `${anchor.id}:slot:${index}`;

            const label = document.createElement('span');
            label.style.flex = '1';
            label.textContent = attached
                ? `slot ${index}: ${String(attached.metadata['_modelName'] ?? attached.label)}`
                : `slot ${index}: empty`;
            row.appendChild(label);

            if (attached) {
                row.appendChild(this._actionButton('×', `Clear slot ${index}`, () => {
                    this.onClearAnchor?.(anchor, index);
                }));
            } else {
                row.appendChild(this._actionButton('+', `Attach to slot ${index}`, () => {
                    const root = this._getRoot(anchor);
                    this.activePicker = { nodeId: anchor.id, mode: 'anchor', root, slotIndex: index };
                    this.render([root]);
                }));
            }

            if (this.activePicker?.nodeId === anchor.id && this.activePicker.slotIndex === index) {
                const picker = this._buildAssetPicker(anchor, 'anchor');
                picker.style.paddingLeft = '22px';
                const wrapper = document.createElement('div');
                wrapper.appendChild(row);
                wrapper.appendChild(picker);
                rows.push(wrapper);
            } else {
                rows.push(row);
            }
        }

        return rows;
    }

    private _buildAssetPicker(node: SceneNode, mode: 'root' | 'anchor'): HTMLElement {
        const row = document.createElement('div');
        row.className = 'tree-action-row';
        row.style.cssText = 'display:flex; gap:4px; align-items:center; padding:4px 0 4px 22px;';

        const selector = new AssetSelect(this.assetManager);

        const addBtn = document.createElement('button');
        addBtn.className = 'preset-btn primary';
        addBtn.style.cssText = 'flex:0; padding:3px 8px; font-size:10px;';
        addBtn.textContent = mode === 'root' ? 'Add' : 'Attach';
        addBtn.addEventListener('click', () => {
            const modelName = selector.value();
            if (!modelName) return;
            const slotIndex = this.activePicker?.slotIndex;
            this.activePicker = null;
            if (mode === 'root') {
                this.onAddRoot?.(modelName);
            } else {
                this.onAttachToAnchor?.(node, modelName, slotIndex);
            }
        });

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'preset-btn';
        cancelBtn.style.cssText = 'flex:0; padding:3px 8px; font-size:10px;';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', () => {
            this.activePicker = null;
            this.render([mode === 'root' ? node : this._getRoot(node)]);
        });

        row.appendChild(selector.element);
        row.appendChild(addBtn);
        row.appendChild(cancelBtn);
        return row;
    }

    private _getRoot(node: SceneNode): SceneNode {
        let cur = node;
        while (cur.parent) cur = cur.parent;
        return cur;
    }

    private _isDescendant(parent: SceneNode, child: SceneNode): boolean {
        let cur: SceneNode | null = child.parent;
        while (cur) {
            if (cur === parent) return true;
            cur = cur.parent;
        }
        return false;
    }

    private _getVisibleChildren(node: SceneNode): SceneNode[] {
        if (node.type === NodeType.ANCHOR) {
            const layout = node.metadata['_layoutDescriptor'] as AnchorLayout | null;
            if (layout?.kind === 'array') return [];
            return node.children.filter(child => child.metadata['_modelName'] !== undefined);
        }

        if (node.type !== NodeType.GROUP) return [];

        // GROUP: JOINT/LINK를 투명하게 통과하며 노출된 ANCHOR만 수집
        const flatList: SceneNode[] = [];
        const traverse = (n: SceneNode) => {
            for (const child of n.children) {
                if (child.metadata['_modelName'] !== undefined) continue; // 부착 인스턴스는 ANCHOR에서 처리
                if (child.type === NodeType.ANCHOR) {
                    if (this._isExposedAnchor(child)) flatList.push(child);
                } else {
                    traverse(child); // JOINT, LINK — 투명하게 통과
                }
            }
        };
        traverse(node);
        return flatList;
    }

    private _isExposedAnchor(node: SceneNode): boolean {
        const layout = node.metadata['_layoutDescriptor'] as AnchorLayout | null;
        return layout?.exposed !== false;
    }

    private _slotChild(anchor: SceneNode, slotIndex: number): SceneNode | null {
        return anchor.children.find(child =>
            child.metadata['_modelName'] !== undefined &&
            Number(child.metadata['_slotIndex'] ?? 0) === slotIndex,
        ) ?? null;
    }

    private _ensureVisible(target: SceneNode): void {
        let cur: SceneNode | null = target.parent;
        while (cur) {
            if (!this.expanded.has(cur.id)) {
                this.expanded.add(cur.id);
                // 이미 렌더된 DOM을 직접 열어준다
                const row = this.container.querySelector<HTMLElement>(`[data-node-id="${cur.id}"]`);
                const toggle = row?.querySelector<HTMLElement>('.tree-toggle');
                const childrenEl = row?.parentElement?.querySelector<HTMLElement>('.tree-children');
                if (toggle && toggle.textContent !== '·') toggle.textContent = '▼';
                if (childrenEl) childrenEl.style.display = 'block';
            }
            cur = cur.parent;
        }
    }
}
