import { AssetCatalogEntry, AssetManager } from '../../core/AssetManager';

export class AssetTreePanel {
    private container: HTMLElement;
    private assetManager: AssetManager;
    private onEditAsset: (name: string) => void;
    private onAddAsset: () => void;
    private selectedName: string | null = null;

    constructor(
        container: HTMLElement,
        assetManager: AssetManager,
        onEditAsset: (name: string) => void,
        onAddAsset: () => void,
    ) {
        this.container = container;
        this.assetManager = assetManager;
        this.onEditAsset = onEditAsset;
        this.onAddAsset = onAddAsset;
        this.render();
    }

    render(): void {
        this.container.innerHTML = '';

        const treeSection = this._sectionWithAction('ASSET DB', this._addButton());
        const groups = this._groupByPath(this.assetManager.getAllModelCatalogEntries());

        for (const [category, subcategories] of groups) {
            treeSection.appendChild(this._categoryRow(category));

            for (const [subcategory, assets] of subcategories) {
                treeSection.appendChild(this._subcategoryRow(subcategory));

                for (const asset of assets) {
                    treeSection.appendChild(this._assetRow(asset));
                }
            }
        }

        this.container.appendChild(treeSection);
        this.container.appendChild(this._detailSection());
    }

    private _groupByPath(entries: AssetCatalogEntry[]): Map<string, Map<string, AssetCatalogEntry[]>> {
        const groups = new Map<string, Map<string, AssetCatalogEntry[]>>();

        for (const entry of entries) {
            if (!groups.has(entry.category)) groups.set(entry.category, new Map());
            const subcategories = groups.get(entry.category)!;
            if (!subcategories.has(entry.subcategory)) subcategories.set(entry.subcategory, []);
            subcategories.get(entry.subcategory)!.push(entry);
        }

        for (const subcategories of groups.values()) {
            for (const assets of subcategories.values()) {
                assets.sort((a, b) => a.name.localeCompare(b.name));
            }
        }

        return new Map([...groups.entries()].sort(([a], [b]) => a.localeCompare(b)));
    }

    private _categoryRow(category: string): HTMLElement {
        const row = document.createElement('div');
        row.className = 'tree-row';
        row.style.fontWeight = 'bold';
        row.textContent = category;
        return row;
    }

    private _subcategoryRow(subcategory: string): HTMLElement {
        const row = document.createElement('div');
        row.className = 'tree-row';
        row.style.paddingLeft = '16px';
        row.style.color = '#aab4c3';
        row.textContent = subcategory;
        return row;
    }

    private _assetRow(asset: AssetCatalogEntry): HTMLElement {
        const row = document.createElement('div');
        row.className = 'tree-row' + (asset.name === this.selectedName ? ' selected' : '');
        row.style.paddingLeft = '32px';
        row.dataset['assetName'] = asset.name;

        const label = document.createElement('span');
        label.className = 'tree-label';
        label.textContent = asset.name;

        const badge = document.createElement('span');
        badge.className = 'tree-badge badge-GROUP';
        badge.textContent = 'ASSET';

        row.appendChild(label);
        row.appendChild(badge);

        row.addEventListener('click', () => {
            this.selectedName = asset.name;
            this.render();
        });

        return row;
    }

    private _detailSection(): HTMLElement {
        const selected = this.selectedName
            ? this.assetManager.getAllModelCatalogEntries().find(entry => entry.name === this.selectedName)
            : null;

        const section = this._sectionWithAction(
            'ASSET INFO',
            selected ? this._editButton(selected.name) : null,
        );

        if (!selected) {
            const empty = document.createElement('div');
            empty.style.cssText = 'color:#7a8494; padding:8px 0; font-size:11px;';
            empty.textContent = 'Select an asset.';
            section.appendChild(empty);
            return section;
        }

        section.appendChild(this._propRow('name', selected.name));
        section.appendChild(this._propRow('category', selected.category));
        section.appendChild(this._propRow('subcategory', selected.subcategory));
        section.appendChild(this._propRow('path', `src/asset/${selected.category}/${selected.subcategory}/${selected.name}.json`));

        const descriptor = this.assetManager.getModel(selected.name);
        section.appendChild(this._propRow('label', descriptor.label ?? descriptor.id));
        section.appendChild(this._propRow('type', descriptor.type));

        return section;
    }

    private _editButton(name: string): HTMLElement {
        const btn = document.createElement('button');
        btn.className = 'preset-btn primary';
        btn.style.cssText = 'flex:0; padding:4px 10px; font-size:10px;';
        btn.textContent = 'Edit';
        btn.addEventListener('click', () => this.onEditAsset(name));
        return btn;
    }

    private _addButton(): HTMLElement {
        const btn = document.createElement('button');
        btn.className = 'preset-btn primary';
        btn.style.cssText = 'flex:0; padding:4px 10px; font-size:10px;';
        btn.textContent = 'Add';
        btn.addEventListener('click', () => this.onAddAsset());
        return btn;
    }

    private _sectionWithAction(title: string, action: HTMLElement | null): HTMLElement {
        const section = document.createElement('div');
        section.className = 'panel-section';

        const header = document.createElement('div');
        header.style.cssText = 'display:flex; justify-content:space-between; align-items:center; gap:8px;';

        const t = document.createElement('div');
        t.className = 'panel-section-title';
        t.textContent = title;

        header.appendChild(t);
        if (action) header.appendChild(action);
        section.appendChild(header);
        return section;
    }

    private _propRow(key: string, value: string): HTMLElement {
        const row = document.createElement('div');
        row.className = 'prop-row';
        const k = document.createElement('span');
        k.textContent = key;
        const v = document.createElement('span');
        v.textContent = value;
        row.appendChild(k);
        row.appendChild(v);
        return row;
    }
}
