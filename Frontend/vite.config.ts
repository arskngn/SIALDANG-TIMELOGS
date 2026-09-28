import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import Icons from 'unplugin-icons/vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
		Icons({
			compiler: 'svelte',
			autoInstall: true
		})
	],
	build: {
		// Ensure assets use relative paths
		assetsDir: '_assets',
		rollupOptions: {
			output: {
				manualChunks: undefined
			}
		}
	},
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			},
			'/static': {
				target: 'http://localhost:8000',
				changeOrigin: true
			}
		}
	},
	preview: {
		port: 4173,
		host: true
	}
});
