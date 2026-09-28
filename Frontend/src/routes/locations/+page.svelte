<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import {
		locationAPI,
		type LocationResponse,
		type CreateLocation,
		type UpdateLocation
	} from '$lib/api';
	import { userRole, isAuthenticated, isAdmin } from '$lib/stores';
	import Icon from '@iconify/svelte';

	let locations: LocationResponse[] = [];
	let loading = true;
	let error: string | null = null;
	let success: string | null = null;

	let showForm = false;
	let isEditing = false;
	let selectedId: number | null = null;
	let name = '';
	let address = '';

	let role = '';
	let authed = false;
	let admin = false;

	const unsubRole = userRole.subscribe((r) => (role = r));
	const unsubAuth = isAuthenticated.subscribe((v) => (authed = v));
	const unsubAdmin = isAdmin.subscribe((v) => (admin = v));

	onMount(async () => {
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}
		if (!admin) {
			return;
		}
		await loadLocations();
	});

	onDestroy(() => {
		unsubRole();
		unsubAuth();
	});

	async function loadLocations() {
		try {
			loading = true;
			error = null;
			success = null;
			locations = await locationAPI.getAllLocations();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load locations';
			console.error('Error loading locations:', err);
		} finally {
			loading = false;
		}
	}

	function openCreateForm() {
		isEditing = false;
		selectedId = null;
		name = '';
		address = '';
		showForm = true;
	}

	function openEditForm(loc: LocationResponse) {
		isEditing = true;
		selectedId = loc.id;
		name = loc.name;
		address = loc.address || '';
		showForm = true;
	}

	function closeForm() {
		showForm = false;
		isEditing = false;
		selectedId = null;
		name = '';
		address = '';
	}

	async function handleSubmit() {
		try {
			error = null;
			const now = new Date().toISOString();
			if (isEditing && selectedId) {
				const payload: UpdateLocation = { name, address, date_updated: now };
				await locationAPI.updateLocation(selectedId, payload);
				success = `Location '${name}' updated`;
			} else {
				const payload: CreateLocation = { name, address, date_created: now, date_updated: now };
				await locationAPI.createLocation(payload);
				success = `Location '${name}' created`;
			}
			await loadLocations();
			closeForm();
			setTimeout(() => (success = null), 3000);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to save location';
			console.error('Error saving location:', err);
		}
	}

	async function deleteLocation(id: number) {
		try {
			const loc = locations.find((l) => l.id === id);
			await locationAPI.deleteLocation(id);
			locations = locations.filter((l) => l.id !== id);
			success = `Location '${loc?.name || id}' deleted`;
			setTimeout(() => (success = null), 3000);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to delete location';
			console.error('Error deleting location:', err);
		}
	}
</script>

{#if !admin}
	<div
		style="position: fixed; inset: 0; z-index: 99999; background: #000; display: flex; align-items: center; justify-content: center;"
	>
		<img
			src="/404.jpg"
			alt="Not authorized"
			style="width: 100vw; height: 100vh; object-fit: cover; display: block;"
		/>
	</div>
{:else}
	<div class="container mx-auto p-4 dark:text-white">
		<h1 class="mb-6 text-3xl font-bold dark:text-white">Location Management</h1>

		{#if error}
			<div
				class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700 dark:border-red-600 dark:bg-red-900 dark:text-red-200"
			>
				{error}
			</div>
		{/if}

		{#if success}
			<div
				class="mb-4 rounded border border-green-400 bg-green-100 px-4 py-3 text-green-700 dark:border-green-600 dark:bg-green-900 dark:text-green-200"
			>
				{success}
			</div>
		{/if}

		<div class="mb-4 flex gap-2">
			<button
				on:click={openCreateForm}
				class="flex items-center rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
			>
				<Icon icon="mdi:plus" class="mr-2 h-5 w-5" />
				Create Location
			</button>
			<button
				on:click={loadLocations}
				class="flex items-center rounded bg-green-500 px-4 py-2 font-bold text-white hover:bg-green-700"
			>
				<Icon icon="mdi:refresh" class="mr-2 h-5 w-5" />
				Refresh
			</button>
		</div>

		{#if showForm}
			<div class="mb-6 rounded bg-white px-8 py-6 shadow-md dark:bg-gray-800">
				<h2 class="mb-4 text-xl font-semibold">{isEditing ? 'Edit' : 'Create'} Location</h2>
				<div class="grid gap-4">
					<div>
						<label for="location-name" class="mb-1 block text-sm font-medium">Name</label>
						<input id="location-name" class="w-full rounded border px-3 py-2" bind:value={name} />
					</div>
					<div>
						<label for="location-address" class="mb-1 block text-sm font-medium">Address</label>
						<input
							id="location-address"
							class="w-full rounded border px-3 py-2"
							bind:value={address}
						/>
					</div>
				</div>
				<div class="mt-4 flex gap-2">
					<button
						on:click={handleSubmit}
						class="rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
						>{isEditing ? 'Update' : 'Create'}</button
					>
					<button
						on:click={closeForm}
						class="rounded bg-gray-500 px-4 py-2 font-bold text-white hover:bg-gray-700"
						>Cancel</button
					>
				</div>
			</div>
		{/if}

		{#if loading}
			<div class="py-8 text-center">
				<p class="text-gray-600 dark:text-gray-400">Loading locations...</p>
			</div>
		{:else if locations.length === 0}
			<div class="py-8 text-center">
				<p class="text-gray-600 dark:text-gray-400">No locations found.</p>
			</div>
		{:else}
			<div class="grid gap-4">
				{#each locations as loc (loc.id)}
					<div class="rounded bg-white px-8 py-6 shadow-md dark:bg-gray-800">
						<div class="flex items-start justify-between">
							<div class="flex-1 pr-4">
								<h3 class="text-lg font-semibold dark:text-white">{loc.name}</h3>
								<p class="text-gray-600 dark:text-gray-300">ID: {loc.id}</p>
								{#if loc.address}
									<p class="text-gray-600 dark:text-gray-300">{loc.address}</p>
								{/if}
							</div>
							<div class="flex gap-2">
								<button
									on:click={() => openEditForm(loc)}
									class="flex items-center rounded bg-yellow-500 px-3 py-1.5 text-white hover:bg-yellow-600"
								>
									<Icon icon="mdi:pencil" class="mr-1 h-4 w-4" /> Edit
								</button>
								<button
									on:click={() => deleteLocation(loc.id)}
									class="flex items-center rounded bg-red-500 px-3 py-1.5 text-white hover:bg-red-700"
								>
									<Icon icon="mdi:delete" class="mr-1 h-4 w-4" /> Delete
								</button>
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
</style>
