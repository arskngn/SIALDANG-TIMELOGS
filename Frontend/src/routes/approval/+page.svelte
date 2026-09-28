<script lang="ts">
	import { onMount } from 'svelte';
	import {
		timelogAPI,
		type TimelogResponse,
		type ProjectResponse,
		task_typeAPI,
		type TaskTypeResponse
	} from '$lib/api';
	import api from '$lib/api';
	import {
		isAuthenticated,
		username as usernameStore,
		isAdmin as isAdminStore,
		isAdmin,
		isManager
	} from '$lib/stores';
	import { addNotification } from '$lib/notifications';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Icon from '@iconify/svelte';

	let authed = false;
	let currentUsername = '';
	const unsubAuth = isAuthenticated.subscribe((v) => (authed = v));
	const unsubUser = usernameStore.subscribe((v) => (currentUsername = v));
	let admin = false;
	const unsubIsAdmin = isAdmin.subscribe((v) => (admin = v));
	let manager = false;
	const unsubManager = isManager.subscribe((v) => (manager = v));

	$: if (authed && !loading && !isAssignedManager && projects.length === 0 && _didApplyQuery) {
		// Only redirect if we've finished loading and determined they have no projects
		// But this is tricky with reactive statements.
		// Better to handle in onMount.
	}

	let logs: TimelogResponse[] = [];
	let filteredLogs: TimelogResponse[] = [];
	let pagedLogs: TimelogResponse[] = [];
	let totalPages = 1;
	let showingStart = 0;
	let showingEnd = 0;
	let canApprove = false;
	let canClear = false;
	let projects: ProjectResponse[] = [];
	let isAssignedManager = false;
	let canAct = false;
	let taskTypes: TaskTypeResponse[] = [];
	const FALLBACK_GENERIC_TASKS = [
		'training',
		'hr task',
		'it task',
		'admin task',
		'delivery assurance',
		'sick leave',
		'holidays',
		'vacation leave',
		'absent without office leave'
	];
	const fallbackNamesById: Record<number, string> = {};
	let loading = false;

	let status: 'All' | 'Pending' | 'Approved' | 'Rejected' = 'Pending';
	let appliedStatus: 'All' | 'Pending' | 'Approved' | 'Rejected' = 'Pending';
	let type: 'All' | 'project' | 'other' | 'leave' = 'All';
	let startDate = '';
	let endDate = '';
	let selectedProjectId: number | null = null;
	let search = '';
	let firstName = '';
	let lastName = '';
	let selectedTaskTypeId: number | null = null;
	import { page as pageStore } from '$app/stores';
	let highlightedId: number | null = null;
	let _didApplyQuery = false;

	let page = 1;
	let pageSize = 30;
	$: {
		const deps = {
			appliedStatus,
			type,
			selectedProjectId,
			startDate,
			endDate,
			search,
			firstName,
			lastName,
			selectedTaskTypeId,
			logs
		};
		filteredLogs = logs.filter(visible);
	}
	$: totalPages = Math.max(1, Math.ceil(filteredLogs.length / pageSize));
	$: page = Math.min(page, totalPages);
	$: pagedLogs = filteredLogs.slice((page - 1) * pageSize, page * pageSize);
	$: showingStart = filteredLogs.length === 0 ? 0 : (page - 1) * pageSize + 1;
	$: showingEnd = Math.min(page * pageSize, filteredLogs.length);
	$: selectedApprovedIds = selected.filter(
		(id) => logs.find((l) => l.id === id)?.status === 'Approved'
	);
	$: selectedRejectedIds = selected.filter(
		(id) => logs.find((l) => l.id === id)?.status === 'Rejected'
	);
	$: selectedPendingIds = selected.filter(
		(id) => logs.find((l) => l.id === id)?.status === 'Pending'
	);
	$: canApprove =
		selectedPendingIds.length > 0 ||
		((isAssignedManager || admin) && selectedRejectedIds.length > 0);
	$: canReject =
		selectedPendingIds.length > 0 ||
		((isAssignedManager || admin) && selectedApprovedIds.length > 0);
	// Reactive: limit task type list based on selected type
	$: taskTypesForFilter =
		type === 'project'
			? []
			: type === 'other'
				? taskTypes.filter((t) => t.category === 'other')
				: type === 'leave'
					? taskTypes.filter((t) => t.category === 'leave')
					: taskTypes;
	// Clear selection when switching to non-task-type category
	$: if (type === 'project') {
		selectedTaskTypeId = null;
	}

	let selected: number[] = [];
	function toggleRow(id: number, checked: boolean) {
		if (checked) {
			if (!selected.includes(id)) selected = [...selected, id];
		} else {
			selected = selected.filter((x) => x !== id);
		}
	}
	function selectAllPage() {
		const ids = pagedLogs.map((r: TimelogResponse) => r.id);
		const set = new Set([...selected, ...ids]);
		selected = Array.from(set);
	}
	function clearSelection() {
		selected = [];
	}
	async function clearRejected() {
		if (!(admin && appliedStatus === 'Rejected')) return;
		const ids = filteredLogs.map((r: TimelogResponse) => r.id);
		if (ids.length === 0) return;
		for (const id of ids) {
			await timelogAPI.remove(id).catch(() => {});
		}
		addNotification({
			title: 'Cleared Rejected',
			message: `Deleted ${ids.length} timelog(s)`,
			type: 'timelog'
		});
		logs = await timelogAPI.listManaged('All').catch(() => []);
		selected = [];
	}
	async function approveSelected() {
		const ids = [...selected];
		if (ids.length === 0) return;
		if (appliedStatus === 'Approved') return;
		await Promise.all(ids.map((id) => timelogAPI.update(id, { status: 'Approved' })));
		logs = await timelogAPI.listManaged('All').catch(() => []);
		selected = [];
	}
	async function rejectSelected() {
		const ids = [...selected];
		if (ids.length === 0) return;
		await Promise.all(ids.map((id) => timelogAPI.update(id, { status: 'Rejected' })));
		logs = await timelogAPI.listManaged('All').catch(() => []);
		selected = [];
	}

	onMount(async () => {
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}
		const params = $pageStore.url.searchParams;
		const qsStatus = params.get('status');
		const qsHighlight = params.get('highlight');
		if (
			qsStatus === 'Approved' ||
			qsStatus === 'Rejected' ||
			qsStatus === 'Pending' ||
			qsStatus === 'All'
		) {
			status = qsStatus as any;
		}
		if (qsHighlight && !Number.isNaN(Number(qsHighlight))) {
			highlightedId = Number(qsHighlight);
		}
		loading = true;
		taskTypes = await api.task_typeAPI.getAllPublic().catch(() => []);
		taskTypes.sort((a, b) => a.name.localeCompare(b.name));
		if (!taskTypes || taskTypes.length === 0) {
			taskTypes = FALLBACK_GENERIC_TASKS.map((name, idx) => {
				const id = -1 - idx;
				fallbackNamesById[id] = name;
				return {
					id,
					name,
					description: '',
					category: 'other',
					created_at: new Date().toISOString()
				} satisfies TaskTypeResponse;
			});
		}

		// Strict access control: Only assigned project managers can access
		// Even admins must be assigned to a project to see this page
		projects = await api.projectAPI.getMyManaged().catch(() => []);
		isAssignedManager = Array.isArray(projects) && projects.length > 0;

		logs = await timelogAPI.listManaged('All').catch(() => []);
		canAct = isAssignedManager || admin;
		loading = false;
		if (!_didApplyQuery && (qsStatus || qsHighlight)) {
			await applyFilters();
			_didApplyQuery = true;
			if (highlightedId !== null) {
				const el = document.getElementById(`row-${highlightedId}`);
				if (el) {
					el.scrollIntoView({ behavior: 'smooth', block: 'center' });
				}
				setTimeout(() => {
					if (highlightedId === Number(qsHighlight)) {
						highlightedId = null;
					}
				}, 5000);
			}
		}
		unsubAuth();
		unsubUser();
		unsubIsAdmin();
		unsubManager();
	});

	function projectName(id?: number): string {
		if (!id) return '';
		const p = projects.find((x) => x.id === id);
		return p ? p.project_name : String(id);
	}

	function typeNameFor(log: TimelogResponse): string {
		if (log.type === 'project') return 'Project';
		const t = taskTypes.find((tt) => tt.id === log.task_type_id);
		return t ? t.name : log.type === 'other' ? 'Other' : 'Leave';
	}

	function withinDates(iso: string): boolean {
		if (!startDate && !endDate) return true;
		const d = new Date(iso);
		if (startDate && d < new Date(startDate)) return false;
		if (endDate) {
			const e = new Date(endDate);
			e.setHours(23, 59, 59, 999);
			if (d > e) return false;
		}
		return true;
	}

	function matchesSearch(log: TimelogResponse): boolean {
		const text =
			`${log.description || ''} ${projectName(log.project_id)} ${typeNameFor(log)}`.toLowerCase();
		return text.includes(search.trim().toLowerCase());
	}

	function visible(log: TimelogResponse): boolean {
		if (appliedStatus !== 'All' && log.status !== appliedStatus) return false;
		if (type !== 'All' && log.type !== type) return false;

		if (selectedProjectId !== null) {
			if (!log.project_id || log.project_id !== selectedProjectId) return false;
		}
		if (!withinDates(log.start_time)) return false;
		if (search && !matchesSearch(log)) return false;
		if (firstName && !currentUsername.toLowerCase().includes(firstName.trim().toLowerCase()))
			return false;
		if (lastName && !currentUsername.toLowerCase().includes(lastName.trim().toLowerCase()))
			return false;
		if (selectedTaskTypeId !== null) {
			if (log.type === 'project') return false;
			const desc = (log.description || '').toLowerCase();
			let match = false;
			if (log.task_type_id && log.task_type_id === selectedTaskTypeId) match = true;
			else if (selectedTaskTypeId < 0) {
				const name = (fallbackNamesById[selectedTaskTypeId] || '').toLowerCase();
				if (name && desc.includes(name)) match = true;
			}
			if (!match) return false;
		}
		return true;
	}

	async function approve(id: number) {
		await timelogAPI.update(id, { status: 'Approved' });
		{
			const l = logs.find((x) => x.id === id);
			const title = 'Timelog Approved';
			const msg = l
				? `${typeNameFor(l)} · ${projectName(l.project_id)} · ${hours(l.duration_minutes)}h`
				: `ID ${id}`;
			addNotification({
				title,
				message: msg,
				type: l?.type === 'leave' ? 'leave' : 'timelog'
			});
		}
		logs = admin
			? await timelogAPI.listAll().catch(() => [])
			: await timelogAPI.listManaged('All').catch(() => []);
	}

	async function reject(id: number) {
		await timelogAPI.update(id, { status: 'Rejected' });
		{
			const l = logs.find((x) => x.id === id);
			const title = 'Timelog Rejected';
			const msg = l
				? `${typeNameFor(l)} · ${projectName(l.project_id)} · ${hours(l.duration_minutes)}h`
				: `ID ${id}`;
			addNotification({
				title,
				message: msg,
				type: l?.type === 'leave' ? 'leave' : 'timelog'
			});
		}
		logs = admin
			? await timelogAPI.listAll().catch(() => [])
			: await timelogAPI.listManaged('All').catch(() => []);
	}

	function resetFilters() {
		status = 'Pending';
		type = 'All';
		startDate = '';
		endDate = '';
		selectedProjectId = null;
		selectedTaskTypeId = null;
		search = '';
	}

	function resetProjects() {
		selectedProjectId = null;
	}
	function resetGenericTasks() {
		selectedTaskTypeId = null;
	}

	async function applyFilters() {
		appliedStatus = status;
		page = 1;
		// Refresh logs when changing status to ensure correct dataset
		if (admin) {
			logs = await timelogAPI.listAll().catch(() => []);
		} else if (isAssignedManager) {
			logs = await timelogAPI
				.listManaged(appliedStatus === 'All' ? 'All' : appliedStatus)
				.catch(() => []);
		} else {
			logs = await timelogAPI.listMine().catch(() => []);
		}
	}

	function hours(mins: number): string {
		return (mins / 60).toFixed(2);
	}
