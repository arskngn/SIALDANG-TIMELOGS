<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Icon from '@iconify/svelte';
	import { isAdmin, isAuthenticated } from '$lib/stores';
	import { addNotification } from '$lib/notifications';
import api, {
	API_BASE,
	type UserResponse,
	user201API,
	type User201FileResponse,
	type DocumentTypeResponse
} from '$lib/api';

	let authed = false;
	let admin = false;
	const unsubAuth = isAuthenticated.subscribe((v) => (authed = v));
	const unsubAdmin = isAdmin.subscribe((v) => (admin = v));

	let users: UserResponse[] = [];
	let items: User201FileResponse[] = [];
	let documentTypes: DocumentTypeResponse[] = [];
	let loading = false;
	let error: string | null = null;
	let success: string | null = null;

	let filterUserId: number | null = null;
	let search = '';
	let statusFilter: 'All' | 'Pending' | 'Approved' | 'Declined' = 'Pending';
	let firstName = '';
	let lastName = '';
	let startDate = '';
	let endDate = '';
	let filterDocTypeId: number | null = null;

	let page = 1;
	let pageSize = 30;
	let selected: number[] = [];
	let rejectModalOpen = false;
	let rejectRemarks = '';
let rejectLoading = false;
let rejectIds: number[] = [];
let rejectIndex = 0;
let perIdRemarks: Record<number, string> = {};

let previewOpen = false;
let previewLoading = false;
let previewItem: User201FileResponse | null = null;
let previewUrl = '';
	function normalizeFileUrl(raw: string): string {
		if (!raw) return '';
		if (raw.startsWith('/static/')) {
			return `${API_BASE}${raw}`;
		}
		return raw;
	}

	async function loadAll() {
		loading = true;
		error = null;
		try {
			users = await api.userAPI.getAllUsers();
			items = await user201API.listAll();
			documentTypes = await api.document_typeAPI.getAll();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load';
		} finally {
			loading = false;
		}
	}

	onMount(async () => {
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}
		if (!admin) {
			return;
		}
		await loadAll();
		unsubAuth();
		unsubAdmin();
	});

	function userName(id: number): string {
		const u = users.find((x) => x.id === id);
		const full = `${u?.first_name || ''} ${u?.last_name || ''}`.trim();
		return full || u?.username || String(id);
	}

	function getDocTypeNameById(id: number): string {
		const found = documentTypes.find((d) => d.id === id);
		return found ? found.name : '';
	}
	function isGovDoc(id: number): boolean {
		return documentTypes.find((d) => d.id === id)?.category === 'government';
	}
	
	// Helper function to extract file type from filename
	function getFileType(fileName?: string): string {
		if (!fileName) return '';
		const match = fileName.match(/\.([a-zA-Z0-9]+)$/);
		return match ? match[1].toUpperCase() : '';
	}
	
	$: filtered = items.filter((x) => {
		if (statusFilter !== 'All' && x.status !== statusFilter) return false;
		if (filterUserId && x.user_id !== filterUserId) return false;
		if (firstName.trim()) {
			const u = users.find((p) => p.id === x.user_id);
			const v = (u?.first_name || '').toLowerCase();
			if (!v.includes(firstName.trim().toLowerCase())) return false;
		}
		if (lastName.trim()) {
			const u = users.find((p) => p.id === x.user_id);
			const v = (u?.last_name || '').toLowerCase();
			if (!v.includes(lastName.trim().toLowerCase())) return false;
		}
		if (startDate) {
			const d = new Date(x.created_at || x.updated_at || '');
			const s = new Date(startDate);
			if (isFinite(d.getTime()) && isFinite(s.getTime())) {
				const floor = new Date(s.getFullYear(), s.getMonth(), s.getDate());
				if (d < floor) return false;
			}
		}
		if (endDate) {
			const d = new Date(x.created_at || x.updated_at || '');
			const e = new Date(endDate);
			if (isFinite(d.getTime()) && isFinite(e.getTime())) {
				const ceil = new Date(e.getFullYear(), e.getMonth(), e.getDate(), 23, 59, 59, 999);
				if (d > ceil) return false;
			}
		}
		if (filterDocTypeId) {
			if (x.document_type_id !== filterDocTypeId) return false;
		}
		const q = search.trim().toLowerCase();
		if (q) {
			const t =
				`${x.file_name || ''} ${getDocTypeNameById(x.document_type_id)} ${x.file_url || ''} ${x.notes || ''}`.toLowerCase();
			if (!t.includes(q)) return false;
		}
		return true;
	});
	$: totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
	$: page = Math.min(page, totalPages);
	$: paged = filtered.slice((page - 1) * pageSize, page * pageSize);
	$: showingStart = filtered.length === 0 ? 0 : (page - 1) * pageSize + 1;
	$: showingEnd = Math.min(page * pageSize, filtered.length);

	function toggleRow(id: number, checked: boolean) {
		if (checked) {
			if (!selected.includes(id)) selected = [...selected, id];
		} else {
			selected = selected.filter((x) => x !== id);
		}
	}
	function selectAllPage() {
		const ids = paged
			.filter((r) => !isGovDoc(r.document_type_id))
			.map((r: User201FileResponse) => r.id);
		const set = new Set([...selected, ...ids]);
		selected = Array.from(set);
	}
	function clearSelection() {
		selected = [];
	}
	$: selectedApprovedIds = selected.filter(
		(id) => items.find((l) => l.id === id)?.status === 'Approved'
	);
	$: selectedDeclinedIds = selected.filter(
		(id) => items.find((l) => l.id === id)?.status === 'Declined'
	);
	$: selectedPendingIds = selected.filter(
		(id) => items.find((l) => l.id === id)?.status === 'Pending'
	);
	$: selectedRejectableIds = selected.filter((id) => {
		const item = items.find((l) => l.id === id);
		if (!item) return false;
		if (isGovDoc(item.document_type_id)) return false;
		return item.status !== 'Declined';
	});
