import './panel.css';
import './asset-editor.css';

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import { SceneNode, NodeType } from '../core/SceneNode';
import { NodeRegistry } from '../core/NodeRegistry';
import { NodeFactory } from '../core/NodeFactory';
import { NodeAssembler } from '../core/NodeAssembler';
import { NodeDescriptorExporter } from '../core/NodeDescriptorExporter';

import { NodeComposer } from './NodeComposer';
import { GeometryEditor } from './GeometryEditor';

export const BROADCAST_CHANNEL = 'plan-asset-editor';

export class AssetEditorApp {
    // ── Three.js ──────────────────────────────────────────
    private scene!:    THREE.Scene;
    private camera!:   THREE.PerspectiveCamera;
    private renderer!: THREE.WebGLRenderer;
    private controls!: OrbitControls;

    // ── 에셋 상태 ─────────────────────────────────────────
    private draftRoot!: SceneNode;
    private editNode:   SceneNode | null = null;

    // ── UI 요소 ───────────────────────────────────────────
    private nameInput!:   HTMLInputElement;
    private composerEl!:  HTMLElement;
    private editorEl!:    HTMLElement;
    private composer!:    NodeComposer;
    private geoEditor!:   GeometryEditor;

    // ── BroadcastChannel ──────────────────────────────────
    private channel = new BroadcastChannel(BROADCAST_CHANNEL);

    constructor() {
        this._buildLayout();
        this._initEngine();
        this._newDraft('NewAsset');
        this._animate();
    }

    // ── 레이아웃 구성 ──────────────────────────────────────

    private _buildLayout(): void {
        // 왼쪽 패널
        const panel = document.createElement('div');
        panel.id = 'ae-panel';

        // 헤더 (타이틀 + 에셋 이름 입력)
        const header = document.createElement('div');
        header.className = 'ae-header';
        const title = document.createElement('span');
        title.className = 'ae-header-title';
        title.textContent = 'ASSET EDITOR';
        this.nameInput = document.createElement('input');
        this.nameInput.id = 'ae-name-input';
        this.nameInput.value = 'NewAsset';
        this.nameInput.addEventListener('change', () => {
            this.draftRoot.label = this.nameInput.value.trim() || 'NewAsset';
        });
        header.appendChild(title);
        header.appendChild(this.nameInput);
        panel.appendChild(header);

        // 액션 버튼
        const actions = document.createElement('div');
        actions.className = 'ae-actions';
        actions.appendChild(this._btn('New',        false, () => this._newDraft(this.nameInput.value.trim() || 'NewAsset')));
        actions.appendChild(this._btn('Load JSON',  false, () => this._loadFromFile()));
        actions.appendChild(this._btn('Save JSON',  true,  () => this._saveJson()));
        actions.appendChild(this._btn('Send to Scene', false, () => this._sendToScene(), 'accent'));
        panel.appendChild(actions);

        // NodeComposer 영역
        this.composerEl = document.createElement('div');
        this.composerEl.id = 'ae-composer';
        panel.appendChild(this.composerEl);

        // GeometryEditor 영역
        this.editorEl = document.createElement('div');
        this.editorEl.id = 'ae-editor';
        panel.appendChild(this.editorEl);

        // Apply 바
        const applyBar = document.createElement('div');
        applyBar.className = 'ae-apply-bar';
        applyBar.appendChild(this._btn('Rebuild Preview', true,  () => this._rebuild()));
        applyBar.appendChild(this._btn('Apply',           false, () => this._apply()));
        panel.appendChild(applyBar);

        document.body.appendChild(panel);

        // 오른쪽 캔버스 컨테이너
        const canvasContainer = document.createElement('div');
        canvasContainer.id = 'ae-canvas-container';
        const hint = document.createElement('div');
        hint.className = 'ae-canvas-hint';
        hint.textContent = 'LMB: rotate  /  RMB: pan  /  Wheel: zoom';
        canvasContainer.appendChild(hint);
        document.body.appendChild(canvasContainer);

        // 컴포저 / 에디터 초기화
        this.composer = new NodeComposer(this.composerEl, (node) => {
            this.editNode = node;
            this.geoEditor.show(node);
        });
        this.geoEditor = new GeometryEditor(this.editorEl, () => {/* live: no-op */});
    }

    // ── Three.js 엔진 ─────────────────────────────────────

