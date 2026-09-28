<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { fade, scale } from 'svelte/transition';
	import Icon from '@iconify/svelte';
	export let open: boolean = false;
	export let title: string = 'Confirm';
	export let message: string = 'Are you sure?';
	export let confirmText: string = 'OK';
	export let cancelText: string = 'Cancel';
	export let floating: boolean = false;

	const dispatch = createEventDispatcher();
	let modalEl: HTMLElement | null = null;

	function doConfirm() {
		dispatch('confirm');
		open = false;
	}

	function doCancel() {
		open = false;
	}

	// Return focus to previously focused element when modal closes
	// Guard access to `document`/`HTMLElement` so SSR (server) doesn't throw.
	let previouslyFocused: Element | null = null;
	$: if (open) {
		if (typeof document !== 'undefined') {
			previouslyFocused = document.activeElement;
		} else {
			previouslyFocused = null;
		}
	}

	onMount(() => {
		const onKey = (e: KeyboardEvent) => {
			if (!open) return;
			if (e.key === 'Escape') doCancel();
			if (e.key === 'Enter') doConfirm();
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	// On close, try to restore focus if the previously focused element supports focus().
	$: if (!open) {
		const pf = previouslyFocused as HTMLElement | null;
		if (pf && typeof pf.focus === 'function') {
			try {
				pf.focus();
			} catch {
				void 0;
			}
		}
	}
</script>

{#if open}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center {floating ? 'pointer-events-none' : ''}"
		style={floating ? '' : "background: rgba(0, 0, 0, 0.1); backdrop-filter: blur(2px);"}
		aria-hidden="false"
	>
		{#if !floating}
			<div class="absolute inset-0" on:click={doCancel} transition:fade aria-hidden="true"></div>
		{/if}

		<div
			class="z-10 w-11/12 max-w-2xl overflow-hidden rounded-lg bg-white shadow-xl ring-1 ring-black/5 dark:bg-gray-800 dark:ring-white/5 {floating ? 'pointer-events-auto border border-gray-200 dark:border-gray-700 shadow-2xl' : ''}"
			role="dialog"
			aria-modal="true"
			aria-labelledby="confirm-title"
			aria-describedby="confirm-desc"
			bind:this={modalEl}
			transition:scale={{ duration: 160 }}
		>
			<div
				class="flex items-center gap-3 border-b border-gray-100 bg-gray-50 px-5 py-3 dark:border-gray-700 dark:bg-gray-900"
			>
				<div
					class="shrink-0 rounded-full bg-red-100 p-2 text-red-600 dark:bg-red-700/20 dark:text-red-300"
				>
					<Icon icon="mdi:alert-circle" class="h-5 w-5" />
				</div>
				<div>
					<h3 id="confirm-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">
						{title}
					</h3>
					<p id="confirm-desc" class="mt-0.5 text-sm text-gray-600 dark:text-gray-300">{message}</p>
				</div>
			</div>

			<div class="p-5">
				<div class="flex justify-end gap-3">
					<button
						class="rounded bg-gray-100 px-4 py-2 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600"
						on:click={doCancel}
					>
						{cancelText}
					</button>
					<button on:click={doConfirm}>
						{confirmText}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
