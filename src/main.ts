import './ui/panel.css';
import { SceneEditorApp } from './SceneEditorApp';
import { AssetManager } from './core/AssetManager';
import type { NodeDescriptor, SceneSnapshot } from './core/NodeAssembler';

// Vite 환경에서 폴더 내의 기본 에셋들을 자동으로 가져와 번들에 포함 (선택적)
const assetModules = import.meta.glob('./asset/*/*/*.json', { eager: true });
const presetModules = import.meta.glob('./presets/*.json', { eager: true });

async function bootstrap() {
    const assetManager = new AssetManager();

    // 1. 기본 제공 Asset 등록: ./asset/<대분류>/<소분류>/<asset>.json
    for (const [path, module] of Object.entries(assetModules)) {
        const parts = path.split('/');
        const name = parts.at(-1)!.replace('.json', '');
        const category = parts.at(-3) ?? 'general';
        const subcategory = parts.at(-2) ?? 'general';
        assetManager.registerModel(name, (module as any).default as NodeDescriptor, {
            category,
            subcategory,
        });
    }

    // 2. 기본 제공 Scene Presets 등록
    for (const [path, module] of Object.entries(presetModules)) {
        const name = path.split('/').pop()!.replace('.json', '');
        assetManager.registerPreset(name, (module as any).default as SceneSnapshot);
    }

    /* 
     * 추가 요구사항 구현: 런타임에 외부 경로에서 비동기로 에셋 로드 가능.
     * 예시:
     * await assetManager.loadModelFromUrl('http://my-server.com/asset/custom_robot.json');
     * await assetManager.loadPresetFromUrl('http://my-server.com/presets/factory_line.json', 'factory_line');
     */

    // AssetManager를 주입하여 앱 초기화
    const app = new SceneEditorApp(assetManager);
    
    // conveyor_line 씬으로 시작
    await app.start('conveyor_line');

    const loading = document.getElementById('loading');
    if (loading) loading.style.display = 'none';
}

window.onload = () => bootstrap().catch(console.error);
