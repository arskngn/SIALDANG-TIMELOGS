<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	// Health page removed — redirect to login/main depending on auth
	onMount(() => {
		goto(resolve('/login'));
	});
</script>

<div class="container mx-auto p-8">
	<p class="text-center">Redirecting...</p>
</div>
