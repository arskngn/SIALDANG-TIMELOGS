<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { isAuthenticated } from '$lib/stores';

	// Redirect root to login (layout will forward to main if already logged in)
	onMount(() => {
		let unsub = isAuthenticated.subscribe(() => {
			// always go to login first; if already authenticated layout/nav will expose main
			goto(resolve('/login'));
		});
		// cleanup
		return () => unsub();
	});
</script>

<div class="container mx-auto p-8">
	<h1 class="text-center text-2xl font-semibold">Redirecting to login...</h1>
</div>
