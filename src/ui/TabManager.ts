import './panel.css';

export type TabId = 'scene' | 'builder';

export class TabManager {
    readonly panel: HTMLElement;
    readonly tabs: Record<TabId, HTMLElement>;
    /** Scene 탭 내 상단: SceneGraphPanel이 렌더링되는 영역 */
    readonly sceneTreePane: HTMLElement;
    /** Scene 탭 내 상단 바로 아래: 액션(저장 등) 버튼이 렌더링되는 영역 */
    readonly sceneActionPane: HTMLElement;
    /** Scene 탭 내 하단: PropertiesPanel이 렌더링되는 영역 */
    readonly sceneInspectorPane: HTMLElement;

    private _active: TabId = 'scene';

    constructor() {
        this.panel = document.createElement('div');
        this.panel.id = 'scene-panel';

        // Lateral resize handle
        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'panel-resize-handle';
        this.panel.appendChild(resizeHandle);

        // Tab bar
        const bar = document.createElement('div');
        bar.className = 'tab-bar';
        const labels: [TabId, string][] = [
            ['scene',   'SCENE'],
            ['builder', 'BUILDER'],
        ];
        for (const [id, text] of labels) {
            const btn = document.createElement('button');
            btn.className = 'tab-btn' + (id === this._active ? ' active' : '');
            btn.textContent = text;
            btn.dataset['tab'] = id;
            btn.addEventListener('click', () => this.switchTo(id));
            bar.appendChild(btn);
        }
        this.panel.appendChild(bar);

        // Scene tab: split layout (tree top / action / divider / inspector bottom)
        const sceneContent = document.createElement('div');
        sceneContent.className = 'tab-content active';
        sceneContent.id = 'tab-scene';

        this.sceneTreePane = document.createElement('div');
        this.sceneTreePane.className = 'scene-tree-pane';

        this.sceneActionPane = document.createElement('div');
        this.sceneActionPane.className = 'scene-action-pane';

        const divider = document.createElement('div');
        divider.className = 'scene-pane-divider';

        this.sceneInspectorPane = document.createElement('div');
        this.sceneInspectorPane.className = 'scene-inspector-pane';

        sceneContent.appendChild(this.sceneTreePane);
        sceneContent.appendChild(this.sceneActionPane);
        sceneContent.appendChild(divider);
        sceneContent.appendChild(this.sceneInspectorPane);
        this.panel.appendChild(sceneContent);

        // Builder tab
        const builderContent = document.createElement('div');
        builderContent.className = 'tab-content';
        builderContent.id = 'tab-builder';
        this.panel.appendChild(builderContent);

        this.tabs = {
            scene:   sceneContent,
            builder: builderContent,
        };

        document.body.appendChild(this.panel);

        // --- Resize Logic ---
        
        // 1. Vertical Split Resize
        let isVerticalDragging = false;
        let startY = 0;
        let startHeight = 0;

        divider.addEventListener('mousedown', (e) => {
            isVerticalDragging = true;
            startY = e.clientY;
            startHeight = this.sceneTreePane.offsetHeight;
            document.body.style.cursor = 'ns-resize';
        });

        // 2. Horizontal Panel Resize
        let isHorizontalDragging = false;
        let startX = 0;
        let startWidth = 0;

        resizeHandle.addEventListener('mousedown', (e) => {
            isHorizontalDragging = true;
            startX = e.clientX;
            startWidth = this.panel.offsetWidth;
            document.body.style.cursor = 'ew-resize';
        });

        window.addEventListener('mousemove', (e) => {
            if (isVerticalDragging) {
                const dy = e.clientY - startY;
                let newHeight = startHeight + dy;
                const maxH = this.panel.offsetHeight * 0.8;
                const minH = 100;
                if (newHeight < minH) newHeight = minH;
                if (newHeight > maxH) newHeight = maxH;
                this.sceneTreePane.style.height = `${newHeight}px`;
            }

            if (isHorizontalDragging) {
                // Dragging from right edge towards left increases width
                const dx = startX - e.clientX;
                let newWidth = startWidth + dx;
                const maxW = window.innerWidth * 0.8;
                const minW = 200;
                if (newWidth < minW) newWidth = minW;
                if (newWidth > maxW) newWidth = maxW;
                this.panel.style.width = `${newWidth}px`;
            }
        });

        window.addEventListener('mouseup', () => {
            if (isVerticalDragging || isHorizontalDragging) {
                isVerticalDragging = false;
                isHorizontalDragging = false;
                document.body.style.cursor = '';
            }
        });
    }

    switchTo(id: TabId): void {
        this._active = id;
        this.panel.querySelectorAll<HTMLElement>('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset['tab'] === id);
        });
        this.panel.querySelectorAll<HTMLElement>('.tab-content').forEach(el => {
            el.classList.toggle('active', el.id === `tab-${id}`);
        });
    }
}
