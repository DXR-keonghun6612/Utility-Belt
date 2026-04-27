import { SceneNode, NodeType } from '../core/SceneNode';
import { NodeFactory } from '../core/NodeFactory';
import { NodeComposer } from './NodeComposer';
import { GeometryEditor } from './GeometryEditor';
import { NodeDescriptor } from '../core/NodeAssembler';

function applyDraftToNode(node: SceneNode, editor: GeometryEditor): void {
    if (node.type === NodeType.LINK) {
        const draft = editor.getGeometryDraft();
        if (!draft.shape) return;
        NodeFactory.rebuildInPlace(node.object3D, draft);
        node.metadata['_geometryDescriptor'] = draft;
    } else if (node.type === NodeType.JOINT) {
        const draft = editor.getLayoutDraft();
        NodeFactory.applyLayout(node.object3D, draft);
        node.metadata['_layoutDescriptor'] = draft;
    }
    // GROUP: no shape/layout to persist; transform-only
}

export class BuilderPanel {
    private container: HTMLElement;
    private roots: SceneNode[] = [];
    private _targetNode: SceneNode | null = null;
    private editNode:   SceneNode | null = null;
    private onChange?: () => void;

    private targetEl!:   HTMLElement;
    private composerEl!: HTMLElement;
    private editorEl!:   HTMLElement;

    private composer!:   NodeComposer;
    private geoEditor!:  GeometryEditor;

    constructor(container: HTMLElement, onChange?: () => void) {
        this.container = container;
        this.onChange = onChange;
        this._build();
    }

    setRoots(roots: SceneNode[]): void {
        this.roots = roots;
        this._refreshTargetSelector();
    }

    private _build(): void {
        this.container.innerHTML = '';

        // ── Target selector ───────────────────────
        const targetSection = document.createElement('div');
        targetSection.className = 'panel-section';
        const targetTitle = document.createElement('div');
        targetTitle.className = 'panel-section-title';
        targetTitle.textContent = 'TARGET NODE';
        this.targetEl = document.createElement('div');
        this.targetEl.className = 'builder-drilldown';
        targetSection.appendChild(targetTitle);
        targetSection.appendChild(this.targetEl);
        this.container.appendChild(targetSection);

        // ── Node Composer ─────────────────────────
        this.composerEl = document.createElement('div');
        this.composerEl.style.flex = '1';
        this.composerEl.style.overflowY = 'auto';
        this.composerEl.style.minHeight = '150px';
        this.composer = new NodeComposer(this.composerEl, (node) => {
            this.editNode = node;
            this.geoEditor.show(node);
            this.editorEl.style.display = 'block';
        }, this.onChange);
        this.container.appendChild(this.composerEl);

        // ── Geometry Editor ───────────────────────
        this.editorEl = document.createElement('div');
        this.editorEl.className = 'panel-section';
        this.editorEl.style.display = 'none';
        this.editorEl.style.flex = '1';
        this.editorEl.style.overflowY = 'auto';
        this.geoEditor = new GeometryEditor(this.editorEl, (_node) => {
            // live: 슬라이더 이동은 transform/layout에 직접 반영됨 (no-op here)
        });
        this.container.appendChild(this.editorEl);

        // ── Action buttons ────────────────────────
        const actions = document.createElement('div');
        actions.className = 'builder-actions';

        const previewBtn = document.createElement('button');
        previewBtn.className = 'preset-btn primary';
        previewBtn.textContent = 'Rebuild Preview';
        previewBtn.addEventListener('click', () => this._rebuild());

        const applyBtn = document.createElement('button');
        applyBtn.className = 'preset-btn';
        applyBtn.textContent = 'Apply';
        applyBtn.addEventListener('click', () => this._apply());

        const saveAssetBtn = document.createElement('button');
        saveAssetBtn.className = 'preset-btn primary';
        saveAssetBtn.textContent = 'Save Asset';
        saveAssetBtn.addEventListener('click', () => this._saveAsset());

        actions.appendChild(previewBtn);
        actions.appendChild(applyBtn);
        actions.appendChild(saveAssetBtn);
        this.container.appendChild(actions);
    }

