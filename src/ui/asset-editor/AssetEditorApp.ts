import '../panel.css';
import './asset-editor.css';

import * as THREE from 'three';

import { SceneNode, NodeType } from '../../core/SceneNode';
import { NodeRegistry } from '../../core/NodeRegistry';
import { NodeAssembler, NodeDescriptor, ParameterSchema, ComputedSchema, AnchorLayout } from '../../core/NodeAssembler';

import { NodeTreeInspector } from './NodeTreeInspector';
import { ParameterEditor } from './ParameterEditor';
import { Viewport3D } from './Viewport3D';
import { PreviewParamsPanel } from './PreviewParamsPanel';

export const BROADCAST_CHANNEL = 'plan-asset-editor';

interface AssetOpenMessage {
    type: 'ASSET_OPEN';
    name: string;
    descriptor: unknown;
}

export class AssetEditorApp {
    // ── 에셋 상태 ─────────────────────────────────────────────────
    private sourceDescriptor!: NodeDescriptor;
    private previewParams: Record<string, unknown> = {};
    private currentFilename = 'NewAsset.json';

    // ── UI 요소 ───────────────────────────────────────────────────
    private nameInput!:      HTMLInputElement;
    private sourceTextarea!: HTMLTextAreaElement;
    private anchorListEl!:   HTMLElement;
    private inspector!:      NodeTreeInspector;
    private paramEditor!:    ParameterEditor;
    private viewport!:       Viewport3D;
    private previewPanel!:   PreviewParamsPanel;

    // ── BroadcastChannel ──────────────────────────────────────────
    private channel = new BroadcastChannel(BROADCAST_CHANNEL);

    // ── Draft scene (kept for anchor list) ───────────────────────
    private draftRootNode!: SceneNode;

    constructor() {
        this._buildLayout();
        this._newDraft('NewAsset');
        this._bindMessages();
        this._requestInitialAsset();
    }

    // ── 레이아웃 ──────────────────────────────────────────────────

