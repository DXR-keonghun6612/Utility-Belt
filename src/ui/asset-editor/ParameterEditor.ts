import { ParameterSchema, ComputedSchema, ParameterDescriptor } from '../../core/NodeAssembler';

type ParamType = ParameterDescriptor['type'];

export class ParameterEditor {
    private container: HTMLElement;
    private params: ParameterSchema = {};
    private computed: ComputedSchema = {};
    private onParamsChange: (params: ParameterSchema) => void;
    private onComputedChange: (computed: ComputedSchema) => void;

    constructor(
        container: HTMLElement,
        onParamsChange: (params: ParameterSchema) => void,
        onComputedChange: (computed: ComputedSchema) => void,
    ) {
        this.container = container;
        this.onParamsChange = onParamsChange;
        this.onComputedChange = onComputedChange;
    }

    setSchema(params?: ParameterSchema, computed?: ComputedSchema): void {
        this.params = params ? JSON.parse(JSON.stringify(params)) as ParameterSchema : {};
        this.computed = computed ? { ...computed } : {};
        this._render();
    }

    private _render(): void {
        this.container.innerHTML = '';
        this._renderParams();
        this._renderComputed();
    }

    // ── PARAMETERS ───────────────────────────────────────────

    private _renderParams(): void {
        const section = document.createElement('div');
        section.className = 'panel-section';
        section.appendChild(this._titleRow('PARAMETERS', () => {
            const key = this._uniqueKey('param', this.params);
            this.params[key] = { type: 'number', default: 0, min: 0, max: 100 };
            this.onParamsChange({ ...this.params });
            this._render();
        }));
        for (const key of Object.keys(this.params)) {
            section.appendChild(this._paramRow(key));
        }
        this.container.appendChild(section);
    }

    private _paramRow(key: string): HTMLElement {
        const param = this.params[key];
        const wrapper = document.createElement('div');
        wrapper.className = 'pe-param-row';

        // 1행: key 입력 + 타입 선택 + 삭제
        const line1 = document.createElement('div');
        line1.className = 'pe-row-line';

        const keyInput = document.createElement('input');
        keyInput.className = 'pe-key-input';
        keyInput.value = key;
        keyInput.placeholder = 'name';
        keyInput.title = `참조 방법: $params.${key}`;
        keyInput.addEventListener('change', () => {
            const next = keyInput.value.trim().replace(/\W/g, '_');
            if (!next || next === key || next in this.params) { keyInput.value = key; return; }
            this.params = this._renameKey(this.params, key, next) as ParameterSchema;
            this.onParamsChange({ ...this.params });
            this._render();
        });

        const typeSelect = document.createElement('select');
        typeSelect.className = 'builder-select pe-type-select';
        for (const t of ['number', 'integer', 'string', 'boolean'] as ParamType[]) {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            if (param.type === t) opt.selected = true;
            typeSelect.appendChild(opt);
        }
        typeSelect.addEventListener('change', () => {
            this.params[key] = { ...this.params[key], type: typeSelect.value as ParamType, default: this._defaultFor(typeSelect.value as ParamType) };
            this.onParamsChange({ ...this.params });
            this._render();
        });

        line1.appendChild(keyInput);
        line1.appendChild(typeSelect);
        line1.appendChild(this._removeBtn(() => {
            delete this.params[key];
            this.onParamsChange({ ...this.params });
            this._render();
        }));
        wrapper.appendChild(line1);

        // 2행: 타입별 세부 설정
        if (param.type === 'number' || param.type === 'integer') {
            const line2 = document.createElement('div');
            line2.className = 'pe-row-line pe-row-numbers';
            const isInt = param.type === 'integer';
            line2.appendChild(this._numField('default', Number(param.default ?? 0), v => {
                this.params[key] = { ...this.params[key], default: isInt ? Math.round(v) : v };
                this.onParamsChange({ ...this.params });
            }));
            line2.appendChild(this._numField('min', Number(param.min ?? 0), v => {
                this.params[key] = { ...this.params[key], min: v };
                this.onParamsChange({ ...this.params });
            }));
            line2.appendChild(this._numField('max', Number(param.max ?? 100), v => {
                this.params[key] = { ...this.params[key], max: v };
                this.onParamsChange({ ...this.params });
            }));
            wrapper.appendChild(line2);
        } else if (param.type === 'boolean') {
            const line2 = document.createElement('div');
            line2.className = 'pe-row-line';
            const lbl = this._inlineLabel('default');
            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.checked = Boolean(param.default);
            chk.addEventListener('change', () => {
                this.params[key] = { ...this.params[key], default: chk.checked };
                this.onParamsChange({ ...this.params });
            });
            line2.appendChild(lbl);
            line2.appendChild(chk);
            wrapper.appendChild(line2);
        } else {
            const line2 = document.createElement('div');
            line2.className = 'pe-row-line';
            const lbl = this._inlineLabel('default');
            const inp = document.createElement('input');
            inp.className = 'pe-expr-input';
            inp.value = String(param.default ?? '');
            inp.addEventListener('change', () => {
                this.params[key] = { ...this.params[key], default: inp.value };
                this.onParamsChange({ ...this.params });
            });
            line2.appendChild(lbl);
            line2.appendChild(inp);
            wrapper.appendChild(line2);
        }

        return wrapper;
    }