</script>

{#if !loading && !isAssignedManager && !admin}
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
	<div class="container mx-auto px-4 py-6">
		<h1 class="mb-4 text-2xl font-semibold dark:text-white">Timelogs For Approval</h1>

		<div class="rounded bg-white p-4 shadow dark:bg-gray-800">
			<div class="mb-3 text-sm font-semibold dark:text-white">Filter</div>
			<div class="grid grid-cols-12 gap-4">
				<div class="col-span-3">
					<label for="filter-status" class="mb-1 block text-sm text-neutral-700 dark:text-gray-300"
						>Status</label
					>
					<select
						id="filter-status"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						bind:value={status}
					>
						<option value="Pending">For Approval</option>
						<option value="All">All</option>
						<option value="Approved">Approved</option>
						<option value="Rejected">Rejected</option>
					</select>
				</div>
				<div class="col-span-3">
					<label for="filter-type" class="mb-1 block text-sm text-neutral-700 dark:text-gray-300"
						>Type</label
					>
					<select
						id="filter-type"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						bind:value={type}
					>
						<option value="All">All</option>
						<option value="project">Project</option>
						<option value="other">Other</option>
						<option value="leave">Leave</option>
					</select>
				</div>
				<div class="col-span-3">
					<label for="filter-start" class="mb-1 block text-sm text-neutral-700 dark:text-gray-300"
						>Start Date</label
					>
					<input
						id="filter-start"
						type="date"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						bind:value={startDate}
					/>
				</div>
				<div class="col-span-3">
					<label for="filter-end" class="mb-1 block text-sm text-neutral-700 dark:text-gray-300"
						>End Date</label
					>
					<input
						id="filter-end"
						type="date"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						bind:value={endDate}
					/>
				</div>
				<div class="col-span-3">
					<label for="filter-first" class="mb-1 block text-sm text-neutral-700 dark:text-gray-300"
						>First Name</label
					>
					<input
						id="filter-first"
						type="text"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						bind:value={firstName}
					/>
				</div>
				<div class="col-span-3">
					<label for="filter-last" class="mb-1 block text-sm text-neutral-700 dark:text-gray-300"
						>Last Name</label
					>
					<input
						id="filter-last"
						type="text"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						bind:value={lastName}
					/>
				</div>
				<div class="col-span-3">
					<label for="filter-search" class="mb-1 block text-sm text-neutral-700 dark:text-gray-300"
						>Task Summary</label
					>
					<input
						id="filter-search"
						type="text"
						placeholder="Task Summary"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						bind:value={search}
					/>
				</div>
				<div class="col-span-6">
					<div class="flex items-center justify-between">
						<label
							for="filter-projects"
							class="mb-1 block text-sm text-neutral-700 dark:text-gray-300">Projects</label
						>
						<button
							class="inline-flex items-center gap-1 text-xs text-blue-600 underline"
							on:click={resetProjects}
						>
							<Icon icon="mdi:refresh" class="h-4 w-4" />
							<span class="hidden sm:inline">Reset</span>
						</button>
					</div>
					<select
						id="filter-projects"
						class="w-full rounded border border-neutral-300 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						on:change={(e) => {
							const v = (e.target as HTMLSelectElement).value;
							selectedProjectId = v ? Number(v) : null;
						}}
					>
						<option value="">All Projects</option>
						{#each projects as p (p.id)}
							<option value={p.id} selected={selectedProjectId === p.id}>{p.project_name}</option>
						{/each}
					</select>
				</div>
				<div class="col-span-6">
					<div class="flex items-center justify-between">
						<label
							for="filter-generic"
							class="mb-1 block text-sm text-neutral-700 dark:text-gray-300">Generic Tasks</label
						>
						<button
							class="inline-flex items-center gap-1 text-xs text-blue-600 underline"
							on:click={resetGenericTasks}
						>
							<Icon icon="mdi:refresh" class="h-4 w-4" />
							<span class="hidden sm:inline">Reset</span>
						</button>
					</div>
					<select
						id="filter-generic"
						class="w-full rounded border border-neutral-300 bg-white p-2 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
						disabled={type === 'project'}
						on:change={(e) => {
							const v = (e.target as HTMLSelectElement).value;
							selectedTaskTypeId = v ? Number(v) : null;
						}}
					>
						<option value="">All Tasks</option>
						{#each taskTypesForFilter as tt (tt.id)}
							<option value={tt.id} selected={selectedTaskTypeId === tt.id}>{tt.name}</option>
						{/each}
					</select>
				</div>
			</div>
			<div class="mt-4 flex gap-2">
				<button
					class="inline-flex items-center gap-2 rounded bg-blue-600 px-3 py-1.5 text-sm text-white"
					on:click={applyFilters}
				>
					<Icon icon="mdi:check" class="h-4 w-4" />
					<span class="hidden sm:inline">Apply</span>
				</button>
				<button
					class="inline-flex items-center gap-2 rounded bg-neutral-200 px-3 py-1.5 text-sm text-neutral-800"
					on:click={resetFilters}
				>
					<Icon icon="mdi:refresh" class="h-4 w-4" />
					<span class="hidden sm:inline">Reset</span>
				</button>
			</div>
		</div>

		<div class="mt-6 rounded bg-white p-4 shadow dark:bg-gray-800">
			<div
				class="mb-2 flex items-center justify-between text-sm text-neutral-700 dark:text-gray-300"
			>
				<div>
					Total Records: {filteredLogs.length} &middot; Showing {showingStart}-{showingEnd} &middot;
					Rows per page: {pageSize}
				</div>
				<div class="flex items-center gap-2">
					<button
						class="rounded bg-neutral-200 px-2 py-1 text-neutral-800 disabled:opacity-50"
						on:click={() => (page = Math.max(1, page - 1))}
						disabled={page === 1}>Prev</button
					>
					<span>Page {page} of {totalPages}</span>
					<button
						class="rounded bg-neutral-200 px-2 py-1 text-neutral-800 disabled:opacity-50"
						on:click={() => (page = Math.min(totalPages, page + 1))}
						disabled={page >= totalPages}>Next</button
					>
				</div>
			</div>

			{#if canAct}
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
						on:click={rejectSelected}
						disabled={!canReject}
					>
						<Icon icon="mdi:close" class="h-4 w-4" />
						<span class="hidden sm:inline">Reject Selected</span>
					</button>
					<button
						class="inline-flex items-center gap-2 rounded bg-neutral-200 px-3 py-1.5 text-neutral-800"
						on:click={selectAllPage}
					>
						<Icon icon="mdi:select-all" class="h-4 w-4" />
						<span class="hidden sm:inline">Select All (page)</span>
					</button>
					<button
						class="inline-flex items-center gap-2 rounded bg-neutral-200 px-3 py-1.5 text-neutral-800 disabled:opacity-50"
						on:click={appliedStatus === 'Rejected' ? clearRejected : clearSelection}
						disabled={appliedStatus === 'Rejected' ? !canClear : selected.length === 0}
					>
						<Icon icon="mdi:broom" class="h-4 w-4" />
						<span class="hidden sm:inline">Clear</span>
					</button>
					<span class="text-xs text-neutral-600 dark:text-gray-300"
						>Selected: {selected.length}</span
					>
				</div>
			{/if}
			{#if loading}
				<div class="p-4 text-sm text-neutral-600 dark:text-gray-300">Loading...</div>
			{:else}
				<div class="space-y-2 sm:hidden">
					{#each pagedLogs as row (row.id)}
						<div
							class="rounded border border-gray-200 bg-white p-3 shadow-sm dark:border-gray-700 dark:bg-gray-800"
						>
							<div class="flex items-center justify-between">
								<div class="text-sm font-medium">
									{projectName(row.project_id) || typeNameFor(row)}
								</div>
								<div
									class="rounded px-2 py-0.5 text-xs font-semibold
								{row.status === 'Approved'
										? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
										: row.status === 'Rejected'
											? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
											: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300'}"
								>
									{row.status}
								</div>
							</div>
							<div class="mt-1 flex items-center justify-between text-xs text-neutral-500">
								<div>
									{row.first_name}
									{row.last_name}
								</div>
								<div>{new Date(row.start_time).toLocaleDateString()}</div>
							</div>
							<div class="mt-1 text-xs text-neutral-600 dark:text-gray-400">
								{hours(row.duration_minutes)}h
								{#if row.description}
									&middot; {row.description}
								{/if}
							</div>
							<div class="mt-2 flex justify-end gap-2">
								<label class="flex items-center gap-2 text-sm">
									<input
										type="checkbox"
										class="h-4 w-4 rounded border-gray-300"
										checked={selected.includes(row.id)}
										on:change={(e) => toggleRow(row.id, e.currentTarget.checked)}
									/>
									Select
								</label>
							</div>
						</div>
					{/each}
				</div>

				<div class="hidden sm:block">
					<table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
						<thead
							class="bg-gray-50 text-xs text-gray-700 uppercase dark:bg-gray-700 dark:text-gray-400"
						>
							<tr>
								<th class="px-4 py-3">
									<input
										type="checkbox"
										class="h-4 w-4 rounded border-gray-300"
										checked={selected.length > 0 && pagedLogs.every((x) => selected.includes(x.id))}
										on:change={(e) => {
											if (e.currentTarget.checked) selectAllPage();
											else clearSelection();
										}}
									/>
								</th>
								<th class="px-4 py-3">User</th>
								<th class="px-4 py-3">Project / Type</th>
								<th class="px-4 py-3">Date</th>
								<th class="px-4 py-3">Hours</th>
								<th class="px-4 py-3">Description</th>
								<th class="px-4 py-3">Status</th>
								{#if appliedStatus === 'Approved' || appliedStatus === 'Rejected'}
									<th class="px-4 py-3">Approver</th>
								{/if}
							</tr>
						</thead>
						<tbody>
							{#each pagedLogs as row (row.id)}
								<tr
									id={`row-${row.id}`}
									class="border-b bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-600 {highlightedId ===
									row.id
										? 'bg-yellow-50 dark:bg-yellow-900/20'
										: ''}"
								>
									<td class="px-4 py-3">
										<input
											type="checkbox"
											class="h-4 w-4 rounded border-gray-300"
											checked={selected.includes(row.id)}
											on:change={(e) => toggleRow(row.id, e.currentTarget.checked)}
										/>
									</td>
									<td class="px-4 py-3">
										<div class="font-medium text-gray-900 dark:text-white">
											{row.first_name}
											{row.last_name}
										</div>
										<div class="text-xs text-gray-500">{row.username}</div>
									</td>
									<td class="px-4 py-3">
										{projectName(row.project_id) || typeNameFor(row)}
									</td>
									<td class="px-4 py-3">
										{new Date(row.start_time).toLocaleDateString()}
										<div class="text-xs text-gray-400">
											{new Date(row.start_time).toLocaleTimeString([], {
												hour: '2-digit',
												minute: '2-digit'
											})}
										</div>
									</td>
									<td class="px-4 py-3">{hours(row.duration_minutes)}</td>
									<td class="px-4 py-3">
										<div class="max-w-xs truncate" title={row.description}>
											{row.description}
										</div>
									</td>
									<td class="px-4 py-3">
										<span
											class="rounded px-2 py-0.5 text-xs font-semibold
										{row.status === 'Approved'
												? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
												: row.status === 'Rejected'
													? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
													: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300'}"
										>
											{row.status}
										</span>
									</td>
									{#if appliedStatus === 'Approved' || appliedStatus === 'Rejected'}
										<td class="px-4 py-3 text-xs text-gray-500">
											{#if row.approver_name}
												<div>{row.approver_name}</div>
												{#if row.approved_at}
													<div class="text-gray-400">
														{new Date(row.approved_at).toLocaleDateString()}
													</div>
												{/if}
											{:else}
												-
											{/if}
										</td>
									{/if}
								</tr>
							{/each}
							{#if filteredLogs.length === 0}
								<tr>
									<td colspan="8" class="py-4 text-center text-gray-500"> No timelogs found </td>
								</tr>
							{/if}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</div>
{/if}