    private _buildLayout(): void {
        const panel = document.createElement('div');
        panel.id = 'ae-panel';

        // ── Header ──
        const header = document.createElement('div');
        header.className = 'ae-header';
        const title = document.createElement('span');
        title.className = 'ae-header-title';
        title.textContent = 'ASSET EDITOR';
        this.nameInput = document.createElement('input');
        this.nameInput.id = 'ae-name-input';
        this.nameInput.value = 'NewAsset';
        this.nameInput.addEventListener('change', () => {
            const name = this.nameInput.value.trim() || 'NewAsset';
            this.sourceDescriptor.label = name;
            this._syncSource();
        });
        header.appendChild(title);
        header.appendChild(this.nameInput);
        panel.appendChild(header);

        // ── Actions ──
        const actions = document.createElement('div');
        actions.className = 'ae-actions';
        actions.appendChild(this._btn('New',           false, () => this._newDraft(this.nameInput.value.trim() || 'NewAsset')));
        actions.appendChild(this._btn('Load JSON',     false, () => this._loadFromFile()));
        actions.appendChild(this._btn('Save JSON',     true,  () => this._saveJson()));
        actions.appendChild(this._btn('Send to Scene', false, () => this._sendToScene(), 'accent'));
        panel.appendChild(actions);

        // ── Params + Preview Params (collapsible) ──
        const paramsDetails = document.createElement('details');
        paramsDetails.id = 'ae-params-details';
        paramsDetails.open = true;

        const paramsSummary = document.createElement('summary');
        paramsSummary.className = 'ae-params-summary';
        paramsSummary.textContent = 'PARAMETERS & PREVIEW';
        paramsDetails.appendChild(paramsSummary);

        const paramsContent = document.createElement('div');
        paramsContent.id = 'ae-params-content';

        const paramEditorEl = document.createElement('div');
        paramsContent.appendChild(paramEditorEl);

        const previewParamsEl = document.createElement('div');
        paramsContent.appendChild(previewParamsEl);

        paramsDetails.appendChild(paramsContent);
        panel.appendChild(paramsDetails);

        // ── Node Tree ──
        const treeArea = document.createElement('div');
        treeArea.id = 'ae-tree-area';

        const treeTitle = document.createElement('div');
        treeTitle.className = 'ae-section-title';
        treeTitle.textContent = 'NODE TREE';
        treeArea.appendChild(treeTitle);

        const treeContent = document.createElement('div');
        treeContent.id = 'ae-tree-content';
        treeArea.appendChild(treeContent);

        panel.appendChild(treeArea);

        // ── Connection Points ──
        const anchorsSection = document.createElement('div');
        anchorsSection.id = 'ae-anchors-section';

        const anchorsHeader = document.createElement('div');
        anchorsHeader.className = 'ae-anchors-header';

        const anchorsTitle = document.createElement('span');
        anchorsTitle.className = 'ae-anchors-title';
        anchorsTitle.textContent = 'CONNECTION POINTS';

        const toggleWrap = document.createElement('div');
        toggleWrap.className = 'ae-marker-toggles';

        const mkToggle = (label: string, checked: boolean, onChange: (v: boolean) => void) => {
            const lbl = document.createElement('label');
            lbl.className = 'ae-marker-toggle';
            const chk = document.createElement('input');
            chk.type = 'checkbox'; chk.checked = checked;
            chk.addEventListener('change', () => onChange(chk.checked));
            lbl.appendChild(chk);
            lbl.appendChild(document.createTextNode(label));
            return lbl;
        };
        toggleWrap.appendChild(mkToggle(' Anchor', true, v => {
            this.viewport?.setShowAnchorMarkers(v);
        }));
        toggleWrap.appendChild(mkToggle(' Joint', true, v => {
            this.viewport?.setShowJointMarkers(v);
        }));

        anchorsHeader.appendChild(anchorsTitle);
        anchorsHeader.appendChild(toggleWrap);
        anchorsSection.appendChild(anchorsHeader);

        this.anchorListEl = document.createElement('div');
        this.anchorListEl.id = 'ae-anchors-list';
        anchorsSection.appendChild(this.anchorListEl);

        panel.appendChild(anchorsSection);

        // ── Raw JSON (collapsible) ──
        const jsonDetails = document.createElement('details');
        jsonDetails.id = 'ae-json-details';
        const jsonSummary = document.createElement('summary');
        jsonSummary.className = 'ae-json-summary';
        jsonSummary.textContent = 'ASSET DATA (RAW JSON)';
        jsonDetails.appendChild(jsonSummary);

        this.sourceTextarea = document.createElement('textarea');
        this.sourceTextarea.id = 'ae-source-input';
        this.sourceTextarea.spellcheck = false;
        jsonDetails.appendChild(this.sourceTextarea);

        const jsonActions = document.createElement('div');
        jsonActions.className = 'ae-json-actions';
        jsonActions.appendChild(this._btn('Format', false, () => this._formatSource()));
        jsonActions.appendChild(this._btn('Apply',  true,  () => this._applySource()));
        jsonDetails.appendChild(jsonActions);

        panel.appendChild(jsonDetails);

        document.body.appendChild(panel);

        // ── Canvas container ──
        const canvasContainer = document.createElement('div');
        canvasContainer.id = 'ae-canvas-container';

        const hint = document.createElement('div');
        hint.className = 'ae-canvas-hint';
        hint.textContent = 'LMB: rotate  /  RMB: pan  /  Wheel: zoom  /  T: translate  /  R: rotate';
        canvasContainer.appendChild(hint);

        // 선택 모드 토글 (상단 좌측)
        const modeGroup = document.createElement('div');
        modeGroup.className = 'ae-select-mode';
        const modeDefs: Array<['link' | 'joint-anchor', string]> = [
            ['link',          'LINK'],
            ['joint-anchor',  'JOINT · ANCHOR'],
        ];
        modeDefs.forEach(([mode, label]) => {
            const btn = document.createElement('button');
            btn.className = 'ae-mode-btn' + (mode === 'link' ? ' active' : '');
            btn.textContent = label;
            btn.addEventListener('click', () => {
                this.viewport?.setSelectMode(mode);
                modeGroup.querySelectorAll<HTMLElement>('.ae-mode-btn')
                    .forEach(b => b.classList.toggle('active', b === btn));
            });
            modeGroup.appendChild(btn);
        });
        canvasContainer.appendChild(modeGroup);

        const snapLabel = document.createElement('label');
        snapLabel.className = 'ae-snap-toggle';
        const snapChk = document.createElement('input');
        snapChk.type = 'checkbox';
        snapChk.checked = true;
        snapChk.addEventListener('change', () => { this.viewport?.setSnapEnabled(snapChk.checked); });
        snapLabel.appendChild(snapChk);
        snapLabel.appendChild(document.createTextNode(' SNAP'));
        canvasContainer.appendChild(snapLabel);

        document.body.appendChild(canvasContainer);

        // ── Init sub-components ──
        this.paramEditor = new ParameterEditor(
            paramEditorEl,
            (params)   => this._onParamsChange(params),
            (computed) => this._onComputedChange(computed),
        );
        this.inspector = new NodeTreeInspector(treeContent, (desc) => this._onInspectorChange(desc));

        this.previewPanel = new PreviewParamsPanel(previewParamsEl, (key, value) => {
            this.previewParams[key] = value;
            this.inspector.updatePreviewParams(this.previewParams);
            this._rebuildPreview();
        });

        this.viewport = new Viewport3D(canvasContainer, {
            onNodeSelected: (nodeId) => {
                if (nodeId === null) {
                    this.inspector.selectById(null);
                } else {
                    this.inspector.selectById(this._nodeIdToDescId(nodeId));
                }
            },
            onGizmoDragEnd: (nodeId, pos, rot) => {
                const descId = this._nodeIdToDescId(nodeId);
                const desc = this._findDescById(descId);
                if (!desc) return;

                desc.transform = {
                    ...desc.transform,
                    position: [pos.x, pos.y, pos.z],
                    rotation: [rot.x, rot.y, rot.z],
                };

                this._syncSource();
                this._rebuildPreview();
                this.inspector.setDescriptor(this.sourceDescriptor, this.previewParams);
            },
        });
    }

