import { SceneNode } from './core/SceneNode';
import { NodeRegistry } from './core/NodeRegistry';
import { SceneDeserializer } from './core/SceneDeserializer';
import { NodeAssembler, type SceneSnapshot, type NodeDescriptor, type AnchorLayout } from './core/NodeAssembler';
import { AssetManager } from './core/AssetManager';
import { BROADCAST_CHANNEL } from './ui/asset-editor/AssetEditorApp';

import { TabManager }         from './ui/app/TabManager';
import { SceneGraphPanel }    from './ui/scene/SceneGraphPanel';
import { SceneInspectorPanel } from './ui/scene/SceneInspectorPanel';
import { SceneViewport }      from './ui/scene/SceneViewport';
import { SceneActionPanel }   from './ui/scene/SceneActionPanel';
import { InstanceBuilderPanel } from './ui/builder/InstanceBuilderPanel';
import { AssetTreePanel }     from './ui/assets/AssetTreePanel';

export class SceneEditorApp {
    private viewport!:   SceneViewport;
    private sceneRoot!:  SceneNode;

    private tabManager!:    TabManager;
    private graphPanel!:    SceneGraphPanel;
    private sceneInspector!: SceneInspectorPanel;
    private sceneActionPanel!: SceneActionPanel;
    private builderPanel!:  InstanceBuilderPanel;
    private assetTreePanel!: AssetTreePanel;

    private assetManager: AssetManager;

    constructor(assetManager: AssetManager) {
        this.assetManager = assetManager;
        this.initUI();
        this.bindEvents();
    }

    public async start(initialPresetName?: string): Promise<void> {
        if (initialPresetName) {
            const snapshot = this.assetManager.getPreset(initialPresetName);
            await this.loadScene(snapshot);
        } else {
            await this.loadScene({ version: 1, scene: [] });
        }
    }

    // ── UI ───────────────────────────────────────────

    private initUI(): void {
        this.tabManager = new TabManager();

        const canvasContainer = document.createElement('div');
        canvasContainer.id = 'scene-canvas-container';
        canvasContainer.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;';
        document.body.appendChild(canvasContainer);

        this.viewport = new SceneViewport(canvasContainer, {
            onNodeSelected: (nodeId) => {
                if (!nodeId) return;
                const node = NodeRegistry.get(nodeId);
                if (node) this.onSelect(node);
            },
            onGizmoDragEnd: (_nodeId, _pos, _rot) => {
                // SceneNode.object3D가 이미 업데이트됨 — inspector만 갱신
                const nodeId = this.viewport.getSelectedNodeId();
                if (!nodeId) return;
                const node = NodeRegistry.get(nodeId);
                if (node) this.sceneInspector.show(node);
            },
        });

        this.graphPanel = new SceneGraphPanel(
            this.tabManager.sceneTreePane,
            this.assetManager,
            (node) => this.onSelect(node),
            undefined,
            (node) => this.onRemoveNode(node),
            (node, newParent) => this.onReparentNode(node, newParent),
            (modelName) => this.onAddRootModel(modelName),
            (anchor, modelName, slotIndex) => this.onAttachToAnchor(anchor, modelName, slotIndex),
            (anchor, slotIndex) => this.onClearAnchor(anchor, slotIndex),
        );

        this.sceneInspector = new SceneInspectorPanel(
            this.tabManager.sceneInspectorPane,
            (anchor, layout) => this.onAnchorLayoutChanged(anchor, layout),
        );
        this.sceneInspector.clear();

        this.sceneActionPanel = new SceneActionPanel(
            this.tabManager.sceneActionPane,
            this.assetManager,
            (root) => this.onSceneReloaded(root),
        );

        this.builderPanel = new InstanceBuilderPanel(
            this.tabManager.tabs['builder'],
            this.assetManager,
            (root) => this.onBuilderRebuilt(root),
        );

        this.assetTreePanel = new AssetTreePanel(
            this.tabManager.tabs['assets'],
            this.assetManager,
            (name) => this.openAssetEditor(name),
            () => this.openNewAssetEditor(),
        );

    }

