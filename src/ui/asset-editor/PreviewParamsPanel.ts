import { ParameterSchema } from '../../core/NodeAssembler';

export class PreviewParamsPanel {
    private container: HTMLElement;
    private onChange: (key: string, value: unknown) => void;

    constructor(container: HTMLElement, onChange: (key: string, value: unknown) => void) {
        this.container = container;
        this.onChange = onChange;
    }

    render(params: ParameterSchema, previewValues: Record<string, unknown>): void {
        this.container.innerHTML = '';
        if (Object.keys(params).length === 0) return;

        const section = document.createElement('div');
        section.className = 'panel-section';
        const title = document.createElement('div');
        title.className = 'panel-section-title';
        title.textContent = 'PREVIEW PARAMS';
        section.appendChild(title);

        for (const [key, param] of Object.entries(params)) {
            if (param.type === 'number' || param.type === 'integer') {
                const min = Number(param.min ?? 0);
                const max = Number(param.max ?? 100);
                const cur = Number(previewValues[key] ?? param.default);
                section.appendChild(this._previewSlider(key, min, max, cur, param.type === 'integer', v => {
                    this.onChange(key, v);
                }));
            } else if (param.type === 'boolean') {
                section.appendChild(this._previewToggle(key, Boolean(previewValues[key] ?? param.default), v => {
                    this.onChange(key, v);
                }));
            }
        }

        this.container.appendChild(section);
    }

    private _previewSlider(
        name: string,
        min: number,
        max: number,
        initial: number,
        isInt: boolean,
        onChange: (v: number) => void,
    ): HTMLElement {
        const group = document.createElement('div');
        group.className = 'slider-group';

        const labelRow = document.createElement('div');
        labelRow.className = 'slider-label';
        const nameEl = document.createElement('span');
        nameEl.textContent = name;
        const valueInput = document.createElement('input');
        valueInput.type = 'number';
        valueInput.className = 'slider-value-input';
        valueInput.value = isInt ? String(Math.round(initial)) : initial.toFixed(3);
        valueInput.step = isInt ? '1' : '0.001';
        labelRow.appendChild(nameEl);
        labelRow.appendChild(valueInput);

        const range = document.createElement('input');
        range.type  = 'range';
        range.min   = String(min);
        range.max   = String(max);
        range.step  = isInt ? '1' : String((max - min) / 500);
        range.value = String(initial);

        range.addEventListener('input', () => {
            let v = parseFloat(range.value); if (isInt) v = Math.round(v);
            valueInput.value = isInt ? String(v) : v.toFixed(3);
            onChange(v);
        });
        valueInput.addEventListener('change', () => {
            let v = parseFloat(valueInput.value);
            if (isNaN(v)) v = initial;
            v = Math.max(min, Math.min(max, isInt ? Math.round(v) : v));
            valueInput.value = isInt ? String(v) : v.toFixed(3);
            range.value = String(v);
            onChange(v);
        });

        group.appendChild(labelRow);
        group.appendChild(range);
        return group;
    }

    private _previewToggle(name: string, initial: boolean, onChange: (v: boolean) => void): HTMLElement {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:4px 0;';
        const lbl = document.createElement('span'); lbl.textContent = name; lbl.style.color = '#8899aa';
        const chk = document.createElement('input'); chk.type = 'checkbox'; chk.checked = initial;
        chk.addEventListener('change', () => onChange(chk.checked));
        row.appendChild(lbl); row.appendChild(chk);
        return row;
    }
}