    // ── 드래프트 관리 ────────────────────────────────────────────

    private _newDraft(name: string): void {
        const descriptor: NodeDescriptor = {
            id: this._sanitizeId(name),
            type: 'GROUP',
            label: name,
            transform: { position: [0, 0, 0], rotation: [0, 0, 0] },
            children: [],
        };
        this._setDescriptor(descriptor, name);
        this.currentFilename = `${this._sanitizeId(name)}.json`;
    }

    private _setDescriptor(descriptor: NodeDescriptor, name: string): void {
        const raw = JSON.parse(JSON.stringify(descriptor)) as NodeDescriptor;
        this.sourceDescriptor = this._resolveDefinitions(raw);

        this.previewParams = {};
        for (const [k, p] of Object.entries(this.sourceDescriptor.parameters ?? {})) {
            this.previewParams[k] = p.default;
        }

        this.nameInput.value = name;
        this._rebuildPreview();
        this._syncSource();
        this.paramEditor.setSchema(this.sourceDescriptor.parameters, this.sourceDescriptor.computed);
        this.inspector.setDescriptor(this.sourceDescriptor, this.previewParams);
        this.previewPanel.render(this.sourceDescriptor.parameters ?? {}, this.previewParams);
    }

    private _rebuildPreview(): void {
        const prevNodeId = this.viewport?.getSelectedNodeId() ?? null;

        // detach gizmo before rebuilding
        this.viewport?.detachGizmo();

        NodeRegistry.clear();
        this.draftRootNode = NodeAssembler.materializeInstance(
            this.sourceDescriptor,
            'draft',
            { state: { params: this.previewParams } },
        );
        const draftRoot = this.draftRootNode.object3D;
        this.viewport?.setDraftScene(draftRoot, this.draftRootNode);
        this._updateAnchorList();

        // restore selection if node still exists
        if (prevNodeId && NodeRegistry.get(prevNodeId)) {
            this.viewport?.restoreSelection(prevNodeId);
        }
    }

    // ── Inspector / Param callbacks ───────────────────────────────

    private _onInspectorChange(_descriptor: NodeDescriptor): void {
        this._syncSource();
        this._rebuildPreview();
    }

    private _onParamsChange(params: ParameterSchema): void {
        if (Object.keys(params).length > 0) {
            this.sourceDescriptor.parameters = params;
        } else {
            delete this.sourceDescriptor.parameters;
        }
        const next: Record<string, unknown> = {};
        for (const [k, p] of Object.entries(params)) {
            next[k] = k in this.previewParams ? this.previewParams[k] : p.default;
        }
        this.previewParams = next;
        this._syncSource();
        this.previewPanel.render(this.sourceDescriptor.parameters ?? {}, this.previewParams);
        this._rebuildPreview();
        this.inspector.setDescriptor(this.sourceDescriptor, this.previewParams);
    }