    // ── Scene ────────────────────────────────────────

    private onRemoveNode(node: SceneNode): void {
        if (!node.parent) {
            console.warn('Cannot remove the root node.');
            return;
        }
        node.parent.removeChild(node);

        for (const n of node.flatten()) NodeRegistry.unregister(n);

        this.sceneInspector.clear();
        this.builderPanel.setSelection(null);
        this.refreshPanels();
    }

    private onReparentNode(node: SceneNode, newParent: SceneNode): void {
        if (node.parent === newParent) return;
        
        // prevent circular parenting
        let cur: SceneNode | null = newParent;
        while (cur) {
            if (cur === node) {
                console.warn('Cannot reparent a node to its own descendant.');
                return;
            }
            cur = cur.parent;
        }

        if (node.parent) {
            node.parent.removeChild(node);
        }
        newParent.addChild(node);
        this.refreshPanels();
        this.onSelect(node, true);
    }

    private async loadScene(snapshot: SceneSnapshot): Promise<void> {
        NodeRegistry.clear();
        this.sceneRoot = await SceneDeserializer.load(
            snapshot,
            (name) => this.assetManager.getModel(name)
        );
        this.viewport.setSceneRoot(this.sceneRoot.object3D, this.sceneRoot);
        this.refreshPanels();
    }

    private onSceneReloaded(root: SceneNode): void {
        this.sceneRoot = root;
        this.viewport.setSceneRoot(root.object3D, root);
        this.sceneInspector.clear();
        this.builderPanel.setSelection(null);
        this.refreshPanels();
    }

    private onRootAdded(root: SceneNode): void {
        this.refreshPanels();
        this.onSelect(root, true);
    }

    private async onAddRootModel(modelName: string): Promise<void> {
        const descriptor = this.assetManager.getModel(modelName);
        const root = NodeAssembler.materializeInstance(
            descriptor,
            this.nextInstanceId(modelName),
            { modelName },
        );
        await SceneDeserializer.populateDefaultAnchors(
            root,
            (name) => this.assetManager.getModel(name),
        );
        this.sceneRoot.addChild(root);
        this.onRootAdded(root);
    }

    private onAttachToAnchor(anchor: SceneNode, modelName: string, slotIndex?: number): void {
        if (slotIndex !== undefined) {
            this.clearAnchorSlot(anchor, slotIndex);
        }

        const descriptor = this.assetManager.getModel(modelName);
        const child = NodeAssembler.materializeInstance(
            descriptor,
            this.nextInstanceId(`${anchor.id}_s${slotIndex ?? 0}_${modelName}`),
            { modelName },
        );
        child.metadata['_slotIndex'] = slotIndex ?? 0;
        this.applyAnchorSlotTransform(anchor, child, slotIndex ?? 0);
        anchor.addChild(child);
        this.refreshPanels();
        this.onSelect(anchor, true);
    }

    private onClearAnchor(anchor: SceneNode, slotIndex?: number): void {
        const attached = anchor.children.filter(c =>
            c.metadata['_modelName'] !== undefined &&
            (slotIndex === undefined || Number(c.metadata['_slotIndex'] ?? 0) === slotIndex),
        );
        for (const child of attached) {
            for (const n of child.flatten()) NodeRegistry.unregister(n);
            anchor.removeChild(child);
        }
        this.refreshPanels();
        this.onSelect(anchor, true);
    }

    private clearAnchorSlot(anchor: SceneNode, slotIndex: number): void {
        const attached = anchor.children.filter(c =>
            c.metadata['_modelName'] !== undefined &&
            Number(c.metadata['_slotIndex'] ?? 0) === slotIndex,
        );
        for (const child of attached) {
            for (const n of child.flatten()) NodeRegistry.unregister(n);
            anchor.removeChild(child);
        }
    }