$: canApprove = selectedPendingIds.length > 0 && statusFilter !== 'Approved';
$: canReject = selectedRejectableIds.length > 0;

async function openPreview(item: User201FileResponse) {
	previewItem = item;
	previewOpen = true;
	previewLoading = true;
	previewUrl = '';
	let url = item.file_url || '';
	if (item.s3_path) {
		try {
			const pr = await user201API.presignDownload(item.s3_path);
			url = pr.download_url;
		} catch {
			url = item.file_url || '';
		}
	}
	previewUrl = normalizeFileUrl(url);
	previewLoading = false;
}

function closePreview() {
	previewOpen = false;
	previewItem = null;
	previewUrl = '';
}

async function downloadFile(item: User201FileResponse) {
	let url = item.file_url || '';
	if (item.s3_path) {
		try {
			const pr = await user201API.presignDownload(item.s3_path);
			url = pr.download_url;
		} catch {
			url = item.file_url || '';
		}
	}
	if (!url) return;
	url = normalizeFileUrl(url);
	try {
		const res = await fetch(url);
		if (!res.ok) {
			throw new Error('Download failed');
		}
		const blob = await res.blob();
		const objectUrl = URL.createObjectURL(blob);
		const link = document.createElement('a');
		const name = item.file_name || getDocTypeNameById(item.document_type_id) || 'document';
		link.href = objectUrl;
		link.download = name;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(objectUrl);
	} catch (e) {
		error = e instanceof Error ? e.message : 'Download failed';
	}
}

	async function approveSelected() {
		const ids = [...selectedPendingIds].filter((id) => {
			const item = items.find((i) => i.id === id);
			return item && !isGovDoc(item.document_type_id);
		});
		if (ids.length === 0) return;
		await Promise.all(ids.map((id) => user201API.approve(id)));
		// Record approvals for notification (owners will see notifications)
		for (const id of ids) {
			try {
				await api.notificationAPI.record201Approval(id, 'Approved');
			} catch (e) {
				console.error(`Failed to record approval notification for 201 file ${id}:`, e);
			}
		}
		items = await user201API.listAll().catch(() => []);
		selected = [];
	}
	function openRejectModal(idsOverride?: number[]) {
		const ids = (idsOverride ?? [...selectedRejectableIds]).filter((id) => {
			const item = items.find((i) => i.id === id);
			return item && !isGovDoc(item.document_type_id);
		});
		if (ids.length === 0) return;
		rejectIds = ids;
		rejectIndex = 0;
		perIdRemarks = {};
		rejectRemarks = '';
		rejectModalOpen = true;
	}
	function currentRejectId(): number | null {
		return rejectIds.length > 0 ? rejectIds[rejectIndex] : null;
	}
	function nextRejectStep() {
		const curr = currentRejectId();
		if (curr) {
			perIdRemarks[curr] = rejectRemarks.trim();
		}
		if (rejectIndex < rejectIds.length - 1) {
			rejectIndex += 1;
			const nextId = currentRejectId();
			rejectRemarks = nextId ? perIdRemarks[nextId] || '' : '';
		} else {
			confirmRejectAll();
		}
	}
	async function confirmRejectAll() {
		if (rejectIds.length === 0) {
			rejectModalOpen = false;
			return;
		}
		rejectLoading = true;
		try {
			for (const id of rejectIds) {
				const r = (perIdRemarks[id] || '').trim();
				await user201API.decline(id, r);
				try {
					await api.notificationAPI.record201Approval(id, 'Declined');
				} catch (e) {
					console.error(`Failed to record decline notification for 201 file ${id}:`, e);
				}
			}
			items = await user201API.listAll().catch(() => []);
			selected = [];
			rejectModalOpen = false;
			rejectRemarks = '';
			rejectIds = [];
			rejectIndex = 0;
			perIdRemarks = {};
		} finally {
			rejectLoading = false;
		}
	}
	async function rejectAllWithoutNotes() {
		if (rejectIds.length === 0) {
			rejectModalOpen = false;
			return;
		}
		rejectLoading = true;
		try {
			for (const id of rejectIds) {
				await user201API.decline(id, '');
				try {
					await api.notificationAPI.record201Approval(id, 'Declined');
				} catch (e) {
					console.error(`Failed to record decline notification for 201 file ${id}:`, e);
				}
			}
			items = await user201API.listAll().catch(() => []);
			selected = [];
			rejectModalOpen = false;
			rejectRemarks = '';
			rejectIds = [];
			rejectIndex = 0;
			perIdRemarks = {};
		} finally {
			rejectLoading = false;
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
		<h1 class="mb-6 text-2xl font-bold">201 Files For Approval</h1>

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

		<div class="rounded bg-white p-4 shadow dark:bg-gray-800">
			<div class="mb-3 text-sm font-semibold dark:text-white">Filter</div>
			<div class="grid grid-cols-12 gap-4">
				<div class="col-span-3">
					<label for="filter-status" class="mb-1 block text-sm">Status</label>
					<select
						id="filter-status"
						class="w-full rounded border px-3 py-2"
						bind:value={statusFilter}
					>
						<option value="Pending">For Approval</option>
						<option value="All">All</option>
						<option value="Approved">Approved</option>
						<option value="Declined">Declined</option>
					</select>
				</div>
				<div class="col-span-3">
					<label for="filter-doc" class="mb-1 block text-sm">Document Type</label>
					<select
						id="filter-doc"
						class="w-full rounded border px-3 py-2"
						bind:value={filterDocTypeId}
					>
						<option value={null}>All</option>
						{#each documentTypes.filter((d) => d.category !== 'government') as dt}
							<option value={dt.id}>{dt.name}</option>
						{/each}
					</select>
				</div>
				<div class="col-span-3">
					<label for="filter-start" class="mb-1 block text-sm">Start Date</label>
					<input
						id="filter-start"
						type="date"
						class="w-full rounded border px-3 py-2"
						bind:value={startDate}
					/>
				</div>
				<div class="col-span-3">
					<label for="filter-end" class="mb-1 block text-sm">End Date</label>
					<input
						id="filter-end"
						type="date"
						class="w-full rounded border px-3 py-2"
						bind:value={endDate}
					/>
				</div>
				<div class="col-span-3">
					<label for="filter-first" class="mb-1 block text-sm">First Name</label>
					<input
						id="filter-first"
						type="text"
						class="w-full rounded border px-3 py-2"
						bind:value={firstName}
					/>
				</div>
				<div class="col-span-3">
					<label for="filter-last" class="mb-1 block text-sm">Last Name</label>
					<input
						id="filter-last"
						type="text"
						class="w-full rounded border px-3 py-2"
						bind:value={lastName}
					/>
				</div>
				<div class="col-span-6">
					<label for="filter-search" class="mb-1 block text-sm">Search</label>
					<input
						id="filter-search"
						type="text"
						class="w-full rounded border px-3 py-2"
						bind:value={search}
					/>
				</div>
			</div>
			<div class="mt-3 flex gap-2">
				<button class="rounded bg-blue-600 px-3 py-1.5 text-white">Apply</button>
				<button
					class="rounded bg-neutral-200 px-3 py-1.5"
					on:click={() => {
						firstName = '';
						lastName = '';
						startDate = '';
						endDate = '';
						filterDocTypeId = null;
						search = '';
						filterUserId = null;
						statusFilter = 'Pending';
						page = 1;
					}}>Reset</button
				>
			</div>
		</div>

		<div class="mt-3 text-sm text-gray-600 dark:text-gray-300">
			Total Records: {filtered.length} · Showing {showingStart}-{showingEnd} · Rows per page: {pageSize}
		</div>
		<div class="mb-2 flex items-center gap-2">
			<button
				class="inline-flex items-center gap-2 rounded bg-green-600 px-3 py-1.5 text-white disabled:opacity-50"
				on:click={approveSelected}
				disabled={!canApprove}
			>
				<Icon icon="mdi:check" class="h-4 w-4" />
				<span class="hidden sm:inline">Approve Selected</span>
			</button>
			<button
				class="inline-flex items-center gap-2 rounded bg-red-600 px-3 py-1.5 text-white disabled:opacity-50"
				on:click={() => openRejectModal()}
				disabled={!canReject}
			>
				<Icon icon="mdi:close" class="h-4 w-4" />
				<span class="hidden sm:inline">Reject Selected</span>
			</button>
			<button
				class="inline-flex items-center gap-2 rounded bg-neutral-200 px-3 py-1.5 text-neutral-800"
				on:click={selectAllPage}
			>
				Select All (page)
			</button>
			<button
				class="inline-flex items-center gap-2 rounded bg-neutral-200 px-3 py-1.5 text-neutral-800"
				on:click={clearSelection}
			>
				Clear
			</button>
			<span class="text-sm">Selected: {selected.length}</span>
			<span class="ml-auto text-sm">Page {page} of {totalPages}</span>
			<div class="flex gap-2">
				<button
					class="rounded bg-neutral-200 px-3 py-1.5 text-neutral-800 disabled:opacity-50"
					disabled={page <= 1}
					on:click={() => (page = Math.max(1, page - 1))}
				>
					Prev
				</button>
				<button
					class="rounded bg-neutral-200 px-3 py-1.5 text-neutral-800 disabled:opacity-50"
					disabled={page >= totalPages}
					on:click={() => (page = Math.min(totalPages, page + 1))}
				>
					Next
				</button>
			</div>
		</div>

		{#if loading}
			<div class="py-8 text-center">
				<span class="text-gray-600 dark:text-gray-400">Loading...</span>
			</div>
		{:else if filtered.length === 0}
			<div class="py-8 text-center">
				<span class="text-gray-600 dark:text-gray-400">No records found.</span>
			</div>
		{:else}
			<div class="overflow-x-auto rounded bg-white p-2 shadow-md dark:bg-gray-800">
				<table class="w-full table-auto">
					<thead>
						<tr class="text-left text-sm text-gray-600 dark:text-gray-300">
							<th class="px-4 py-3">Select</th>
							<th class="px-4 py-3">Resource</th>
							<th class="px-4 py-3">Type</th>
							<th class="px-4 py-3">File Name</th>
							<th class="px-4 py-3">Preview</th>
							<th class="px-4 py-3">Download</th>
							<th class="px-4 py-3">Uploaded</th>
							<th class="px-4 py-3">Status</th>
							<th class="px-4 py-3">Notes</th>
						</tr>
					</thead>
					<tbody>
						{#each paged as item (item.id)}
							<tr class="border-t text-sm text-gray-700 dark:text-gray-200">
								<td class="px-4 py-3"
									><input
										type="checkbox"
										checked={selected.includes(item.id)}
										disabled={isGovDoc(item.document_type_id)}
										on:change={(e) => toggleRow(item.id, (e.target as HTMLInputElement).checked)}
									/></td
								>
								<td class="px-4 py-3">{userName(item.user_id)}</td>
								<td class="px-4 py-3">{getDocTypeNameById(item.document_type_id)}</td>
								<td class="px-4 py-3">{item.file_name}</td>
								<td class="px-4 py-3">
									<button
										class="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-1 text-xs text-blue-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-blue-300 dark:hover:bg-gray-600"
										on:click={() => openPreview(item)}
									>
										<Icon icon="mdi:eye" class="h-4 w-4" />
										<span>Preview</span>
									</button>
								</td>
								<td class="px-4 py-3">
									<button
										class="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-1 text-xs text-blue-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-blue-300 dark:hover:bg-gray-600"
										on:click={() => downloadFile(item)}
									>
										<Icon icon="mdi:download" class="h-4 w-4" />
										<span>Download</span>
										{#if item.file_name}
											<span class="text-gray-600 dark:text-gray-400">
												({getFileType(item.file_name)})
											</span>
										{/if}
									</button>
								</td>
								<td class="px-4 py-3">{item.created_at || ''}</td>
								<td class="px-4 py-3">
									<span
										class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs"
										class:!bg-yellow-100={item.status === 'Pending'}
										class:!bg-green-100={item.status === 'Approved'}
										class:!bg-red-100={item.status === 'Declined'}
									>
										{item.status}
									</span>
									{#if item.remarks}
										<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
											{item.remarks}
										</div>
									{/if}
								</td>
								<td class="px-4 py-3">{item.notes || ''}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	{#if previewOpen && previewItem}
		<div
			class="fixed inset-0 z-50 flex items-center justify-center p-4"
			style="background: rgba(0,0,0,0.2); backdrop-filter: blur(2px);"
		>
			<div
				class="h-auto max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border bg-white p-4 shadow-2xl dark:border-gray-700 dark:bg-gray-800"
			>
				<div class="mb-4 flex items-center justify-between border-b pb-3 dark:border-gray-700">
					<div class="text-lg font-semibold dark:text-white">
						{previewItem.file_name}
					</div>
					<button
						class="rounded bg-gray-100 p-2 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600"
						on:click={closePreview}
					>
						<Icon icon="mdi:close" class="h-5 w-5" />
					</button>
				</div>

				{#if previewLoading}
					<div class="flex justify-center p-8">
						<div
							class="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"
						></div>
					</div>
				{:else if previewUrl}
					{#if (previewItem.file_name || '').toLowerCase().endsWith('.pdf')}
						<iframe
							src={previewUrl}
							title={previewItem.file_name}
							class="h-[70vh] w-full rounded border bg-gray-50"
						></iframe>
					{:else}
						<img
							src={previewUrl}
							alt={previewItem.file_name}
							class="max-h-[70vh] w-full rounded bg-gray-100 object-contain dark:bg-gray-700"
						/>
					{/if}
				{:else}
					<div
						class="flex h-56 w-full items-center justify-center rounded bg-gray-100 dark:bg-gray-700"
					>
						<span class="text-gray-400">No Preview</span>
					</div>
				{/if}
			</div>
		</div>
	{/if}

	{#if rejectModalOpen}
		<div
			class="fixed inset-0 z-50 flex items-center justify-center p-4"
			style="background: rgba(0,0,0,0.2); backdrop-filter: blur(2px);"
		>
			<div
				class="w-full max-w-lg rounded-lg border bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-800"
			>
				<div class="mb-4 flex items-center justify-between border-b pb-3 dark:border-gray-700">
					<div class="text-lg font-semibold dark:text-white">
						Reject {rejectIds.length > 1 ? 'Files' : 'File'}
					</div>
					<button
						class="rounded bg-gray-100 p-2 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600"
						on:click={() => (rejectModalOpen = false)}
						disabled={rejectLoading}
					>
						<Icon icon="mdi:close" class="h-5 w-5" />
					</button>
				</div>

				{#if currentRejectId() !== null}
					{#key currentRejectId()}
						<div class="mb-3 text-sm dark:text-white">
							<div>
								<span class="font-semibold">User:</span>
								{userName(items.find((i) => i.id === currentRejectId())?.user_id || 0)}
							</div>
							<div>
								<span class="font-semibold">Type:</span>
								{getDocTypeNameById(
									items.find((i) => i.id === currentRejectId())?.document_type_id || 0
								)}
							</div>
							<div>
								<span class="font-semibold">File:</span>
								{items.find((i) => i.id === currentRejectId())?.file_name}
							</div>
							<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
								Item {rejectIndex + 1} of {rejectIds.length}
							</div>
						</div>
						<div class="mb-4">
							<label for="reject-remarks" class="mb-2 block text-sm dark:text-white">Remarks</label>
							<textarea
								id="reject-remarks"
								bind:value={rejectRemarks}
								class="w-full rounded border p-2 dark:bg-gray-700 dark:text-white"
								placeholder="Enter reason for rejection"
							></textarea>
						</div>
					{/key}
				{/if}

				<div class="flex justify-end gap-2">
					<button
						class="rounded bg-gray-200 px-4 py-2 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
						on:click={() => (rejectModalOpen = false)}
						disabled={rejectLoading}
					>
						Cancel
					</button>
					<button
						class="rounded bg-red-500 px-4 py-2 text-white hover:bg-red-600 disabled:opacity-50"
						on:click={rejectAllWithoutNotes}
						disabled={rejectLoading}
					>
						Reject Without Notes
					</button>
					<button
						class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
						on:click={nextRejectStep}
						disabled={rejectLoading}
					>
						{rejectIndex < rejectIds.length - 1 ? 'Next' : 'Reject'}
					</button>
				</div>
			</div>
		</div>
	{/if}
{/if}

<style>
	button {
		cursor: pointer;
	}
</style>