    private _onComputedChange(computed: ComputedSchema): void {
        if (Object.keys(computed).length > 0) {
            this.sourceDescriptor.computed = computed;
        } else {
            delete this.sourceDescriptor.computed;
        }
        this._syncSource();
        this._rebuildPreview();
        this.inspector.setDescriptor(this.sourceDescriptor, this.previewParams);
    }

    // ── Anchor list (stays in AssetEditorApp, uses draftRootNode) ─

    private _collectExposedAnchors(root: SceneNode): SceneNode[] {
        const result: SceneNode[] = [];
        const traverse = (node: SceneNode) => {
            if (node.type === NodeType.ANCHOR) {
                const layout = node.metadata['_layoutDescriptor'] as AnchorLayout | null;
                if (layout?.exposed !== false) result.push(node);
            }
            for (const child of node.children) traverse(child);
        };
        traverse(root);
        return result;
    }

    private _updateAnchorList(): void {
        this.anchorListEl.innerHTML = '';
        if (!this.draftRootNode) return;

        const exposed = this._collectExposedAnchors(this.draftRootNode);
        if (exposed.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'ae-anchors-empty';
            empty.textContent = '노출된 연결 공간 없음';
            this.anchorListEl.appendChild(empty);
            return;
        }

        for (const node of exposed) {
            const worldPos = new THREE.Vector3();
            node.object3D.getWorldPosition(worldPos);

            const row = document.createElement('div');
            row.className = 'ae-anchor-row';

            const dot = document.createElement('span');
            dot.className = 'ae-anchor-dot';

            const lbl = document.createElement('span');
            lbl.className = 'ae-anchor-label';
            lbl.textContent = node.label;

            const pos = document.createElement('span');
            pos.className = 'ae-anchor-pos';
            pos.textContent = `(${worldPos.x.toFixed(2)}, ${worldPos.y.toFixed(2)}, ${worldPos.z.toFixed(2)})`;

            row.appendChild(dot);
            row.appendChild(lbl);
            row.appendChild(pos);
            this.anchorListEl.appendChild(row);
        }
    }

    // ── File I/O ──────────────────────────────────────────────────

    private _loadFromFile(): void {
        const input = document.createElement('input');
        input.type = 'file'; input.accept = '.json';
        input.addEventListener('change', async () => {
            const file = input.files?.[0];
            if (!file) return;
            try {
                const text = await file.text();
                const descriptor = JSON.parse(text) as NodeDescriptor;
                const name = descriptor.label || descriptor.id || 'Loaded';
                this._setDescriptor(descriptor, name);
                this.currentFilename = file.name || `${this._sanitizeId(name)}.json`;
            } catch (err) {
                alert(`Load failed: ${(err as Error).message}`);
            }
        });
        input.click();
    }

