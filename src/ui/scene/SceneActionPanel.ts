import { SceneNode } from '../../core/SceneNode';
import { AssetManager } from '../../core/AssetManager';
import { NodeRegistry } from '../../core/NodeRegistry';
import { SceneSerializer } from '../../core/SceneSerializer';
import { SceneDeserializer } from '../../core/SceneDeserializer';

interface FileSystemWritableFileStream {
    write(data: Blob): Promise<void>;
    close(): Promise<void>;
}

interface FileSystemFileHandle {
    createWritable(): Promise<FileSystemWritableFileStream>;
}

interface SaveFilePickerOptions {
    suggestedName?: string;
    types?: Array<{
        description: string;
        accept: Record<string, string[]>;
    }>;
}

type WindowWithSavePicker = Window & {
    showSaveFilePicker?: (options?: SaveFilePickerOptions) => Promise<FileSystemFileHandle>;
};

export class SceneActionPanel {
    private container: HTMLElement;
    private assetManager: AssetManager;
    private sceneRoot: SceneNode | null = null;
    private onLoad: (root: SceneNode) => void;

    constructor(
        container: HTMLElement,
        assetManager: AssetManager,
        onLoad: (root: SceneNode) => void,
    ) {
        this.container = container;
        this.assetManager = assetManager;
        this.onLoad = onLoad;
        this._render();
    }

    setRoot(root: SceneNode): void {
        this.sceneRoot = root;
    }

    private _render(): void {
        this.container.innerHTML = '';

        const section = document.createElement('div');
        section.className = 'preset-row';
        section.style.margin = '0';
        section.style.padding = '8px 12px';
        section.style.flexWrap = 'wrap';

        const saveBtn = document.createElement('button');
        saveBtn.className = 'preset-btn primary';
        saveBtn.textContent = 'Save Scene';
        saveBtn.addEventListener('click', () => { void this._export(); });

        const loadBtn = document.createElement('button');
        loadBtn.className = 'preset-btn';
        loadBtn.textContent = 'Load Scene';
        loadBtn.addEventListener('click', () => this._triggerImport());

        section.appendChild(saveBtn);
        section.appendChild(loadBtn);
        this.container.appendChild(section);
    }

    private async _export(): Promise<void> {
        if (!this.sceneRoot) return;
        const snapshot = SceneSerializer.serialize(this.sceneRoot);
        const json = JSON.stringify(snapshot, null, 2);
        const blob = new Blob([json], { type: 'application/json' });

        const picker = (window as WindowWithSavePicker).showSaveFilePicker;
        if (picker) {
            try {
                const handle = await picker({
                    suggestedName: 'scene_export.json',
                    types: [
                        {
                            description: 'PLAN Scene JSON',
                            accept: { 'application/json': ['.json'] },
                        },
                    ],
                });
                const writable = await handle.createWritable();
                await writable.write(blob);
                await writable.close();
                return;
            } catch (err) {
                if ((err as DOMException).name === 'AbortError') return;
                console.error('SceneActionPanel: save picker failed', err);
                alert(`Save failed: ${(err as Error).message}`);
                return;
            }
        }

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'scene_export.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    private _triggerImport(): void {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.addEventListener('change', async () => {
            const file = input.files?.[0];
            if (!file) return;
            const text = await file.text();
            try {
                const snapshot = JSON.parse(text);
                NodeRegistry.clear();
                const root = await SceneDeserializer.load(
                    snapshot,
                    name => this.assetManager.getModel(name),
                );
                this.sceneRoot = root;
                this.onLoad(root);
            } catch (err) {
                console.error('SceneActionPanel: import failed', err);
                alert(`Import failed: ${(err as Error).message}`);
            }
        });
        input.click();
    }
}