    private _initEngine(): void {
        const container = document.getElementById('ae-canvas-container')!;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color('#1a1e28');

        this.camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
        this.camera.position.set(0, 8, 20);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(container.clientWidth, container.clientHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(this.renderer.domElement);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.set(0, 2, 0);
        this.controls.update();

        this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const dir = new THREE.DirectionalLight(0xffffff, 0.6);
        dir.position.set(10, 20, 15);
        dir.castShadow = true;
        this.scene.add(dir);

        const grid = new THREE.GridHelper(40, 40, 0x333344, 0x333344);
        this.scene.add(grid);

        window.addEventListener('resize', () => {
            const w = container.clientWidth;
            const h = container.clientHeight;
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(w, h);
        });
    }

    private _animate(): void {
        requestAnimationFrame(this._animate.bind(this));
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    // ── 드래프트 관리 ──────────────────────────────────────

    private _newDraft(name: string): void {
        if (this.draftRoot) {
            this.scene.remove(this.draftRoot.object3D);
        }
        NodeRegistry.clear();

        const group = new THREE.Group();
        this.draftRoot = new SceneNode('draft', name, NodeType.GROUP, group);
        NodeRegistry.register(this.draftRoot);

        this.nameInput.value = name;
        this.editNode = null;
        this.scene.add(this.draftRoot.object3D);
        this._refreshComposer();
    }

    private _refreshComposer(): void {
        this.composer.render(this.draftRoot);
    }

    // ── 파일 I/O ──────────────────────────────────────────

    private _loadFromFile(): void {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.addEventListener('change', async () => {
            const file = input.files?.[0];
            if (!file) return;
            try {
                const text = await file.text();
                const descriptor = JSON.parse(text);
                const name = descriptor.label || descriptor.id || 'Loaded';

                if (this.draftRoot) this.scene.remove(this.draftRoot.object3D);
                NodeRegistry.clear();

                this.draftRoot = NodeAssembler.load(descriptor, 'draft');
                this.draftRoot.label = name;
                this.nameInput.value = name;

                this.scene.add(this.draftRoot.object3D);
                this.editNode = null;
                this._refreshComposer();
            } catch (err) {
                alert(`Load failed: ${(err as Error).message}`);
            }
        });
        input.click();
    }

    private _saveJson(): void {
        const descriptor = NodeDescriptorExporter.export(this.draftRoot);
        const json = JSON.stringify(descriptor, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.draftRoot.label || 'asset'}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    private _sendToScene(): void {
        const name       = this.draftRoot.label || 'asset';
        const descriptor = NodeDescriptorExporter.export(this.draftRoot);
        this.channel.postMessage({ type: 'ASSET_SAVED', name, descriptor });

        // 전송 피드백
        const btn = document.querySelector<HTMLButtonElement>('.ae-btn.accent');
        if (btn) {
            const orig = btn.textContent!;
            btn.textContent = 'Sent ✓';
            btn.disabled = true;
            setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 1500);
        }
    }

    // ── 편집 액션 ─────────────────────────────────────────

    private _rebuild(): void {
        if (!this.editNode) return;
        this._applyDraftToNode(this.editNode);
    }

    private _apply(): void {
        if (!this.editNode) return;
        this._applyDraftToNode(this.editNode);

        const pos = this.editNode.object3D.position;
        const rot = this.editNode.object3D.rotation;
        this.editNode.metadata['_defaultPosition'] = [pos.x, pos.y, pos.z];
        this.editNode.metadata['_defaultRotation'] = [rot.x, rot.y, rot.z];
    }

    private _applyDraftToNode(node: SceneNode): void {
        if (node.type === NodeType.LINK) {
            const draft = this.geoEditor.getGeometryDraft();
            if (!draft.shape) return;
            NodeFactory.rebuildInPlace(node.object3D, draft);
            node.metadata['_geometryDescriptor'] = draft;
        } else if (node.type === NodeType.ANCHOR) {
            const draft = this.geoEditor.getLayoutDraft();
            NodeFactory.applyLayout(node.object3D, draft);
            node.metadata['_layoutDescriptor'] = draft;
        }
    }

    // ── 헬퍼 ─────────────────────────────────────────────

    private _btn(
        text: string,
        primary: boolean,
        onClick: () => void,
        extra?: string,
    ): HTMLButtonElement {
        const btn = document.createElement('button');
        btn.className = 'ae-btn' + (primary ? ' primary' : '') + (extra ? ` ${extra}` : '');
        btn.textContent = text;
        btn.addEventListener('click', onClick);
        return btn;
    }
}
