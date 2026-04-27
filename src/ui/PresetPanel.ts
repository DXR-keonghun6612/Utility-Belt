import { SceneNode } from '../core/SceneNode';
import { SceneSerializer } from '../core/SceneSerializer';
import { SceneDeserializer, ModelLoader } from '../core/SceneDeserializer';
import { NodeRegistry } from '../core/NodeRegistry';

export class PresetPanel {
    private container: HTMLElement;
    private sceneRoot: SceneNode | null = null;
    private modelLoader: ModelLoader;
    private onLoad: (root: SceneNode) => void;

    constructor(
        container: HTMLElement,
        modelLoader: ModelLoader,
        onLoad: (root: SceneNode) => void,
    ) {
        this.container   = container;
        this.modelLoader = modelLoader;
        this.onLoad      = onLoad;
        this._render();
    }

    setRoot(root: SceneNode): void {
        this.sceneRoot = root;
    }

    private _render(): void {
        const row = document.createElement('div');
        row.className = 'preset-row';
        row.style.margin = '0';
        row.style.padding = '8px 12px';

        const saveBtn = document.createElement('button');
        saveBtn.className = 'preset-btn primary';
        saveBtn.textContent = 'Save Scene';
        saveBtn.addEventListener('click', () => this._export());

        const loadBtn = document.createElement('button');
        loadBtn.className = 'preset-btn';
        loadBtn.textContent = 'Load Scene';
        loadBtn.addEventListener('click', () => this._triggerImport());

        row.appendChild(saveBtn);
        row.appendChild(loadBtn);

        this.container.appendChild(row);
    }

    private _export(): void {
        if (!this.sceneRoot) return;
        const snapshot = SceneSerializer.serialize(this.sceneRoot);
        const json     = JSON.stringify(snapshot, null, 2);
        const blob     = new Blob([json], { type: 'application/json' });
        const url      = URL.createObjectURL(blob);
        const a        = document.createElement('a');
        a.href         = url;
        a.download     = 'scene_export.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    private _triggerImport(): void {
        const input   = document.createElement('input');
        input.type    = 'file';
        input.accept  = '.json';
        input.addEventListener('change', async () => {
            const file = input.files?.[0];
            if (!file) return;
            const text = await file.text();
            try {
                const snapshot = JSON.parse(text);
                NodeRegistry.clear();
                const root = await SceneDeserializer.load(snapshot, this.modelLoader);
                this.sceneRoot = root;
                this.onLoad(root);
            } catch (err) {
                console.error('PresetPanel: import failed', err);
                alert(`Import failed: ${(err as Error).message}`);
            }
        });
        input.click();
    }
}
