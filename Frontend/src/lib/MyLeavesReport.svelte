<script lang="ts">
	import { onMount } from 'svelte';
	import {
		timelogAPI,
		task_typeAPI,
		type TimelogResponse,
		type TaskTypeResponse,
		type UserResponse
	} from '$lib/api';
	import { computeLeaveSummary, type LeaveSummary } from '$lib/leaveCalculations';
	import Icon from '@iconify/svelte';
	import * as XLSX from 'xlsx';

	export let user: UserResponse;

	let year = new Date().getFullYear().toString();
	let searchYear = year;
	let loading = false;
	let timelogs: TimelogResponse[] = [];
	let taskTypes: TaskTypeResponse[] = [];

	let summary: LeaveSummary[] = [];

	onMount(async () => {
		await loadData();
	});

	async function loadData() {
		loading = true;
		try {
			const [logs, types] = await Promise.all([timelogAPI.listMine(), task_typeAPI.getAllPublic()]);
			timelogs = logs;
			taskTypes = types;
			processData();
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function processData() {
		const targetYear = parseInt(searchYear);
		summary = computeLeaveSummary(user, timelogs, taskTypes, targetYear);
	}

	function handleSearch() {
		searchYear = year;
		processData();
	}

	function formatHours(minutes: number): string {
		return (minutes / 60).toFixed(1);
	}

	function exportCSV() {
		const rows = [['Leave Type', 'Date', 'Description', 'Status', 'Hours Logged']];
		summary.forEach((s) => {
			s.items.forEach((item) => {
				rows.push([
					s.typeName,
					new Date(item.start_time).toLocaleDateString(),
					item.description || '',
					item.status,
					formatHours(item.duration_minutes)
				]);
			});
		});
		const csvContent =
			'data:text/csv;charset=utf-8,' +
			rows.map((e) => e.map((c) => `"${c}"`).join(',')).join('\n');
		const encodedUri = encodeURI(csvContent);
		const link = document.createElement('a');
		link.setAttribute('href', encodedUri);
		link.setAttribute('download', `leaves_report_${searchYear}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}

	function exportExcel() {
		const wb = XLSX.utils.book_new();
		const summaryRows: (string | number)[][] = [
			['Leave Name', 'Earned Days', 'Awarded Days', 'Spent Days', 'Available', 'Total Unused']
		];
		summary.forEach((s) => {
			summaryRows.push([s.typeName, s.earned, s.awarded, s.spent, s.earnedBalance, s.remaining]);
		});
		const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
		XLSX.utils.book_append_sheet(wb, summarySheet, `Summary ${searchYear}`);

		const detailRows: (string | number)[][] = [
			[
				'Leave Type',
				'Date',
				'Description',
				'Status',
				'Hours Logged',
				'Date Filed',
				'Approver',
				'Approved At'
			]
		];
		summary.forEach((s) => {
			s.items.forEach((item) => {
				detailRows.push([
					s.typeName,
					new Date(item.start_time).toLocaleDateString(),
					item.description || '',
					item.status,
					formatHours(item.duration_minutes),
					new Date(item.created_at).toLocaleDateString(),
					item.approver_name || '-',
					item.approved_at ? new Date(item.approved_at).toLocaleDateString() : '-'
				]);
			});
		});
		const detailSheet = XLSX.utils.aoa_to_sheet(detailRows);
		XLSX.utils.book_append_sheet(wb, detailSheet, `Filed Leaves ${searchYear}`);

		XLSX.writeFile(wb, `leaves_report_${searchYear}.xlsx`);
	}

	function formatDate(d: string | undefined) {
		if (!d) return 'N/A';
		return new Date(d).toLocaleDateString();
	}

	function toggleSection(index: number) {
		summary[index].isOpen = !summary[index].isOpen;
		summary = summary;
	}
</script>

<div class="space-y-6 p-4">
	<div class="rounded-lg bg-white p-6 shadow-sm">
		<h2 class="mb-4 text-xl font-semibold text-gray-800">
			Leave Individual Report ({user.last_name}, {user.first_name})
		</h2>
		<div class="flex items-end gap-4">
			<div>
				<label for="report-year" class="mb-1 block text-sm font-medium text-red-600">
					* Report Year (format: YYYY)
				</label>
				<input
					id="report-year"
					type="text"
					bind:value={year}
					class="w-48 rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
				/>
			</div>
			<button
				on:click={handleSearch}
				class="rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
			>
				Search Now
			</button>
		</div>
	</div>

	<div class="rounded-lg bg-white p-6 shadow-sm">
		<h3 class="mb-4 text-lg font-semibold text-gray-800">
			{user.last_name}, {user.first_name}
		</h3>
		<div class="space-y-2 text-sm text-gray-600">
			<div>
				<span class="font-medium">Employment Start:</span>
				{formatDate(user.emp_start_date)}
			</div>
			<div>
				<span class="font-medium">Contract End:</span>
				{formatDate(user.emp_end_date)}
			</div>
			<div>
				<span class="font-medium">Status:</span>
				{user.status || 'Active'}
			</div>
		</div>
	</div>

	<div>
		<button
			on:click={exportCSV}
			class="inline-flex items-center gap-2 rounded-md bg-teal-500 px-4 py-2 font-medium text-white hover:bg-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2"
		>
			<Icon icon="mdi:file-export" />
			Export Summary to CSV
		</button>
		<button
			on:click={exportExcel}
			class="ml-2 inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
		>
			<Icon icon="mdi:file-excel" />
			Export to Excel
		</button>
	</div>

	<div class="overflow-hidden rounded-lg bg-white shadow-sm">
		<div class="bg-gray-50 px-6 py-4">
			<h3 class="font-semibold text-gray-700">Summary for {searchYear}</h3>
		</div>
		<div class="overflow-x-auto">
			<table class="w-full min-w-[1000px] text-left text-sm">
				<thead class="bg-gray-50 text-gray-500">
					<tr>
						<th class="px-6 py-3 font-medium">Leave Name</th>
						<th class="px-6 py-3 font-medium">Earned Days</th>
						<th class="px-6 py-3 font-medium">Awarded Days</th>
						<th class="px-6 py-3 font-medium">Spent Days</th>
						<th class="px-6 py-3 font-medium">Available</th>
						<th class="px-6 py-3 font-medium">Total Unused</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					{#each summary as s}
						<tr class="hover:bg-gray-50">
							<td class="px-6 py-4 font-medium text-gray-900">{s.typeName}</td>
							<td class="px-6 py-4">{s.earned}</td>
							<td class="px-6 py-4">{s.awarded}</td>
							<td class="px-6 py-4 text-blue-600">{s.spent}</td>
							<td class="px-6 py-4">{s.earnedBalance}</td>
							<td class="px-6 py-4">{s.remaining}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>

	<div class="rounded-lg bg-white shadow-sm">
		<div class="bg-gray-50 px-6 py-4">
			<h3 class="font-semibold text-gray-700">Filed Leaves for {searchYear}</h3>
		</div>
		<div class="divide-y divide-gray-200">
			{#each summary as s, i}
				<div class="p-4">
					<button
						class="flex w-full items-center justify-between text-left focus:outline-none"
						on:click={() => toggleSection(i)}
					>
						<div class="flex items-center gap-2 font-medium text-gray-800">
							<Icon icon={s.isOpen ? 'mdi:chevron-up' : 'mdi:chevron-down'} />
							{s.typeName}
						</div>
						{#if s.spent > 0}
							<div class="text-sm text-gray-500">{s.spent} day{s.spent === 1 ? '' : 's'}</div>
						{/if}
					</button>

					{#if s.isOpen}
						<div class="mt-4 overflow-x-auto">
							<table class="w-full text-left text-sm">
								<thead class="bg-gray-50 text-gray-500">
									<tr>
										<th class="px-4 py-2 font-medium">Date of Leave</th>
										<th class="px-4 py-2 font-medium">Hours Logged</th>
										<th class="px-4 py-2 font-medium">Description</th>
										<th class="px-4 py-2 font-medium">Date Filed</th>
										<th class="px-4 py-2 font-medium">Status</th>
										<th class="px-4 py-2 font-medium">Approver</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-gray-100">
									{#if s.items.length === 0}
										<tr>
											<td colspan="6" class="px-4 py-3 text-center text-gray-500">No filed leaves</td>
										</tr>
									{:else}
										{#each s.items as item}
											<tr class="hover:bg-gray-50">
												<td class="px-4 py-3">
													<div class="font-medium">
														{new Date(item.start_time).toLocaleDateString(undefined, {
															month: 'short',
															day: 'numeric',
															year: 'numeric'
														})}
													</div>
													<div class="text-xs text-gray-500">
														{new Date(item.start_time).toLocaleDateString(undefined, {
															weekday: 'long'
														})}
													</div>
												</td>
												<td class="px-4 py-3">{formatHours(item.duration_minutes)} hrs</td>
												<td class="px-4 py-3">{item.description || '-'}</td>
												<td class="px-4 py-3">{new Date(item.created_at).toLocaleDateString()}</td>
												<td class="px-4 py-3">
													<span
														class:text-green-600={item.status === 'Approved'}
														class:text-yellow-600={item.status === 'Pending'}
														class:text-red-600={item.status === 'Rejected'}
													>
														{item.status}
													</span>
													{#if item.approved_at}
														<div class="text-xs text-gray-500">
															on {new Date(item.approved_at).toLocaleDateString()}
														</div>
													{/if}
												</td>
												<td class="px-4 py-3">{item.approver_name || '-'}</td>
											</tr>
										{/each}
									{/if}
								</tbody>
							</table>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>