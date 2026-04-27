import { SceneNode } from './SceneNode';

export class NodeRegistry {
    private static readonly _map = new Map<string, SceneNode>();

    static register(node: SceneNode): void {
        if (this._map.has(node.id)) {
            throw new Error(`NodeRegistry: duplicate id "${node.id}"`);
        }
        this._map.set(node.id, node);
    }

    static unregister(node: SceneNode): void {
        this._map.delete(node.id);
    }

    static get(id: string): SceneNode | undefined {
        return this._map.get(id);
    }

    static has(id: string): boolean {
        return this._map.has(id);
    }

    static clear(): void {
        this._map.clear();
    }

    static all(): SceneNode[] {
        return Array.from(this._map.values());
    }
}
