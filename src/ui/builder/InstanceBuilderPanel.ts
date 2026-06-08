import { AssetManager } from '../../core/AssetManager';
import {
    NodeAssembler,
    NodeDescriptor,
    ParameterDescriptor,
    SceneInstanceState,
} from '../../core/NodeAssembler';
import { SceneNode } from '../../core/SceneNode';

export class InstanceBuilderPanel {
    private container: HTMLElement;
    private assetManager: AssetManager;
    private onRebuilt: (root: SceneNode) => void;
    private selectedNode: SceneNode | null = null;
    private sceneRoot: SceneNode | null = null;

    constructor(
        container: HTMLElement,
        assetManager: AssetManager,
        onRebuilt: (root: SceneNode) => void,
    ) {
        this.container = container;
        this.assetManager = assetManager;
        this.onRebuilt = onRebuilt;
        this.render();
    }

    setSelection(node: SceneNode | null): void {
        this.selectedNode = node;
        this.render();
    }

    setSceneRoot(root: SceneNode): void {
        this.sceneRoot = root;
        this.render();
    }

    render(): void {
        this.container.innerHTML = '';

        const instances = this._sceneInstances();
        const root = this._targetInstance(instances);

        this.container.appendChild(this._targetSection(instances, root));

        if (!root) {
            this.container.appendChild(this._hintSection('Select a scene instance to edit its placement parameters.'));
            return;
        }

        const modelName = String(root.metadata['_modelName'] ?? root.id);
        const descriptor = this.assetManager.getModel(modelName);
        const state = NodeAssembler.readInstanceState(root);
        const params = this._defaultParams(descriptor, state);

        if (Object.keys(params).length === 0) {
            this.container.appendChild(this._hintSection('No builder parameters for this instance.'));
            return;
        }

        this.container.appendChild(this._summary(root, modelName));
        this.container.appendChild(this._paramsSection(root, descriptor, params));
    }

    private _targetSection(instances: SceneNode[], selectedRoot: SceneNode | null): HTMLElement {
        const section = this._section('TARGET INSTANCE');

        if (instances.length === 0) {
            section.appendChild(this._hint('No scene instances.'));
            return section;
        }

        const select = document.createElement('select');
        select.className = 'builder-select';
        select.style.width = '100%';

        for (const instance of instances) {
            const opt = document.createElement('option');
            opt.value = instance.id;
            opt.textContent = `${String(instance.metadata['_modelName'] ?? instance.label)} / ${instance.id}`;
            if (instance === selectedRoot) opt.selected = true;
            select.appendChild(opt);
        }

        select.addEventListener('change', () => {
            this.selectedNode = instances.find(instance => instance.id === select.value) ?? null;
            this.render();
        });

        section.appendChild(select);
        return section;
    }

    private _targetInstance(instances: SceneNode[]): SceneNode | null {
        const selectedRoot = this._findInstanceRoot(this.selectedNode);
        if (selectedRoot && instances.includes(selectedRoot)) return selectedRoot;
        return instances[0] ?? null;
    }

    private _sceneInstances(): SceneNode[] {
        if (!this.sceneRoot) return [];
        return this.sceneRoot
            .flatten()
            .filter(node => {
                const modelName = node.metadata['_modelName'];
                if (modelName === undefined) return false;
                return this._hasParameterSchema(this.assetManager.getModel(String(modelName)));
            });
    }

    private _findInstanceRoot(node: SceneNode | null): SceneNode | null {
        let cur = node;
        while (cur) {
            if (cur.metadata['_modelName'] !== undefined) return cur;
            cur = cur.parent;
        }
        return null;
    }

    private _summary(root: SceneNode, modelName: string): HTMLElement {
        const section = this._section('INSTANCE');
        section.appendChild(this._propRow('model', modelName));
        section.appendChild(this._propRow('instance', root.id));
        return section;
    }

    private _paramsSection(
        root: SceneNode,
        descriptor: NodeDescriptor,
        params: Record<string, unknown>,
    ): HTMLElement {
        const section = this._section('PARAMETERS');

        for (const [key, value] of Object.entries(params)) {
            section.appendChild(this._paramControl(key, value, descriptor.parameters?.[key], nextValue => {
                this._applyState(root, {
                    params: {
                        ...NodeAssembler.readInstanceState(root).params,
                        [key]: nextValue,
                    },
                });
            }));
        }

        return section;
    }

    private _defaultParams(descriptor: NodeDescriptor, state: SceneInstanceState): Record<string, unknown> {
        const params: Record<string, unknown> = {};
        for (const [key, parameter] of Object.entries(descriptor.parameters ?? {})) {
            params[key] = state.params?.[key] ?? parameter.default;
        }
        return params;
    }

    private _applyState(root: SceneNode, patch: SceneInstanceState): void {
        const modelName = String(root.metadata['_modelName'] ?? root.id);
        const descriptor = this.assetManager.getModel(modelName);
        const nextState = NodeAssembler.updateInstanceState(root, patch);
        const nextRoot = NodeAssembler.rebuildInstance(root, descriptor, nextState);
        this.selectedNode = nextRoot;
        this.onRebuilt(nextRoot);
        this.render();
    }

