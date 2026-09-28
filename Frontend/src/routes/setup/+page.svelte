<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import api, { type BranchResponse, type SystemOptionResponse } from '$lib/api';
	import { isAuthenticated, isAdmin } from '$lib/stores';
	import Icon from '@iconify/svelte';
	import ConfirmModal from '$lib/ConfirmModal.svelte';

	let authed = false;
	let admin = false;
	let loading = true;

	// Data
	let branches: BranchResponse[] = [];
	let systemOptions: SystemOptionResponse[] = [];

	// Reactive filtered lists
	$: departments = systemOptions.filter((o) => o.category === 'Department');
	$: salutations = systemOptions.filter((o) => o.category === 'Salutation');
	$: jobLevels = systemOptions.filter((o) => o.category === 'Job Level');

	// Unified View Model
	$: sections = [
		{
			title: 'Branch',
			type: 'Branch',
			items: branches.map((b) => ({ id: b.id, key: 'Branch', value: b.branch_name, original: b }))
		},
		{
			title: 'Department',
			type: 'Department',
			items: departments.map((d) => ({
				id: d.id,
				key: 'Department',
				value: d.value,
				original: d
			}))
		},
		{
			title: 'Salutation',
			type: 'Salutation',
			items: salutations.map((s) => ({
				id: s.id,
				key: 'Salutation',
				value: s.value,
				original: s
			}))
		},
		{
			title: 'Job Level',
			type: 'Job Level',
			items: jobLevels.map((j) => ({
				id: j.id,
				key: 'Job Level',
				value: j.value,
				original: j
			}))
		}
	];

	// Modal State
	let showModal = false;
	let modalTitle = '';
	let modalType: 'Branch' | 'Department' | 'Salutation' | 'Job Level' = 'Branch';
	let editingId: number | null = null;
	let formValue = '';

	// Delete State
	let showDeleteConfirm = false;
	let deleteMessage = '';
	let itemToDelete: { id: number; type: string } | null = null;

	const unsub = isAuthenticated.subscribe((v) => (authed = v));
	const unsubAdmin = isAdmin.subscribe((v) => (admin = v));

	onMount(async () => {
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}
		if (admin) {
			await loadData();
		}
	});

	async function loadData() {
		loading = true;
		try {
			const [bRes, sRes] = await Promise.all([
				api.branchAPI.getAllBranches(),
				api.systemOptionsAPI.getAll()
			]);
			branches = bRes;
			systemOptions = sRes;
		} catch (error) {
			console.error('Failed to load data:', error);
		}
		loading = false;
	}

	function openAdd(type: string) {
		modalType = type as any;
		modalTitle = `Add ${type}`;
		editingId = null;
		formValue = '';
		showModal = true;
	}

	function openEdit(item: any, type: string) {
		modalType = type as any;
		modalTitle = `Edit ${type}`;
		editingId = item.id;
		formValue = item.value;
		showModal = true;
	}

	function openDelete(item: any, type: string) {
		itemToDelete = { id: item.id, type };
		deleteMessage = `Are you sure you want to delete ${type} '${item.value}'?`;
		showDeleteConfirm = true;
	}

	async function handleSave() {
		try {
			if (modalType === 'Branch') {
				if (editingId) {
					await api.branchAPI.updateBranch(editingId, { branch_name: formValue });
				} else {
					await api.branchAPI.createBranch({ branch_name: formValue });
				}
			} else {
				// System Options
				if (editingId) {
					await api.systemOptionsAPI.update(editingId, { value: formValue });
				} else {
					await api.systemOptionsAPI.create({ category: modalType, value: formValue });
				}
			}
			await loadData();
			showModal = false;
		} catch (error) {
			console.error('Save failed:', error);
			alert('Failed to save. ' + String(error));
		}
	}

	async function confirmDelete() {
		if (!itemToDelete) return;
		try {
			if (itemToDelete.type === 'Branch') {
				await api.branchAPI.deleteBranch(itemToDelete.id);
			} else {
				await api.systemOptionsAPI.delete(itemToDelete.id);
			}
			await loadData();
			showDeleteConfirm = false;
		} catch (error) {
			console.error('Delete failed:', error);
			alert('Failed to delete. ' + String(error));
		}
	}
</script>

<div class="container mx-auto p-6">
	<div class="mb-6 flex items-center justify-between">
		<h1 class="text-2xl font-bold text-gray-800 dark:text-white">Set up</h1>
		<button
			class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
			on:click={loadData}
			disabled={loading}
		>
			<Icon icon="mdi:refresh" class="h-5 w-5" />
		</button>
	</div>

	{#if loading}
		<div class="py-10 text-center text-gray-500">Loading setup data...</div>
	{:else}
		<div class="space-y-8">
			{#each sections as section}
				<div
					class="rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
				>
					<div class="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
						<h2 class="text-lg font-semibold text-gray-800 dark:text-white">{section.title}</h2>
						<button
							on:click={() => openAdd(section.type)}
							class="flex items-center gap-1 rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
						>
							<Icon icon="mdi:plus" class="h-4 w-4" />
							Add
						</button>
					</div>
					<div class="overflow-x-auto">
						<table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
							<thead class="bg-gray-50 dark:bg-gray-900">
								<tr>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">ID</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Key</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Value</th>
									<th class="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
								{#each section.items as item}
									<tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
										<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{item.id}</td>
										<td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white"
											>{item.key}</td
										>
										<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400"
											>{item.value}</td
										>
										<td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
											<button
												on:click={() => openEdit(item, section.type)}
												class="mr-3 inline-flex items-center gap-1 text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
											>
												<Icon icon="mdi:pencil" class="h-4 w-4" />
												Edit
											</button>
											<button
												on:click={() => openDelete(item, section.type)}
												class="inline-flex items-center gap-1 text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
											>
												<Icon icon="mdi:delete" class="h-4 w-4" />
												Delete
											</button>
										</td>
									</tr>
								{/each}
								{#if section.items.length === 0}
									<tr>
										<td colspan="4" class="px-6 py-4 text-center text-gray-500">No items found.</td>
									</tr>
								{/if}
							</tbody>
						</table>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<!-- Add/Edit Modal -->
{#if showModal}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
	>
		<div class="w-full max-w-md rounded-lg bg-white p-6 shadow-2xl dark:bg-gray-800 pointer-events-auto border border-gray-200 dark:border-gray-700">
			<h3 class="mb-4 text-xl font-bold text-gray-900 dark:text-white">{modalTitle}</h3>
			<form on:submit|preventDefault={handleSave}>
				<div class="mb-4">
					<label class="mb-2 block text-sm font-bold text-gray-700 dark:text-gray-300" for="value">
						Value
					</label>
					<input
						id="value"
						type="text"
						bind:value={formValue}
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none dark:bg-gray-700 dark:text-white dark:border-gray-600"
						required
						placeholder={`Enter ${modalType} value`}
					/>
				</div>
				<div class="flex justify-end gap-2">
					<button
						type="button"
						on:click={() => (showModal = false)}
						class="rounded bg-gray-200 px-4 py-2 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
					>
						Cancel
					</button>
					<button
						type="submit"
						class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
					>
						Save
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}

<!-- Delete Confirmation -->
<ConfirmModal
	bind:open={showDeleteConfirm}
	title="Confirm Deletion"
	message={deleteMessage}
	confirmText="Delete"
	cancelText="Cancel"
	on:confirm={confirmDelete}
	floating={true}
/>