    private applyAnchorSlotTransform(anchor: SceneNode, child: SceneNode, slotIndex: number): void {
        const layout = anchor.metadata['_layoutDescriptor'] as AnchorLayout | null;
        if (!layout || layout.kind !== 'array') return;

        const gap = Number(layout.gap ?? 2);
        const start = Number(layout.start ?? 0);
        const axis = layout.axis ?? 'x';
        const axisIndex = axis === 'x' ? 0 : axis === 'y' ? 1 : 2;
        const pos: [number, number, number] = [0, 0, 0];
        pos[axisIndex] = start + slotIndex * gap;
        child.object3D.position.set(...pos);
        child.object3D.rotation.set(0, 0, 0);
    }

    private nextInstanceId(seed: string): string {
        const base = seed.replace(/[^a-zA-Z0-9_]/g, '_') || 'model';
        let index = 1;
        let id = `${base}_${index}`;
        while (NodeRegistry.has(id)) {
            index += 1;
            id = `${base}_${index}`;
        }
        return id;
    }

    private refreshPanels(): void {
        this.graphPanel.render([this.sceneRoot]);
        this.sceneActionPanel.setRoot(this.sceneRoot);
        this.builderPanel.setSceneRoot(this.sceneRoot);
    }

    private async onBuilderRebuilt(root: SceneNode): Promise<void> {
        await SceneDeserializer.populateDefaultAnchors(
            root,
            (name) => this.assetManager.getModel(name),
        );
        this.refreshPanels();
        this.onSelect(root);
    }

    private onAnchorLayoutChanged(anchor: SceneNode, layout: AnchorLayout): void {
        const root = this.findInstanceRoot(anchor);
        if (!root) return;

        NodeAssembler.updateInstanceState(root, {
            anchorOverrides: {
                [anchor.id]: { layout },
            },
        });
        this.refreshPanels();
        this.onSelect(anchor);
    }

    // ── Selection ────────────────────────────────────

    private onSelect(node: SceneNode, focusSceneTab = false): void {
        this.sceneInspector.show(node);
        this.graphPanel.highlight(node);
        this.builderPanel.setSelection(node);
        if (focusSceneTab) this.tabManager.switchTo('scene');
    }

    private findInstanceRoot(node: SceneNode): SceneNode | null {
        let cur: SceneNode | null = node;
        while (cur) {
            if (cur.metadata['_modelName'] !== undefined) return cur;
            cur = cur.parent;
        }
        return null;
    }

    private openAssetEditor(modelName: string): void {
        window.open(`/asset-editor.html?asset=${encodeURIComponent(modelName)}`, '_blank');
    }

    private openNewAssetEditor(): void {
        window.open('/asset-editor.html', '_blank');
    }

    // ── Loop ─────────────────────────────────────────

    private bindEvents(): void {
        // Asset Editor 탭에서 전송된 에셋을 AssetManager에 등록
        const channel = new BroadcastChannel(BROADCAST_CHANNEL);
        channel.addEventListener('message', (e: MessageEvent) => {
            if (e.data?.type === 'ASSET_REQUEST') {
                const { name } = e.data as { name: string };
                try {
                    channel.postMessage({
                        type: 'ASSET_OPEN',
                        name,
                        descriptor: this.assetManager.getModel(name),
                    });
                } catch (err) {
                    this._showToast((err as Error).message);
                }
                return;
            }

            if (e.data?.type !== 'ASSET_SAVED') return;
            const { name, descriptor } = e.data as { name: string; descriptor: NodeDescriptor };
            this.assetManager.registerModel(name, descriptor);
            this.assetTreePanel.render();
            this._showToast(`Asset "${name}" registered`);
        });
    }

    private _showToast(msg: string): void {
        const el = document.createElement('div');
        el.style.cssText = `
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            background: #004d5f; border: 1px solid #00bcd4; color: #00bcd4;
            font-family: monospace; font-size: 12px; padding: 6px 16px;
            border-radius: 4px; z-index: 9999; pointer-events: none;
        `;
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 2500);
    }

}
