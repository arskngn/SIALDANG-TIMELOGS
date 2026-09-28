<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Icon from '@iconify/svelte';
	import { timelogAPI, projectAPI, type TimelogResponse, type ProjectResponse } from '$lib/api';
	import api from '$lib/api';
	import { isAuthenticated, userRole } from '$lib/stores';
	import { utils, writeFile } from 'xlsx';

	type UserOption = { id: number; first_name: string; last_name: string };

	let authed = false;
	let role = '';
	let logs: TimelogResponse[] = [];
	let projects: ProjectResponse[] = [];
	let loading = true;
	let error = '';
	let startDate = '';
	let endDate = '';

	// Project / approver dropdown filters
	let selectedProjectId: number | 'All' = 'All';
	let selectedApprover: string | 'All' = 'All';

	// Search User (privileged only) - combobox over user_id/first_name/last_name
	let userSearchQuery = '';
	let selectedUserId: number | null = null;
	let showUserDropdown = false;
	let filteredLogs: TimelogResponse[] = [];
	let pagedLogs: TimelogResponse[] = [];
	let totalMinutes = 0;
	let totalHours = '0.00';
	let currentPage = 1;
	const pageSize = 20;
	let maxPage = 1;

	const unsubAuth = isAuthenticated.subscribe((v) => (authed = v));
	const unsubRole = userRole.subscribe((v) => (role = v));

	// Single source of truth for what this view is allowed to do.
	// Everything else (API call, filters shown, export columns) branches off this.
	$: isPrivileged = ['admin'].includes((role || '').toLowerCase());

	async function loadTimelogs() {
		loading = true;
		error = '';
		try {
			const fetchLogs = isPrivileged ? timelogAPI.listAll() : timelogAPI.listMine();
			// TODO: replace with the real "all projects" endpoint for admin/manager.
			// Falls back to the user's own assigned projects if it doesn't exist.
			const fetchProjects = isPrivileged
				? (api.projectAPI?.getAllProjects?.() ?? api.userAPI.getMyProjects())
				: api.userAPI.getMyProjects();

			const [mine, allProjects] = await Promise.all([
				fetchLogs.catch(() => []),
				fetchProjects.catch(() => [])
			]);
			logs = mine || [];
			projects = (allProjects as ProjectResponse[] | undefined) || [];
		} catch (e) {
			error = 'Failed to load timelogs';
		} finally {
			loading = false;
		}
	}

	function handleSearch() {
		currentPage = 1;
		loadTimelogs();
	}

	onMount(async () => {
		if (!authed) {
			goto(resolve('/login'));
			return;
		}

		await loadTimelogs();
		unsubAuth();
		unsubRole();
	});

	$: projectNameById = new Map<number, string>(projects.map((p) => [p.id, p.project_name]));

	// Dropdown option sets, derived from the full (unfiltered) loaded logs so
	// selecting one filter doesn't shrink the options available to another.
	$: approverOptions = Array.from(
		new Set(logs.map((l) => l.approver_name).filter((n): n is string => !!n && n.trim().length > 0))
	).sort((a, b) => a.localeCompare(b));

	$: userOptions = (() => {
		const map = new Map<number, UserOption>();
		for (const l of logs) {
			if (l.user_id != null && !map.has(l.user_id)) {
				map.set(l.user_id, {
					id: l.user_id,
					first_name: l.first_name || '',
					last_name: l.last_name || ''
				});
			}
		}
		return Array.from(map.values()).sort((a, b) =>
			`${a.last_name}${a.first_name}`.localeCompare(`${b.last_name}${b.first_name}`)
		);
	})();

	$: filteredUserOptions = userOptions.filter((u) => {
		if (!userSearchQuery.trim()) return true;
		const q = userSearchQuery.trim().toLowerCase();
		return (
			String(u.id).includes(q) ||
			u.first_name.toLowerCase().includes(q) ||
			u.last_name.toLowerCase().includes(q)
		);
	});

	function selectUser(u: UserOption) {
		selectedUserId = u.id;
		userSearchQuery = `${u.id} - ${u.first_name} ${u.last_name}`.trim();
		showUserDropdown = false;
	}

	function clearUserSelection() {
		selectedUserId = null;
		userSearchQuery = '';
	}

	function formatDate(d: string) {
		if (!d) return '';
		const dt = new Date(d);
		if (Number.isNaN(dt.getTime())) return d;
		return dt.toLocaleDateString();
	}

	function formatTimeRange(start: string, end: string) {
		if (!start || !end) return '';
		const s = new Date(start);
		const e = new Date(end);
		if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return '';
		const opts: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit' };
		return `${s.toLocaleTimeString([], opts)} – ${e.toLocaleTimeString([], opts)}`;
	}

	function hoursFromMinutes(mins: number) {
		if (!mins || mins <= 0) return '0 h';
		const h = mins / 60;
		return `${h.toFixed(2)} h`;
	}

	function matchesDateRange(log: TimelogResponse) {
		if (!startDate && !endDate) return true;
		const d = new Date(log.start_time);
		if (Number.isNaN(d.getTime())) return true;
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		const iso = `${y}-${m}-${day}`;
		if (startDate && iso < startDate) return false;
		if (endDate && iso > endDate) return false;
		return true;
	}

	function matchesProject(log: TimelogResponse) {
		if (selectedProjectId === 'All') return true;
		return log.project_id === selectedProjectId;
	}

	function matchesUserFilters(log: TimelogResponse) {
		if (isPrivileged && selectedUserId !== null && log.user_id !== selectedUserId) return false;
		if (selectedApprover !== 'All' && (log.approver_name || '') !== selectedApprover) return false;
		return true;
	}


	function matchesApprovedOnly(log: TimelogResponse) {
		return log.status === 'Approved';
	}

	function toCsvValue(v: unknown) {
		const s = String(v ?? '');
		const escaped = s.replace(/"/g, '""');
		return `"${escaped}"`;
	}

	function exportCsv(allColumns: boolean) {
		if (typeof window === 'undefined') return;
		const rows: string[] = [];
		if (filteredLogs.length === 0) return;
		if (allColumns) {
			const headers = [
				'ID',
				'Date',
				'Project',
				'Type',
				'Start Time',
				'End Time',
				'Duration Hours',
				'Status',
				'Description',
				'Approver'
			];
			if (isPrivileged) headers.push('User ID', 'First Name', 'Last Name');
			rows.push(headers.map(toCsvValue).join(','));
		} else {
			rows.push(
				['Date', 'Project', 'Type', 'Time Range', 'Duration Hours', 'Description']
					.map(toCsvValue)
					.join(',')
			);
		}
		for (const log of filteredLogs) {
			if (allColumns) {
				const row = [
					log.id,
					formatDate(log.start_time),
					projectNameById.get(log.project_id || -1) || '',
					log.type,
					log.start_time,
					log.end_time,
					(log.duration_minutes / 60).toFixed(2),
					log.status,
					log.description || '',
					log.approver_name || ''
				];
				if (isPrivileged) row.push(log.user_id, log.first_name || '', log.last_name || '');
				rows.push(row.map(toCsvValue).join(','));
			} else {
				rows.push(
					[
						formatDate(log.start_time),
						projectNameById.get(log.project_id || -1) || '',
						log.type,
						formatTimeRange(log.start_time, log.end_time),
						hoursFromMinutes(log.duration_minutes),
						log.description || ''
					]
						.map(toCsvValue)
						.join(',')
				);
			}
		}
		const blob = new Blob([rows.join('\r\n')], {
			type: 'text/csv;charset=utf-8;'
		});
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = allColumns ? 'timelogs_full.csv' : 'timelogs_limited.csv';
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	function exportXlsx() {
		if (filteredLogs.length === 0) return;

		const data = filteredLogs.map((log) => {
			const row: Record<string, unknown> = {
				ID: log.id,
				Date: formatDate(log.start_time),
				Project: projectNameById.get(log.project_id || -1) || '',
				Type: log.type,
				'Start Time': log.start_time,
				'End Time': log.end_time,
				'Duration Hours': (log.duration_minutes / 60).toFixed(2),
				Status: log.status,
				Description: log.description || '',
				Approver: log.approver_name || ''
			};
			if (isPrivileged) {
				row['User ID'] = log.user_id;
				row['First Name'] = log.first_name || '';
				row['Last Name'] = log.last_name || '';
			}
			return row;
		});

		const ws = utils.json_to_sheet(data);
		const wb = utils.book_new();
		utils.book_append_sheet(wb, ws, 'Timelogs');
		writeFile(wb, 'timelogs.xlsx');
	}

	$: {
		const base = logs.filter(
			(l) =>
				matchesDateRange(l) && matchesProject(l) && matchesUserFilters(l) && matchesApprovedOnly(l)
		);
		filteredLogs = base;
		totalMinutes = base.reduce((sum, l) => sum + (l.duration_minutes || 0), 0);
		totalHours = (totalMinutes / 60).toFixed(2);
		maxPage = Math.max(1, Math.ceil(base.length / pageSize));
		if (currentPage > maxPage) currentPage = maxPage;
		if (currentPage < 1) currentPage = 1;
		const start = (currentPage - 1) * pageSize;
		pagedLogs = base.slice(start, start + pageSize);
	}
</script>

<div class="min-h-screen bg-gray-50 px-4 py-8 dark:bg-gray-900">
	<div class="mx-auto max-w-6xl">
		<div class="mb-6">
			<h1 class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
				{isPrivileged ? 'Detailed Timelogs' : 'My Timelogs'}
			</h1>
		</div>

		<div
			class="rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
		>
			<div class="border-b border-gray-200 px-4 py-3 dark:border-gray-700">
				<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">Filter</div>
				<div class="text-xs text-gray-500 dark:text-gray-400">Fields with * are required</div>
			</div>
			<div class="space-y-4 px-4 pt-3 pb-4">
				<!-- Top row: start date, end date, project, approver, search -->
				<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
					<div class="space-y-1">
						<label
							for="start-date"
							class="block text-xs font-semibold tracking-wide text-gray-700 uppercase dark:text-gray-300"
							>Start Date *</label
						>
						<input
							id="start-date"
							type="date"
							bind:value={startDate}
							class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
						/>
					</div>
					<div class="space-y-1">
						<label
							for="end-date"
							class="block text-xs font-semibold tracking-wide text-gray-700 uppercase dark:text-gray-300"
							>End Date *</label
						>
						<input
							id="end-date"
							type="date"
							bind:value={endDate}
							class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
						/>
					</div>
					<div class="space-y-1">
						<label
							for="filter-project"
							class="block text-xs font-semibold tracking-wide text-gray-700 uppercase dark:text-gray-300"
							>Project</label
						>
						<select
							id="filter-project"
							bind:value={selectedProjectId}
							class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
						>
							<option value={'All'}>All Projects</option>
							{#each projects as p}
								<option value={p.id}>{p.project_name}</option>
							{/each}
						</select>
					</div>
					<div class="space-y-1">
						<label
							for="filter-approver"
							class="block text-xs font-semibold tracking-wide text-gray-700 uppercase dark:text-gray-300"
							>Approver</label
						>
						<select
							id="filter-approver"
							bind:value={selectedApprover}
							class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
						>
							<option value={'All'}>All</option>
							{#each approverOptions as a}
								<option value={a}>{a}</option>
							{/each}
						</select>
					</div>
					<div class="space-y-1">
						<span
							class="invisible block text-xs font-semibold tracking-wide text-gray-700 uppercase dark:text-gray-300"
							>Action</span
						>
						<button
							type="button"
							on:click={handleSearch}
							class="inline-flex w-full items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
						>
							<Icon icon="mdi:magnify" class="mr-2 h-4 w-4" />
							Search Now
						</button>
					</div>
				</div>

				<!-- Bottom row: search user (privileged only), CTO checkbox -->
				<div class="flex flex-wrap items-end gap-4">
					{#if isPrivileged}
						<div class="relative w-full max-w-sm space-y-1">
							<label
								for="search-user"
								class="block text-xs font-semibold tracking-wide text-gray-700 uppercase dark:text-gray-300"
								>Search User</label
							>
							<div class="relative">
								<input
									id="search-user"
									type="text"
									placeholder="Search by ID, first or last name"
									bind:value={userSearchQuery}
									on:input={() => (selectedUserId = null)}
									on:focus={() => (showUserDropdown = true)}
									on:blur={() => setTimeout(() => (showUserDropdown = false), 150)}
									class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 pr-8 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
								/>
								{#if selectedUserId !== null}
									<button
										type="button"
										on:click={clearUserSelection}
										class="absolute top-1/2 right-2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
										aria-label="Clear user filter"
									>
										<Icon icon="mdi:close" class="h-4 w-4" />
									</button>
								{/if}
							</div>
							{#if showUserDropdown && filteredUserOptions.length > 0}
								<ul
									class="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-md border border-gray-200 bg-white text-sm shadow-lg dark:border-gray-700 dark:bg-gray-900"
								>
									{#each filteredUserOptions as u}
										<li>
											<button
												type="button"
												on:mousedown|preventDefault={() => selectUser(u)}
												class="block w-full px-3 py-1.5 text-left text-gray-900 hover:bg-gray-100 dark:text-gray-100 dark:hover:bg-gray-800"
											>
												{u.id} - {u.first_name}
												{u.last_name}
											</button>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/if}
				</div>
			</div>
		</div>

		<div class="mt-4 flex flex-wrap items-center justify-between gap-3">
			<div class="flex flex-wrap gap-2">
				<button
					type="button"
					on:click={() => exportCsv(true)}
					class="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700"
				>
					<Icon icon="mdi:file-delimited" class="mr-1 h-4 w-4" />
					Export List as CSV
				</button>
				<button
					type="button"
					on:click={() => exportCsv(false)}
					class="inline-flex items-center rounded-md bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-600"
				>
					<Icon icon="mdi:file-delimited-outline" class="mr-1 h-4 w-4" />
					Export Limited Columns as CSV
				</button>
				<button
					type="button"
					on:click={exportXlsx}
					class="inline-flex items-center rounded-md bg-green-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-green-700"
				>
					<Icon icon="mdi:file-excel" class="mr-1 h-4 w-4" />
					Export List as XLSX
				</button>
			</div>
			<div class="text-sm text-gray-700 dark:text-gray-200">
				Total Records: {filteredLogs.length} · Total Spent Hours: {totalHours}
			</div>
		</div>

		{#if loading}
			<div
				class="mt-6 rounded-md border border-gray-200 bg-white p-6 text-center text-gray-600 shadow-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
			>
				Loading timelogs...
			</div>
		{:else if error}
			<div
				class="mt-6 rounded-md border border-red-200 bg-red-50 p-6 text-center text-red-700 shadow-sm dark:border-red-700 dark:bg-red-900 dark:text-red-200"
			>
				{error}
			</div>
		{:else if filteredLogs.length === 0}
			<div
				class="mt-6 rounded-md border border-gray-200 bg-white p-6 text-center text-gray-600 shadow-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
			>
				No timelogs found for the selected filters.
			</div>
		{:else}
			<div
				class="mt-4 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
			>
				<div
					class="flex items-center justify-between border-b border-gray-200 px-4 py-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200"
				>
					<div class="flex items-center gap-2">
						<Icon icon="mdi:check-circle" class="h-4 w-4 text-green-500" />
						<span>{filteredLogs.length} timelog{filteredLogs.length === 1 ? '' : 's'}</span>
					</div>
				</div>
				<div class="max-h-[540px] overflow-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
						<thead class="bg-gray-50 dark:bg-gray-900">
							<tr>
								<th class="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
									Date
								</th>
								<th class="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
									Project
								</th>
								<th class="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
									Type
								</th>
								<th class="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
									Time
								</th>
								<th class="px-4 py-2 text-right font-semibold text-gray-700 dark:text-gray-200">
									Duration
								</th>
								<th class="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
									Status
								</th>
								<th class="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
									Description
								</th>
								<th class="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">
									Approver
								</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
							{#each pagedLogs as log}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-900">
									<td class="px-4 py-2 whitespace-nowrap text-gray-900 dark:text-gray-100">
										{formatDate(log.start_time)}
									</td>
									<td class="px-4 py-2 whitespace-nowrap text-gray-900 dark:text-gray-100">
										{projectNameById.get(log.project_id || -1) || 'N/A'}
									</td>
									<td
										class="px-4 py-2 whitespace-nowrap text-gray-900 capitalize dark:text-gray-100"
									>
										{log.type}
									</td>
									<td class="px-4 py-2 whitespace-nowrap text-gray-900 dark:text-gray-100">
										{formatTimeRange(log.start_time, log.end_time)}
									</td>
									<td
										class="px-4 py-2 text-right whitespace-nowrap text-gray-900 dark:text-gray-100"
									>
										{hoursFromMinutes(log.duration_minutes)}
									</td>
									<td class="px-4 py-2 whitespace-nowrap text-gray-900 dark:text-gray-100">
										<span
											class:text-green-600={log.status === 'Approved'}
											class:text-red-600={log.status === 'Rejected'}
											class:text-yellow-600={log.status === 'Pending'}
											class="font-medium"
										>
											{log.status}
										</span>
									</td>
									<td class="max-w-xs px-4 py-2 text-gray-900 dark:text-gray-100">
										<div class="line-clamp-2 text-xs text-ellipsis sm:text-sm">
											{log.description || 'No description'}
										</div>
									</td>
									<td class="px-4 py-2 whitespace-nowrap text-gray-900 dark:text-gray-100">
										{log.approver_name || 'N/A'}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		{#if filteredLogs.length > pageSize}
			<div class="mt-4 flex items-center justify-between text-sm text-gray-700 dark:text-gray-200">
				<div>Page {currentPage} of {maxPage}</div>
				<div class="inline-flex rounded-md shadow-sm">
					<button
						type="button"
						on:click={() => currentPage > 1 && currentPage--}
						class="rounded-l-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
					>
						Previous
					</button>
					<button
						type="button"
						on:click={() => currentPage < maxPage && currentPage++}
						class="rounded-r-md border border-l-0 border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
					>
						Next
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