    // ── COMPUTED ──────────────────────────────────────────────

    private _renderComputed(): void {
        const section = document.createElement('div');
        section.className = 'panel-section';
        section.appendChild(this._titleRow('COMPUTED', () => {
            const key = this._uniqueKey('val', this.computed as Record<string, unknown>);
            (this.computed as Record<string, unknown>)[key] = '0';
            this.onComputedChange({ ...this.computed });
            this._render();
        }));
        for (const [key, expr] of Object.entries(this.computed)) {
            section.appendChild(this._computedRow(key, String(expr)));
        }
        this.container.appendChild(section);
    }

    private _computedRow(key: string, expr: string): HTMLElement {
        const wrapper = document.createElement('div');
        wrapper.className = 'pe-param-row';

        const line = document.createElement('div');
        line.className = 'pe-row-line';

        const keyInput = document.createElement('input');
        keyInput.className = 'pe-key-input';
        keyInput.value = key;
        keyInput.placeholder = 'name';
        keyInput.title = `참조 방법: $computed.${key}`;
        keyInput.addEventListener('change', () => {
            const next = keyInput.value.trim().replace(/\W/g, '_');
            if (!next || next === key || next in this.computed) { keyInput.value = key; return; }
            this.computed = this._renameKey(this.computed as Record<string, unknown>, key, next) as ComputedSchema;
            this.onComputedChange({ ...this.computed });
            this._render();
        });

        const exprInput = document.createElement('input');
        exprInput.className = 'pe-expr-input';
        exprInput.value = expr;
        exprInput.placeholder = 'e.g.  length * 0.5';
        exprInput.title = '파라미터 이름을 직접 사용 (e.g. length * 0.5, floor(count))';
        exprInput.addEventListener('change', () => {
            (this.computed as Record<string, unknown>)[key] = exprInput.value.trim() || '0';
            this.onComputedChange({ ...this.computed });
        });

        line.appendChild(keyInput);
        line.appendChild(exprInput);
        line.appendChild(this._removeBtn(() => {
            delete (this.computed as Record<string, unknown>)[key];
            this.onComputedChange({ ...this.computed });
            this._render();
        }));
        wrapper.appendChild(line);
        return wrapper;
    }

    // ── 공용 DOM 헬퍼 ─────────────────────────────────────────

    private _titleRow(text: string, onAdd: () => void): HTMLElement {
        const row = document.createElement('div');
        row.className = 'pe-title-row';
        const title = document.createElement('span');
        title.className = 'panel-section-title';
        title.style.margin = '0';
        title.textContent = text;
        const btn = document.createElement('button');
        btn.className = 'composer-icon-btn';
        btn.textContent = '+';
        btn.title = `Add ${text.toLowerCase()} entry`;
        btn.addEventListener('click', onAdd);
        row.appendChild(title);
        row.appendChild(btn);
        return row;
    }

    private _numField(label: string, initial: number, onChange: (v: number) => void): HTMLElement {
        const wrap = document.createElement('div');
        wrap.className = 'pe-num-field';
        const lbl = document.createElement('span');
        lbl.textContent = label;
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.value = String(initial);
        inp.step = '0.1';
        inp.addEventListener('change', () => {
            const v = parseFloat(inp.value);
            if (!isNaN(v)) onChange(v);
        });
        wrap.appendChild(lbl);
        wrap.appendChild(inp);
        return wrap;
    }

    private _inlineLabel(text: string): HTMLElement {
        const span = document.createElement('span');
        span.className = 'pe-inline-label';
        span.textContent = text;
        return span;
    }

    private _removeBtn(onClick: () => void): HTMLElement {
        const btn = document.createElement('button');
        btn.className = 'composer-icon-btn remove';
        btn.textContent = '×';
        btn.addEventListener('click', onClick);
        return btn;
    }

    // ── 유틸 ─────────────────────────────────────────────────

    private _uniqueKey(prefix: string, map: Record<string, unknown>): string {
        let key = prefix;
        let i = 1;
        while (key in map) key = `${prefix}${i++}`;
        return key;
    }

    private _renameKey(obj: Record<string, unknown>, oldKey: string, newKey: string): Record<string, unknown> {
        const next: Record<string, unknown> = {};
        for (const k of Object.keys(obj)) next[k === oldKey ? newKey : k] = obj[k];
        return next;
    }

    private _defaultFor(type: ParamType): unknown {
        if (type === 'number' || type === 'integer') return 0;
        if (type === 'boolean') return false;
        return '';
    }
}
