import { AssetManager, AssetCatalogEntry } from '../../core/AssetManager';

export class AssetSelect {
    readonly element: HTMLElement;
    private categorySelect: HTMLSelectElement;
    private subcategorySelect: HTMLSelectElement;
    private modelSelect: HTMLSelectElement;
    private options: AssetCatalogEntry[];

    constructor(assetManager: AssetManager) {
        this.options = assetManager.getAllModelCatalogEntries();

        this.element = document.createElement('div');
        this.element.style.cssText = 'display:flex; gap:4px; flex:1; min-width:0;';

        this.categorySelect = document.createElement('select');
        this.categorySelect.className = 'builder-select';
        this.categorySelect.style.cssText = 'flex:0 0 80px; min-width:0;';

        this.subcategorySelect = document.createElement('select');
        this.subcategorySelect.className = 'builder-select';
        this.subcategorySelect.style.cssText = 'flex:0 0 90px; min-width:0;';

        this.modelSelect = document.createElement('select');
        this.modelSelect.className = 'builder-select';
        this.modelSelect.style.cssText = 'flex:1; min-width:0;';

        this.categorySelect.addEventListener('change', () => this._renderSubcategories());
        this.subcategorySelect.addEventListener('change', () => this._renderModels());

        this.element.appendChild(this.categorySelect);
        this.element.appendChild(this.subcategorySelect);
        this.element.appendChild(this.modelSelect);

        this._renderCategories();
    }

    value(): string {
        return this.modelSelect.value;
    }

    private _renderCategories(): void {
        this.categorySelect.innerHTML = '';

        const categories = Array.from(new Set(this.options.map(option => option.category))).sort();
        for (const category of categories) {
            const opt = document.createElement('option');
            opt.value = category;
            opt.textContent = category;
            this.categorySelect.appendChild(opt);
        }

        this._renderSubcategories();
    }

    private _renderSubcategories(): void {
        this.subcategorySelect.innerHTML = '';

        const category = this.categorySelect.value;
        const subcategories = Array.from(new Set(
            this.options
                .filter(option => option.category === category)
                .map(option => option.subcategory),
        )).sort();

        for (const subcategory of subcategories) {
            const opt = document.createElement('option');
            opt.value = subcategory;
            opt.textContent = subcategory;
            this.subcategorySelect.appendChild(opt);
        }

        this._renderModels();
    }

    private _renderModels(): void {
        this.modelSelect.innerHTML = '';

        const category = this.categorySelect.value;
        const subcategory = this.subcategorySelect.value;
        const models = this.options
            .filter(option => option.category === category)
            .filter(option => option.subcategory === subcategory)
            .sort((a, b) => a.name.localeCompare(b.name));

        for (const model of models) {
            const opt = document.createElement('option');
            opt.value = model.name;
            opt.textContent = model.name;
            this.modelSelect.appendChild(opt);
        }
    }
}
