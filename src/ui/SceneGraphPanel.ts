import { SceneNode, NodeType } from '../core/SceneNode';

const BADGE_CLASS: Record<NodeType, string> = {
    [NodeType.GROUP]:   'badge-GROUP',
    [NodeType.JOINT]:   'badge-JOINT',
    [NodeType.LINK]:    'badge-LINK',
};

export class SceneGraphPanel {
    private container: HTMLElement;
    private onSelect: (node: SceneNode) => void;
    private onAddChild?: (node: SceneNode) => void;
    private onRemoveNode?: (node: SceneNode) => void;
    private onReparentNode?: (node: SceneNode, newParent: SceneNode) => void;
    private expanded = new Set<string>();
    private selectedId: string | null = null;
    private dragSourceNode: SceneNode | null = null;

    constructor(
        container: HTMLElement,
        onSelect: (node: SceneNode) => void,
        onAddChild?: (node: SceneNode) => void,
        onRemoveNode?: (node: SceneNode) => void,
        onReparentNode?: (node: SceneNode, newParent: SceneNode) => void,
    ) {
        this.container = container;
        this.onSelect = onSelect;
        this.onAddChild = onAddChild;
        this.onRemoveNode = onRemoveNode;
        this.onReparentNode = onReparentNode;
    }

    render(roots: SceneNode[]): void {
        this.container.innerHTML = '';
        const section = document.createElement('div');
        section.className = 'panel-section';
        const title = document.createElement('div');
        title.className = 'panel-section-title';
        title.textContent = 'SCENE GRAPH';
        section.appendChild(title);
        for (const root of roots) {
            section.appendChild(this._buildNode(root, 0));
        }
        this.container.appendChild(section);
    }

    highlight(node: SceneNode): void {
        this.selectedId = node.id;
        this.container.querySelectorAll<HTMLElement>('.tree-row').forEach(row => {
            row.classList.toggle('selected', row.dataset['nodeId'] === node.id);
        });
        // Auto-expand ancestors
        this._ensureVisible(node);
    }

    private _buildNode(node: SceneNode, _depth: number): HTMLElement {
        const wrapper = document.createElement('div');
        wrapper.className = 'tree-node';

        const row = document.createElement('div');
        row.className = 'tree-row' + (node.id === this.selectedId ? ' selected' : '');
        row.dataset['nodeId'] = node.id;

        const visibleChildren = this._getVisibleChildren(node);
        const hasChildren = visibleChildren.length > 0;

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

        if (node.type === NodeType.JOINT) {
            const addBtn = document.createElement('span');
            addBtn.className = 'tree-add-btn';
            addBtn.textContent = '+';
            addBtn.title = 'Mount model to this joint';
            addBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.onAddChild) {
                    this.onAddChild(node);
                }
            });
            row.appendChild(addBtn);
        }

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

        if (node.type === NodeType.GROUP || node.type === NodeType.JOINT) {
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

        // Children container
        const childrenEl = document.createElement('div');
        childrenEl.className = 'tree-children';
        childrenEl.style.display = this.expanded.has(node.id) ? 'block' : 'none';
        for (const child of visibleChildren) {
            childrenEl.appendChild(this._buildNode(child, _depth + 1));
        }
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

    private _isDescendant(parent: SceneNode, child: SceneNode): boolean {
        let cur: SceneNode | null = child.parent;
        while (cur) {
            if (cur === parent) return true;
            cur = cur.parent;
        }
        return false;
    }

    private _getVisibleChildren(node: SceneNode): SceneNode[] {
        if (node.type === NodeType.GROUP) {
            const flatList: SceneNode[] = [];
            const traverse = (n: SceneNode) => {
                for (const child of n.children) {
                    if (child.type === NodeType.GROUP) {
                        flatList.push(child);
                        // Do not traverse into nested GROUPs
                    } else if (child.type === NodeType.JOINT) {
                        flatList.push(child);
                        traverse(child); // Continue traversing to find other joints/groups
                    } else { // LINK
                        traverse(child);
                    }
                }
            };
            traverse(node);
            return flatList;
        }
        return [];
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