    private _paramControl(
        key: string,
        value: unknown,
        parameter: ParameterDescriptor | undefined,
        onChange: (value: unknown) => void,
    ): HTMLElement {
        if (typeof value === 'number') {
            return this._numField(this._paramLabel(key, parameter), value, parameter, onChange);
        }
        if (typeof value === 'boolean') {
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = value;
            input.addEventListener('change', () => onChange(input.checked));
            return this._field(this._paramLabel(key, parameter), input);
        }

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'slider-value-input';
        input.value = String(value);
        input.style.width = '130px';
        input.addEventListener('change', () => onChange(input.value));
        return this._field(this._paramLabel(key, parameter), input);
    }

    private _paramLabel(key: string, parameter: ParameterDescriptor | undefined): string {
        const label = parameter?.label ?? key;
        return parameter?.unit ? `${label} (${parameter.unit})` : label;
    }

    private _section(title: string): HTMLElement {
        const section = document.createElement('div');
        section.className = 'panel-section';
        const t = document.createElement('div');
        t.className = 'panel-section-title';
        t.textContent = title;
        section.appendChild(t);
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

    private _field(label: string, control: HTMLElement): HTMLElement {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px;';
        const lbl = document.createElement('span');
        lbl.textContent = label;
        lbl.style.color = '#8899aa';
        row.appendChild(lbl);
        row.appendChild(control);
        return row;
    }

    private _numField(
        label: string,
        initial: number,
        parameter: ParameterDescriptor | undefined,
        onChange: (value: number) => void,
    ): HTMLElement {
        if (parameter?.unit === 'rad') {
            return this._angleField(label.replace(/\s*\(rad\)$/, ' (deg)'), initial, parameter, onChange);
        }

        const input = document.createElement('input');
        input.type = 'number';
        input.className = 'slider-value-input';
        input.style.width = '90px';
        input.value = String(initial);
        input.step = String(parameter?.step ?? (parameter?.type === 'integer' ? 1 : 0.1));
        if (parameter?.min !== undefined) input.min = String(parameter.min);
        if (parameter?.max !== undefined) input.max = String(parameter.max);
        input.addEventListener('change', () => {
            const parsed = parameter?.type === 'integer'
                ? parseInt(input.value, 10)
                : parseFloat(input.value);
            const value = parameter?.type === 'integer' ? Math.round(parsed) : parsed;
            if (!Number.isNaN(value)) onChange(value);
        });
        return this._field(label, input);
    }

    private _angleField(
        label: string,
        initialRad: number,
        parameter: ParameterDescriptor,
        onChange: (value: number) => void,
    ): HTMLElement {
        const toDeg = (rad: number) => rad * 180 / Math.PI;
        const toRad = (deg: number) => deg * Math.PI / 180;
        const min = toDeg(parameter.min ?? -Math.PI);
        const max = toDeg(parameter.max ?? Math.PI);
        const step = toDeg(parameter.step ?? 0.01);
        return this._rangeField(label, toDeg(initialRad), min, max, step, deg => onChange(toRad(deg)), 1);
    }

    private _rangeField(
        label: string,
        initial: number,
        min: number,
        max: number,
        step: number,
        onChange: (value: number) => void,
        precision = 2,
    ): HTMLElement {
        const group = document.createElement('div');
        group.className = 'slider-group';

        const labelRow = document.createElement('div');
        labelRow.className = 'slider-label';
        const labelText = document.createElement('span');
        labelText.textContent = label;

        const input = document.createElement('input');
        input.type = 'number';
        input.className = 'slider-value-input';
        input.value = this._formatNumber(initial, precision);
        input.min = String(min);
        input.max = String(max);
        input.step = String(step);

        labelRow.appendChild(labelText);
        labelRow.appendChild(input);

        const slider = document.createElement('input');
        slider.type = 'range';
        slider.min = String(min);
        slider.max = String(max);
        slider.step = String(step);
        slider.value = String(initial);

        const commit = (value: number) => {
            if (Number.isNaN(value)) return;
            const clamped = Math.min(max, Math.max(min, value));
            slider.value = String(clamped);
            input.value = this._formatNumber(clamped, precision);
            onChange(clamped);
        };

        slider.addEventListener('input', () => {
            const value = parseFloat(slider.value);
            input.value = this._formatNumber(value, precision);
        });
        slider.addEventListener('change', () => commit(parseFloat(slider.value)));
        input.addEventListener('change', () => commit(parseFloat(input.value)));

        group.appendChild(labelRow);
        group.appendChild(slider);
        return group;
    }

    private _formatNumber(value: number, precision: number): string {
        return Number(value.toFixed(precision)).toString();
    }

    private _hasParameterSchema(descriptor: NodeDescriptor): boolean {
        return Object.keys(descriptor.parameters ?? {}).length > 0;
    }

    private _hint(text: string): HTMLElement {
        const el = document.createElement('div');
        el.style.cssText = 'color:#7a8494; padding:8px 0; font-size:11px;';
        el.textContent = text;
        return el;
    }

    private _hintSection(message: string): HTMLElement {
        const section = this._section('BUILDER');
        section.appendChild(this._hint(message));
        return section;
    }
}