    private _saveJson(): void {
        const filename = this._requestFilename();
        if (!filename) return;
        const descriptor = this._readSourceDescriptor();
        if (!descriptor) return;
        const blob = new Blob([JSON.stringify(descriptor, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    }

    private _sendToScene(): void {
        const filename = this._requestFilename();
        if (!filename) return;
        const descriptor = this._readSourceDescriptor();
        if (!descriptor) return;
        const name = filename.replace(/\.json$/i, '');
        descriptor.id    = name;
        descriptor.label = this.sourceDescriptor.label || name;
        this.channel.postMessage({ type: 'ASSET_SAVED', name, filename, descriptor });

        const btn = document.querySelector<HTMLButtonElement>('.ae-btn.accent');
        if (btn) {
            const orig = btn.textContent!;
            btn.textContent = 'Sent ✓'; btn.disabled = true;
            setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 1500);
        }
    }

    // ── BroadcastChannel ─────────────────────────────────────────

    private _bindMessages(): void {
        this.channel.addEventListener('message', (e: MessageEvent) => {
            const data = e.data as Partial<AssetOpenMessage>;
            if (data?.type !== 'ASSET_OPEN' || !data.descriptor || !data.name) return;
            try {
                const descriptor = data.descriptor as NodeDescriptor;
                const name = descriptor.label || descriptor.id || data.name;
                this._setDescriptor(descriptor, name);
                this.currentFilename = `${this._sanitizeId(data.name)}.json`;
            } catch (err) {
                alert(`Asset open failed: ${(err as Error).message}`);
            }
        });
    }

    private _requestInitialAsset(): void {
        const assetName = new URLSearchParams(window.location.search).get('asset');
        if (!assetName) return;
        this.channel.postMessage({ type: 'ASSET_REQUEST', name: assetName });
    }

    // ── Raw JSON ─────────────────────────────────────────────────

    private _syncSource(): void {
        if (!this.sourceTextarea || !this.sourceDescriptor) return;
        this.sourceTextarea.value = JSON.stringify(this.sourceDescriptor, null, 2);
    }

    private _formatSource(): void {
        const descriptor = this._readSourceDescriptor();
        if (!descriptor) return;
        this.sourceTextarea.value = JSON.stringify(descriptor, null, 2);
    }

    private _applySource(): void {
        const descriptor = this._readSourceDescriptor();
        if (!descriptor) return;
        const prevPreview = { ...this.previewParams };
        const name = descriptor.label || descriptor.id || this.nameInput.value.trim() || 'Asset';
        this._setDescriptor(descriptor, name);
        for (const [k, p] of Object.entries(this.sourceDescriptor.parameters ?? {})) {
            if (k in prevPreview) {
                const v = Number(prevPreview[k]);
                const lo = Number(p.min ?? -Infinity);
                const hi = Number(p.max ??  Infinity);
                if (!isNaN(v)) this.previewParams[k] = Math.max(lo, Math.min(hi, v));
            }
        }
        this.previewPanel.render(this.sourceDescriptor.parameters ?? {}, this.previewParams);
        this._rebuildPreview();
        this.inspector.setDescriptor(this.sourceDescriptor, this.previewParams);
    }

    private _readSourceDescriptor(): NodeDescriptor | null {
        try {
            return JSON.parse(this.sourceTextarea.value) as NodeDescriptor;
        } catch (err) {
            alert(`Invalid JSON: ${(err as Error).message}`);
            return null;
        }
    }

    // ── ID helpers ────────────────────────────────────────────────

    private _nodeIdToDescId(nodeId: string): string {
        const rootId = this.sourceDescriptor.id;
        if (nodeId === 'draft') return rootId;
        if (nodeId.startsWith('draft.')) return rootId + nodeId.slice('draft'.length);
        return nodeId;
    }

    private _findDescById(targetId: string, desc: NodeDescriptor = this.sourceDescriptor): NodeDescriptor | null {
        if (desc.id === targetId) return desc;
        for (const child of desc.children ?? []) {
            if (typeof child === 'string') continue;
            const found = this._findDescById(targetId, child as NodeDescriptor);
            if (found) return found;
        }
        return null;
    }

    // ── definitions + string ref → 완전한 인라인 중첩 구조로 변환
    private _resolveDefinitions(descriptor: NodeDescriptor): NodeDescriptor {
        const defs = descriptor.definitions;
        if (!defs || Object.keys(defs).length === 0) return descriptor;

        const resolveNode = (desc: NodeDescriptor): NodeDescriptor => {
            const children: NodeDescriptor[] = [];
            for (const child of desc.children ?? []) {
                if (typeof child === 'string') {
                    const found = defs[child];
                    if (found) children.push(resolveNode(found));
                    else console.warn(`resolveDefinitions: "${child}" not found in definitions`);
                } else {
                    children.push(resolveNode(child as NodeDescriptor));
                }
            }
            const result: NodeDescriptor = { ...desc };
            if (children.length > 0) result.children = children;
            else delete result.children;
            delete result.definitions;
            return result;
        };

        return resolveNode(descriptor);
    }

    // ── Helpers ───────────────────────────────────────────────────

    private _requestFilename(): string | null {
        const fallback = this.currentFilename || `${this._sanitizeId(this.sourceDescriptor?.label || 'asset')}.json`;
        const input = prompt('Asset filename', fallback);
        if (input === null) return null;
        const name = this._sanitizeId(input.replace(/\.json$/i, ''));
        if (!name) { alert('Enter a filename.'); return null; }
        return (this.currentFilename = `${name}.json`);
    }

    private _sanitizeId(value: string): string {
        return value.trim().replace(/[^a-zA-Z0-9_-]/g, '_') || 'asset';
    }

    private _btn(text: string, primary: boolean, onClick: () => void, extra?: string): HTMLButtonElement {
        const btn = document.createElement('button');
        btn.className = 'ae-btn' + (primary ? ' primary' : '') + (extra ? ` ${extra}` : '');
        btn.textContent = text;
        btn.addEventListener('click', onClick);
        return btn;
    }
}
