import { NodeDescriptor, SceneSnapshot } from './NodeAssembler';

export class AssetManager {
    private _models = new Map<string, NodeDescriptor>();
    private _presets = new Map<string, SceneSnapshot>();

    // 1. 메모리에 직접 등록 (내부 번들 또는 glob 처리용)
    registerModel(name: string, descriptor: NodeDescriptor): void {
        this._models.set(name, descriptor);
    }

    registerPreset(name: string, snapshot: SceneSnapshot): void {
        this._presets.set(name, snapshot);
    }

    // 2. 이름으로 로드 (동기 반환, 모델 조립 시 호출됨)
    getModel(name: string): NodeDescriptor {
        const desc = this._models.get(name);
        if (!desc) throw new Error(`AssetManager: Model "${name}" not found`);
        return desc;
    }

    getPreset(name: string): SceneSnapshot {
        const snap = this._presets.get(name);
        if (!snap) throw new Error(`AssetManager: Preset "${name}" not found`);
        return snap;
    }

    getAllPresetNames(): string[] {
        return Array.from(this._presets.keys());
    }

    getAllModelNames(): string[] {
        return Array.from(this._models.keys());
    }

    // 3. 외부 경로(URL)로부터 비동기 로드 (사용자가 경로를 입력하여 확장할 때 사용)
    async loadModelFromUrl(url: string, name?: string): Promise<NodeDescriptor> {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Failed to load model from ${url}`);
        const data = (await res.json()) as NodeDescriptor;
        const modelName = name ?? data.id;
        this.registerModel(modelName, data);
        return data;
    }

    async loadPresetFromUrl(url: string, name: string): Promise<SceneSnapshot> {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Failed to load preset from ${url}`);
        const data = (await res.json()) as SceneSnapshot;
        this.registerPreset(name, data);
        return data;
    }
}
