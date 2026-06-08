import { NodeDescriptor, AnchorLayout } from '../../core/NodeAssembler';
import { GeometryDescriptor } from '../../core/NodeFactory';

const SHAPE_PARAMS: Record<string, Array<{ key: string; label: string; min: number; max: number; default: number }>> = {
    Box:          [
        { key: 'width',        label: 'width',       min: 0.01, max: 20, default: 1   },
        { key: 'height',       label: 'height',      min: 0.01, max: 20, default: 1   },
        { key: 'depth',        label: 'depth',       min: 0.01, max: 20, default: 1   },
    ],
    Cylinder:     [
        { key: 'radiusTop',    label: 'radius top',  min: 0.01, max: 5,  default: 0.5 },
        { key: 'radiusBottom', label: 'radius bot',  min: 0.01, max: 5,  default: 0.5 },
        { key: 'height',       label: 'height',      min: 0.01, max: 20, default: 1   },
    ],
    Sphere:       [{ key: 'radius', label: 'radius', min: 0.01, max: 10, default: 0.5 }],
    Capsule:      [
        { key: 'radius', label: 'radius', min: 0.01, max: 5,  default: 0.3 },
        { key: 'length', label: 'length', min: 0.01, max: 20, default: 1   },
    ],
    JointCapsule: [
        { key: 'radius', label: 'radius', min: 0.01, max: 5,  default: 0.3 },
        { key: 'length', label: 'length', min: 0.01, max: 20, default: 1   },
    ],
    ConveyorBody: [{ key: 'length', label: 'length', min: 1, max: 50, default: 10 }],
    Elbow:        [
        { key: 'pathRadius',  label: 'path radius',  min: 0.1, max: 5, default: 1.2  },
        { key: 'outerRadius', label: 'outer radius', min: 0.1, max: 2, default: 0.6  },
        { key: 'innerRadius', label: 'inner radius', min: 0.0, max: 2, default: 0.45 },
    ],
};

export const ALL_SHAPES = Object.keys(SHAPE_PARAMS);

const RAD2DEG = 180 / Math.PI;
const DEG2RAD = Math.PI / 180;

// ── Field widgets ────────────────────────────────────────────────────────────

function resolveNum(value: unknown, previewParams: Record<string, unknown>, factor = 1): number {
    if (typeof value === 'number') return value * factor;
    if (typeof value === 'string') {
        const m = /^\$(params|computed)\.(\w+)$/.exec(value);
        if (m) return Number(previewParams[m[2]] ?? 0) * factor;
    }
    return 0;
}

