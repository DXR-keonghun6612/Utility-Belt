import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
    build: {
        rollupOptions: {
            input: {
                main:        resolve(__dirname, 'index.html'),
                assetEditor: resolve(__dirname, 'asset-editor.html'),
            },
        },
    },
});