    private _refreshTargetSelector(): void {
        const oldTargetId = this._targetNode?.id;

        this.targetEl.innerHTML = '';
        if (this.roots.length === 0) return;

        // 모든 GROUP 노드 수집
        const allGroups: SceneNode[] = [];
        for (const root of this.roots) {
            for (const n of root.flatten()) {
                if (n.type === NodeType.GROUP) {
                    allGroups.push(n);
                }
            }
        }

        // Group 선택 드롭다운
        const groupSelect = document.createElement('select');
        groupSelect.className = 'builder-select';
        
        for (const g of allGroups) {
            const opt = document.createElement('option');
            opt.value = g.id;
            opt.textContent = g.label;
            groupSelect.appendChild(opt);
        }

        groupSelect.addEventListener('change', () => {
            const node = allGroups.find(n => n.id === groupSelect.value) ?? null;
            this._setTarget(node);
        });

        this.targetEl.appendChild(groupSelect);
        
        const preservedTarget = allGroups.find(g => g.id === oldTargetId);
        if (preservedTarget) {
            groupSelect.value = preservedTarget.id;
            if (this._targetNode !== preservedTarget) {
                this._setTarget(preservedTarget);
            } else {
                // If it's the exact same target, just re-render composer to pick up tree changes
                this.composer.render(this._targetNode);
            }
        } else if (allGroups.length > 0) {
            this._setTarget(allGroups[0]);
        } else {
            this._setTarget(null);
        }
    }

    private _setTarget(node: SceneNode | null): void {
        this._targetNode = node;
        if (this._targetNode) {
            this.composer.render(this._targetNode);
            // 타겟 GROUP 자체의 layout을 바로 편집할 수 있도록 에디터를 연다.
            this.editNode = this._targetNode;
            this.geoEditor.show(this._targetNode);
            this.editorEl.style.display = 'block';
        } else {
            this.editNode = null;
            this.editorEl.style.display = 'none';
            this.composerEl.innerHTML = '';
        }
    }

    private _rebuild(): void {
        if (!this.editNode) return;
        applyDraftToNode(this.editNode, this.geoEditor);
    }

    private _apply(): void {
        if (!this.editNode) return;
        applyDraftToNode(this.editNode, this.geoEditor);

        const pos = this.editNode.object3D.position;
        const rot = this.editNode.object3D.rotation;
        this.editNode.metadata['_defaultPosition'] = [pos.x, pos.y, pos.z];
        this.editNode.metadata['_defaultRotation'] = [rot.x, rot.y, rot.z];

        if (this.onChange) this.onChange();
    }

    private _saveAsset(): void {
        if (!this._targetNode) return;
        
        const descriptor = this._serializeGroup(this._targetNode, true);
        if (!descriptor) return;

        const json = JSON.stringify(descriptor, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this._targetNode.label || 'asset'}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    private _serializeGroup(node: SceneNode, isRoot: boolean): NodeDescriptor | null {
        // 하위 GROUP 노드는 직렬화하지 않음
        if (!isRoot && node.type === NodeType.GROUP) return null;

        const pos = node.object3D.position;
        const rot = node.object3D.rotation;
        
        const descriptor: NodeDescriptor = {
            id: isRoot ? node.label || node.id : node.id.split('.').pop() || node.id,
            type: node.type,
            label: node.label,
        };

        // root 노드가 아니거나 위치/회전값이 있는 경우에만 transform 추가
        // root여도 내부적인 기본 transform이 있으면 포함
        descriptor.transform = {
            position: [pos.x, pos.y, pos.z],
            rotation: [rot.x, rot.y, rot.z],
        };

        const metadata = { ...node.metadata };
        const geometry = metadata['_geometryDescriptor'];
        const layout   = metadata['_layoutDescriptor'];

        delete metadata['_geometryDescriptor'];
        delete metadata['_layoutDescriptor'];
        delete metadata['_defaultPosition'];
        delete metadata['_defaultRotation'];

        if (node.type === NodeType.LINK && geometry) {
            descriptor.geometry = geometry as any;
        } else if (node.type === NodeType.JOINT && layout) {
            descriptor.layout = layout as any;
        }

        if (Object.keys(metadata).length > 0) {
            descriptor.metadata = metadata;
        }

        const children: NodeDescriptor[] = [];
        for (const child of node.children) {
            const childDesc = this._serializeGroup(child, false);
            if (childDesc) {
                children.push(childDesc);
            }
        }
        
        if (children.length > 0) {
            descriptor.children = children;
        }

        return descriptor;
    }
}