export function createBindField(
    label: string,
    min: number,
    max: number,
    value: unknown,
    bindings: string[],
    previewParams: Record<string, unknown>,
    onChange: (v: number | string) => void,
    isInt = false,
): HTMLElement {
    const isBound = typeof value === 'string' && /^\$/.test(value);
    const wrap = document.createElement('div');
    wrap.className = 'nti-field' + (isBound ? ' is-bound' : '');

    const lbl = document.createElement('span');
    lbl.className = 'nti-field-label';
    lbl.textContent = label;

    const ctrl = document.createElement('div');
    ctrl.className = 'nti-field-ctrl';

    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'nti-bind-btn' + (isBound ? ' active' : '');
    toggleBtn.title = isBound ? 'literal 값으로 전환' : '파라미터에 바인딩';
    toggleBtn.textContent = '⊕';

    const renderLiteral = (cur: number) => {
        ctrl.innerHTML = '';
        wrap.classList.remove('is-bound');
        toggleBtn.classList.remove('active');
        toggleBtn.title = '파라미터에 바인딩';

        const range = document.createElement('input');
        range.type  = 'range';
        range.min   = String(min);
        range.max   = String(max);
        range.step  = isInt ? '1' : String((max - min) / 500);
        range.value = String(cur);

        const numIn = document.createElement('input');
        numIn.type      = 'number';
        numIn.className = 'nti-num-in';
        numIn.value     = isInt ? String(Math.round(cur)) : cur.toFixed(3);
        numIn.step      = isInt ? '1' : '0.001';

        const sync = (v: number) => {
            range.value = String(v);
            numIn.value = isInt ? String(v) : v.toFixed(3);
            onChange(v);
        };
        range.addEventListener('input', () => {
            let v = parseFloat(range.value);
            if (isInt) v = Math.round(v);
            sync(v);
        });
        numIn.addEventListener('change', () => {
            let v = parseFloat(numIn.value);
            if (isNaN(v)) v = cur;
            v = Math.max(min, Math.min(max, isInt ? Math.round(v) : v));
            sync(v);
        });

        ctrl.appendChild(range);
        ctrl.appendChild(numIn);
    };

    const renderBound = (cur: string) => {
        ctrl.innerHTML = '';
        wrap.classList.add('is-bound');
        toggleBtn.classList.add('active');
        toggleBtn.title = 'literal 값으로 전환';

        const sel = document.createElement('select');
        sel.className = 'builder-select nti-bind-sel';
        if (bindings.length === 0) {
            const opt = document.createElement('option');
            opt.textContent = '(params 없음)';
            sel.appendChild(opt);
        }
        for (const b of bindings) {
            const opt = document.createElement('option');
            opt.value = b; opt.textContent = b;
            if (b === cur) opt.selected = true;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', () => onChange(sel.value));
        ctrl.appendChild(sel);
    };

    toggleBtn.addEventListener('click', () => {
        if (toggleBtn.classList.contains('active')) {
            const sel = ctrl.querySelector<HTMLSelectElement>('select');
            const startVal = resolveNum(sel?.value ?? '', previewParams);
            renderLiteral(startVal);
            onChange(startVal);
        } else {
            if (bindings.length === 0) return;
            renderBound(bindings[0]);
            onChange(bindings[0]);
        }
    });

    if (isBound) renderBound(value as string);
    else renderLiteral(resolveNum(value, previewParams));

    wrap.appendChild(lbl);
    wrap.appendChild(ctrl);
    wrap.appendChild(toggleBtn);
    return wrap;
}

export function createColorField(label: string, initial: string, onChange: (v: string) => void): HTMLElement {
    const wrap = document.createElement('div');
    wrap.className = 'nti-field';
    const lbl = document.createElement('span'); lbl.className = 'nti-field-label'; lbl.textContent = label;
    const inp = document.createElement('input'); inp.type = 'color';
    inp.value = /^#/.test(initial) ? initial : '#cccccc';
    inp.addEventListener('input', () => onChange(inp.value));
    wrap.appendChild(lbl); wrap.appendChild(inp);
    return wrap;
}

export function createCheckField(label: string, initial: boolean, onChange: (v: boolean) => void): HTMLElement {
    const wrap = document.createElement('div');
    wrap.className = 'nti-field';
    const lbl = document.createElement('span'); lbl.className = 'nti-field-label'; lbl.textContent = label;
    const inp = document.createElement('input'); inp.type = 'checkbox'; inp.checked = initial;
    inp.addEventListener('change', () => onChange(inp.checked));
    wrap.appendChild(lbl); wrap.appendChild(inp);
    return wrap;
}

export function createSelectField(label: string, options: string[], initial: string, onChange: (v: string) => void): HTMLElement {
    const wrap = document.createElement('div');
    wrap.className = 'nti-field';
    const lbl = document.createElement('span'); lbl.className = 'nti-field-label'; lbl.textContent = label;
    const sel = document.createElement('select'); sel.className = 'builder-select';
    for (const o of options) {
        const opt = document.createElement('option'); opt.value = o; opt.textContent = o;
        if (o === initial) opt.selected = true;
        sel.appendChild(opt);
    }
    sel.addEventListener('change', () => onChange(sel.value));
    wrap.appendChild(lbl); wrap.appendChild(sel);
    return wrap;
}

export function createSubSep(text: string): HTMLElement {
    const el = document.createElement('div');
    el.className = 'nti-subsep';
    el.textContent = text;
    return el;
}

// ── Property renderers ──────────────────────────────────────────────────────

export function renderLinkProps(
    desc: NodeDescriptor,
    container: HTMLElement,
    bindings: string[],
    previewParams: Record<string, unknown>,
    emit: () => void,
    onShapeChange: () => void,
): void {
    const geoInit = { shape: 'Box', color: '#cccccc', ...(desc.geometry ?? {}) } as Record<string, unknown>;
    const setGeo = (patch: Record<string, unknown>) => {
        desc.geometry = { ...(desc.geometry ?? {}), ...patch } as GeometryDescriptor;
        emit();
    };

    container.appendChild(createSelectField('shape', ALL_SHAPES, geoInit.shape as string, v => {
        setGeo({ shape: v });
        onShapeChange();
    }));

    if (geoInit.shape === 'JointCapsule') {
        container.appendChild(createColorField('bodyColor', (geoInit.bodyColor as string) ?? '#cccccc', v => setGeo({ bodyColor: v })));
        container.appendChild(createColorField('capColor',  (geoInit.capColor  as string) ?? '#00bcd4', v => setGeo({ capColor:  v })));
    } else {
        container.appendChild(createColorField('color', (geoInit.color as string) ?? '#cccccc', v => setGeo({ color: v })));
    }

    container.appendChild(createBindField('opacity', 0, 1, geoInit.opacity ?? 1, bindings, previewParams,
        v => setGeo({ opacity: v })));

    for (const p of (SHAPE_PARAMS[geoInit.shape as string] ?? [])) {
        container.appendChild(createBindField(p.label, p.min, p.max, geoInit[p.key] ?? p.default, bindings, previewParams,
            v => setGeo({ [p.key]: v })));
    }
}

export function renderAnchorProps(
    desc: NodeDescriptor,
    container: HTMLElement,
    bindings: string[],
    previewParams: Record<string, unknown>,
    emit: () => void,
    onKindChange: () => void,
): void {
    const layoutInit = { kind: 'single', exposed: true, ...(desc.layout ?? {}) } as Record<string, unknown>;
    const setLayout = (patch: Record<string, unknown>) => {
        desc.layout = { ...(desc.layout ?? {}), ...patch } as AnchorLayout;
        emit();
    };

    container.appendChild(createCheckField('exposed', layoutInit.exposed !== false, v => setLayout({ exposed: v })));
    container.appendChild(createSelectField('kind', ['single', 'array'], layoutInit.kind as string, v => {
        setLayout({ kind: v });
        onKindChange();
    }));

    if (layoutInit.kind === 'array') {
        container.appendChild(createSelectField('axis', ['x', 'y', 'z'], (layoutInit.axis as string) ?? 'x',
            v => setLayout({ axis: v })));
        container.appendChild(createBindField('count', 1, 100, layoutInit.count ?? 5, bindings, previewParams,
            v => setLayout({ count: v }), true));
        container.appendChild(createBindField('gap', 0, 50, layoutInit.gap ?? 2, bindings, previewParams,
            v => setLayout({ gap: v })));
    }
}

export function renderJointProps(
    desc: NodeDescriptor,
    container: HTMLElement,
    bindings: string[],
    previewParams: Record<string, unknown>,
    emit: () => void,
): void {
    const metaInit = desc.metadata ?? {};
    const setMeta = (patch: Record<string, unknown>) => {
        desc.metadata = { ...(desc.metadata ?? {}), ...patch };
        emit();
    };

    container.appendChild(createSelectField('joint axis', ['x', 'y', 'z'], (metaInit['axis'] as string) ?? 'y',
        v => setMeta({ axis: v })));

    const minDeg = ((metaInit['min'] as number) ?? -Math.PI) * RAD2DEG;
    const maxDeg = ((metaInit['max'] as number) ??  Math.PI) * RAD2DEG;
    container.appendChild(createBindField('min (°)', -360, 0,   minDeg, bindings, previewParams,
        v => setMeta({ min: typeof v === 'number' ? v * DEG2RAD : v })));
    container.appendChild(createBindField('max (°)', 0,   360,  maxDeg, bindings, previewParams,
        v => setMeta({ max: typeof v === 'number' ? v * DEG2RAD : v })));
}

export function renderTransformProps(
    desc: NodeDescriptor,
    container: HTMLElement,
    bindings: string[],
    previewParams: Record<string, unknown>,
    emit: () => void,
): void {
    const pos = ((desc.transform?.position ?? [0, 0, 0]) as unknown[]);
    const rot = ((desc.transform?.rotation ?? [0, 0, 0]) as unknown[]);

    container.appendChild(createSubSep('transform'));

    for (const i of [0, 1, 2]) {
        const label = ['pos.x', 'pos.y', 'pos.z'][i];
        container.appendChild(createBindField(label, -20, 20, pos[i] ?? 0, bindings, previewParams, v => {
            const next = [...pos]; next[i] = v;
            desc.transform = { ...desc.transform, position: next as [number, number, number] };
            emit();
        }));
    }
    for (const i of [0, 1, 2]) {
        const label = ['rot.x (°)', 'rot.y (°)', 'rot.z (°)'][i];
        const raw = rot[i] ?? 0;
        const display = typeof raw === 'number' ? raw * RAD2DEG : raw;
        container.appendChild(createBindField(label, -180, 180, display, bindings, previewParams, v => {
            const next = [...rot];
            next[i] = typeof v === 'number' ? v * DEG2RAD : v;
            desc.transform = { ...desc.transform, rotation: next as [number, number, number] };
            emit();
        }));
    }
}
