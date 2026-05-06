import { SceneNode, NodeType } from '../core/SceneNode';
import { NodeRegistry } from '../core/NodeRegistry';
import { NodeFactory } from '../core/NodeFactory';

const BADGE_COLORS: Record<NodeType, string> = {
    [NodeType.GROUP]:   'badge-GROUP',
    [NodeType.ANCHOR]:  'badge-ANCHOR',
    [NodeType.JOINT]:   'badge-JOINT',
    [NodeType.LINK]:    'badge-LINK',
};

export class NodeComposer {
    private container: HTMLElement;
    private targetNode: SceneNode | null = null;
    private selectedId: string | null = null;
    private onSelect: (node: SceneNode) => void;
    private onChange?: () => void;

    constructor(container: HTMLElement, onSelect: (node: SceneNode) => void, onChange?: () => void) {
        this.container = container;
        this.onSelect  = onSelect;
        this.onChange  = onChange;
    }

    render(target: SceneNode): void {
        this.targetNode = target;
        this.container.innerHTML = '';

        const section = document.createElement('div');
        section.className = 'panel-section';

        const title = document.createElement('div');
        title.className = 'panel-section-title';
        title.textContent = `NODE TREE  — ${target.label}`;
        section.appendChild(title);

        this._renderTree(target, section, 0);

        this.container.appendChild(section);
    }

    private _renderTree(node: SceneNode, container: HTMLElement, depth: number): void {
        // Hide nested GROUP subtrees; only the target GROUP and its non-GROUP descendants are shown.
        if (node !== this.targetNode && node.type === NodeType.GROUP) return;

        container.appendChild(this._buildRow(node, depth));

        for (const child of node.children) {
            this._renderTree(child, container, depth + 1);
        }

        // Add-child form sits at one indent deeper than this node's row.
        container.appendChild(this._buildAddForm(node, depth + 1));
    }

    private _buildRow(node: SceneNode, depth: number): HTMLElement {
        const isTarget = node === this.targetNode;
        const row = document.createElement('div');
        row.className = 'composer-row' + (node.id === this.selectedId ? ' selected' : '');
        row.style.paddingLeft = `${depth * 16}px`;

        const badge = document.createElement('span');
        badge.className = `tree-badge ${BADGE_COLORS[node.type]}`;
        badge.textContent = node.type;

        const label = document.createElement('span');
        label.className = 'composer-row-label';
        label.textContent = node.label;

        row.appendChild(badge);
        row.appendChild(label);

        // 타겟 GROUP은 본인을 삭제할 수 없으므로 remove 버튼을 숨긴다.
        if (!isTarget) {
            const removeBtn = document.createElement('button');
            removeBtn.className = 'composer-icon-btn remove';
            removeBtn.textContent = '×';
            removeBtn.title = 'Remove node';
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this._removeNode(node);
            });
            row.appendChild(removeBtn);
        }

        row.addEventListener('click', () => {
            this.selectedId = node.id;
            this.container.querySelectorAll<HTMLElement>('.composer-row').forEach(r => {
                r.classList.toggle('selected', r === row);
            });
            this.onSelect(node);
        });

        return row;
    }

    private _buildAddForm(parent: SceneNode, depth: number): HTMLElement {
        const row = document.createElement('div');
        row.className = 'add-child-row';
        row.style.paddingLeft = `${depth * 16}px`;

        const typeSelect = document.createElement('select');
        typeSelect.className = 'builder-select';
        typeSelect.style.width = '110px';
        for (const t of [NodeType.ANCHOR, NodeType.JOINT, NodeType.LINK]) {
            const opt = document.createElement('option');
            opt.value = t; opt.textContent = t;
            typeSelect.appendChild(opt);
        }

        const labelInput = document.createElement('input');
        labelInput.placeholder = 'label';

        const addBtn = document.createElement('button');
        addBtn.className = 'composer-icon-btn';
        addBtn.textContent = '+';
        addBtn.title = 'Add child node';
        addBtn.addEventListener('click', () => {
            const type  = typeSelect.value as NodeType;
            const label = labelInput.value.trim() || type.toLowerCase();
            this._addChild(parent, type, label);
            labelInput.value = '';
        });

        row.appendChild(typeSelect);
        row.appendChild(labelInput);
        row.appendChild(addBtn);
        return row;
    }

    private _addChild(parent: SceneNode, type: NodeType, label: string): void {
        // 고유 id 생성: parent.id + "." + label (중복 방지용 suffix)
        let id = `${parent.id}.${label}`;
        let suffix = 1;
        while (NodeRegistry.has(id)) { id = `${parent.id}.${label}_${suffix++}`; }

        const group = NodeFactory.build(null);
        const child = new SceneNode(id, label, type, group);
        // 타입에 맞는 디스크립터만 초기화 (GROUP은 둘 다 비워둔다).
        if (type === NodeType.LINK) {
            child.metadata['_geometryDescriptor'] = null;
        } else if (type === NodeType.ANCHOR) {
            child.metadata['_layoutDescriptor'] = { kind: 'single' };
        } else if (type === NodeType.JOINT) {
            child.metadata['axis'] = 'y';
            child.metadata['min']  = -Math.PI;
            child.metadata['max']  =  Math.PI;
        }
        child.metadata['_defaultRotation'] = [0, 0, 0];
        child.metadata['_defaultPosition'] = [0, 0, 0];
        NodeRegistry.register(child);
        parent.addChild(child);

        if (this.targetNode) this.render(this.targetNode);
        this.selectedId = child.id;
        this.onSelect(child);
        if (this.onChange) this.onChange();
    }

    private _removeNode(node: SceneNode): void {
        // NodeRegistry에서 하위 트리 전체 제거
        for (const n of node.flatten()) NodeRegistry.unregister(n);
        node.parent?.removeChild(node);
        if (this.selectedId === node.id) this.selectedId = null;
        if (this.targetNode) this.render(this.targetNode);
        if (this.onChange) this.onChange();
    }
}
