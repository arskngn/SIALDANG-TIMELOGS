<script lang="ts">
	import { onMount } from 'svelte';
	import { isAuthenticated } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { userAPI, type UserResponse } from '$lib/api';
	import MyLeavesReport from '$lib/MyLeavesReport.svelte';

	let authed = false;
	isAuthenticated.subscribe((v) => (authed = v));

	let user: UserResponse | null = null;
	let loading = true;
	let error: string | null = null;

	onMount(async () => {
		if (!authed) {
			goto(resolve('/login'));
			return;
		}
		try {
			user = await userAPI.getMe();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load user';
		} finally {
			loading = false;
		}
	});
</script>

<div class="container mx-auto px-4 py-6">
	<h1 class="mb-4 text-2xl font-semibold">My Leaves</h1>
	{#if loading}
		<p>Loading...</p>
	{:else if error}
		<div class="rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700">{error}</div>
	{:else if user}
		<MyLeavesReport {user} />
	{/if}
</div>
