<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { isAuthenticated } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { timelogAPI, type WeeklySummaryItem } from '$lib/api';
	import api, { user201API } from '$lib/api';
	import { addNotification, notifications } from '$lib/notifications';
	import { isAdmin } from '$lib/stores';
	import Icon from '@iconify/svelte';

	let authed = false;
	let summary: WeeklySummaryItem[] = [];
	let weeks = 52;
	let showWeeks: 'show' | 'hide' = 'show';
	let refreshTimer: ReturnType<typeof setInterval> | null = null;
	let lastCheckedTime = 0;
	let pendingApprovalsCount = 0;
	let currentUser: any = null;

	const unsub1 = isAuthenticated.subscribe((v) => (authed = v));

	let refreshing = false;
	async function refreshSummary() {
		if (refreshing) return;
		refreshing = true;
		try {
			const data = await timelogAPI.weeklySummary(weeks).catch(() => summary);
			const base = (data || []).slice();
			const now = new Date();
			const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
			function parseYMD(s: string): Date {
				const [y, m, d] = s.split('-').map((x) => parseInt(x, 10));
				return new Date(y, (m || 1) - 1, d || 1);
			}
			const contractStart = currentUser?.emp_start_date
				? parseYMD(currentUser.emp_start_date)
				: today;
			const contractEnd = currentUser?.emp_end_date ? parseYMD(currentUser.emp_end_date) : today;
			const startRef = contractStart.getTime() > today.getTime() ? contractStart : today;
			const startSunday = new Date(
				startRef.getFullYear(),
				startRef.getMonth(),
				startRef.getDate() - startRef.getDay()
			);
			const endSunday = new Date(
				contractEnd.getFullYear(),
				contractEnd.getMonth(),
				contractEnd.getDate() - contractEnd.getDay()
			);
			const weeksList: WeeklySummaryItem[] = [];
			let cur = new Date(startSunday.getFullYear(), startSunday.getMonth(), startSunday.getDate());
			while (cur.getTime() <= endSunday.getTime()) {
				const endSat = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 6);
				const ws = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, '0')}-${String(
					cur.getDate()
				).padStart(2, '0')}`;
				const we = `${endSat.getFullYear()}-${String(endSat.getMonth() + 1).padStart(2, '0')}-${String(
					endSat.getDate()
				).padStart(2, '0')}`;
				weeksList.push({
					week_start: ws,
					week_end: we,
					total_logged_hours: 0,
					deficient_hours: 0,
					approved_hours: 0,
					for_approval_hours: 0,
					rejected_hours: 0
				});
				cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 7);
			}
			const byStart = new Map<string, WeeklySummaryItem>();
			for (const i of base) byStart.set(i.week_start, i);
			for (const w of weeksList) if (!byStart.has(w.week_start)) byStart.set(w.week_start, w);
			const allWeeks = Array.from(byStart.values());
			const currentYear = now.getFullYear();
			const yearStart = new Date(currentYear, 0, 1);
			const currentWeekSunday = new Date(
				today.getFullYear(),
				today.getMonth(),
				today.getDate() - today.getDay()
			);
			const cwY = currentWeekSunday.getFullYear();
			const cwM = String(currentWeekSunday.getMonth() + 1).padStart(2, '0');
			const cwD = String(currentWeekSunday.getDate()).padStart(2, '0');
			const currentWeekStartStr = `${cwY}-${cwM}-${cwD}`;

			summary = allWeeks
				.filter((w) => {
					if (w.week_start === currentWeekStartStr) return true;
					if (w.week_start > currentWeekStartStr) return false;

					const wEndDate = parseYMD(w.week_end);
					const wStartDate = parseYMD(w.week_start);

					// Filter out weeks strictly before contract start
					if (wEndDate.getTime() < contractStart.getTime()) return false;

					// Filter out weeks strictly after contract end
					if (contractEnd && wStartDate.getTime() > contractEnd.getTime()) return false;

					// Never show a week whose end falls before the current year —
					// keeps the oldest visible row inside the current year
					if (wEndDate.getTime() < yearStart.getTime()) return false;

					if (w.deficient_hours !== 0) return true;
					return false;
				})
				.sort((a, b) => {
					if (a.week_start === currentWeekStartStr) return -1;
					if (b.week_start === currentWeekStartStr) return 1;
					return new Date(b.week_start).getTime() - new Date(a.week_start).getTime();
				})
				// Hard cap at 52 rows regardless of how many deficient weeks exist this year
				.slice(0, 52);
		} finally {
			refreshing = false;
		}
	}

	async function fetchBackendNotifications() {
		try {
			const result = await api.notificationAPI.getNotifications();
			if (result.notifications && Array.isArray(result.notifications)) {
				for (const notif of result.notifications) {
					// Check if notification already exists in store
					if (!$notifications.find((n) => n.id === String(notif.id))) {
						const routeFor201 = admin ? '/201-files?status=Pending' : '/profile?tab=employment';
						addNotification({
							id: String(notif.id),
							title: notif.action === 'approved' ? 'Timelog Approved' : 'Timelog Rejected',
							message: `${notif.approver_name} ${notif.action} your ${notif.item_type} entry`,
							type: notif.item_type === 'user201' ? 'user201' : 'timelog',
							approver_id: notif.approver_id,
							approver_name: notif.approver_name,
							approver_avatar: notif.approver_avatar,
							action: notif.action as any,
							target_route: notif.item_type === 'user201' ? routeFor201 : notif.target_route,
							target_item_id: notif.item_id,
							read: notif.is_read === 1
						});
					}
				}
			}
		} catch (e) {
			console.error('Failed to fetch backend notifications:', e);
		}
	}

	async function checkForStatusUpdates() {
		try {
			const result = await api.notificationAPI.getStatusUpdates();
			if (result.updates && result.updates.length > 0) {
				// Show only recent updates (since last check)
				const now = Date.now();
				const recentUpdates = result.updates.filter((u) => {
					const updateTime = new Date(u.approved_at || 0).getTime();
					return updateTime > lastCheckedTime;
				});

				for (const update of recentUpdates) {
					addNotification({
						title: update.status === 'Approved' ? 'Timelog Approved' : 'Timelog Rejected',
						message: update.description || `${update.type} entry · ${update.status}`,
						type: update.type === 'leave' ? 'leave' : 'timelog',
						approver_id: update.approver_id,
						approver_name: update.approver_name,
						approver_avatar: update.approver_avatar,
						action: update.action,
						target_route: update.target_route,
						target_item_id: update.timelog_id
					});
				}
				lastCheckedTime = now;
			}
		} catch (e) {
			console.error('Failed to check for status updates:', e);
		}
	}

	let lastPendingApprovalsNotification = 0;
	let lastPending201Notification = 0;
	let lastUser201Reminder = 0;
	let admin = false;
	const unsubAdmin = isAdmin.subscribe((v) => (admin = v));

	async function checkPendingApprovals() {
		try {
			// Check if user is a manager/has pending approvals
			const managed = await api.timelogAPI.listManaged('Pending').catch(() => []);
			pendingApprovalsCount = managed.length;

			// Show pending approvals popup every 24 hours
			const now = Date.now();
			const TWENTY_FOUR_HOURS = 24 * 60 * 60 * 1000;

			if (managed.length > 0 && now - lastPendingApprovalsNotification > TWENTY_FOUR_HOURS) {
				// Only add if one doesn't already exist in the list
				if (!$notifications.some((n) => n.id === 'pending-approvals-reminder')) {
					addNotification({
						id: 'pending-approvals-reminder',
						title: 'Pending Approvals',
						message: `You have ${managed.length} timelog(s) pending approval`,
						type: 'generic',
						action: 'created',
						target_route: '/approval',
						read: false
					});
				}
				lastPendingApprovalsNotification = now;
			}
		} catch (e) {
			// User is not a manager, ignore
		}
	}

	async function checkPending201Approvals() {
		try {
			if (!admin) return;
			const all = await user201API.listAll().catch(() => []);
			const pending = all.filter((f) => f.status === 'Pending');
			const now = Date.now();
			const DAY = 24 * 60 * 60 * 1000;
			if (pending.length > 0 && now - lastPending201Notification > DAY) {
				if (!$notifications.some((n) => n.id === 'pending-201-reminder')) {
					addNotification({
						id: 'pending-201-reminder',
						title: '201 Files Pending Approval',
						message: `You have ${pending.length} 201 file(s) pending approval`,
						type: 'user201',
						action: 'created',
						target_route: '/201-files?status=Pending',
						read: false
					});
				}
				lastPending201Notification = now;
			}
		} catch (e) {}
	}

	async function checkUser201UploadReminder() {
		try {
			if (admin) return;
			const mine = await user201API.listMineActive().catch(() => []);
			const now = Date.now();
			const DAY = 24 * 60 * 60 * 1000;
			if ((!mine || mine.length === 0) && now - lastUser201Reminder > DAY) {
				if (!$notifications.some((n) => n.id === 'user201-upload-reminder')) {
					addNotification({
						id: 'user201-upload-reminder',
						title: 'Complete Your 201 Files',
						message: 'Go to Employment Details to upload your 201 files',
						type: 'user201',
						action: 'created',
						target_route: '/profile?tab=employment',
						read: false
					});
				}
				lastUser201Reminder = now;
			}
		} catch (e) {}
	}
	onMount(async () => {
		if (!authed) {
			goto(resolve('/login'));
			return;
		}
		try {
			currentUser = await api.userAPI.getMe();
		} catch (e) {
			currentUser = null;
		}
		lastCheckedTime = Date.now();
		await refreshSummary();
		// Notifications handled globally in layout
		await checkPendingApprovals();
		await checkPending201Approvals();
		await checkUser201UploadReminder();
		refreshTimer = setInterval(() => {
			refreshSummary();
			checkPendingApprovals();
			checkPending201Approvals();
			checkUser201UploadReminder();
		}, 30000);
		window.addEventListener('focus', () => {
			refreshSummary();
			checkPendingApprovals();
			checkPending201Approvals();
			checkUser201UploadReminder();
		});
		document.addEventListener('visibilitychange', () => {
			if (document.visibilityState === 'visible') {
				refreshSummary();
			}
		});
	});

	onDestroy(() => {
		unsub1();
		if (refreshTimer) clearInterval(refreshTimer);
		window.removeEventListener('focus', () => {});
	});

	function totals() {
		return {
			total_logged_hours: summary.reduce((a, b) => a + (b.total_logged_hours || 0), 0),
			deficient_hours: summary.reduce((a, b) => a + (b.deficient_hours || 0), 0),
			approved_hours: summary.reduce((a, b) => a + (b.approved_hours || 0), 0),
			for_approval_hours: summary.reduce((a, b) => a + (b.for_approval_hours || 0), 0),
			rejected_hours: summary.reduce((a, b) => a + (b.rejected_hours || 0), 0)
		};
	}

	function formatWeek(startStr: string, endStr: string): string {
		let s = new Date(startStr);
		let e = new Date(endStr);

		// Clamp dates to contract range
		if (currentUser?.emp_start_date) {
			const cs = new Date(currentUser.emp_start_date);
			// Reset time to midnight for accurate comparison
			const csDate = new Date(cs.getFullYear(), cs.getMonth(), cs.getDate());
			if (s < csDate) s = csDate;
		}
		if (currentUser?.emp_end_date) {
			const ce = new Date(currentUser.emp_end_date);
			const ceDate = new Date(ce.getFullYear(), ce.getMonth(), ce.getDate());
			if (e > ceDate) e = ceDate;
		}

		// If clamping made start > end, just return the original (or handle as empty?)
		// This shouldn't happen if filtered correctly, but as a fallback:
		if (s > e) {
			s = new Date(startStr);
			e = new Date(endStr);
		}

		const sm = s.toLocaleString('en-US', { month: 'short' });
		const em = e.toLocaleString('en-US', { month: 'short' });
		const sd = s.getDate();
		const ed = e.getDate();
		const yr = e.getFullYear();
		const syr = s.getFullYear();

		if (syr !== yr) {
			return `${sm} ${sd}, ${syr} - ${em} ${ed}, ${yr}`;
		}
		return sm === em ? `${sm} ${sd} - ${ed}, ${yr}` : `${sm} ${sd} - ${em} ${ed}, ${yr}`;
	}

	function ymdForCalendar(weekStartStr: string): string {
		const s = new Date(weekStartStr);
		const dow = s.getDay();
		const mondayOffset = dow === 0 ? 1 : 1 - dow;
		const monday = new Date(s.getFullYear(), s.getMonth(), s.getDate() + mondayOffset);
		const y = monday.getFullYear();
		const m = String(monday.getMonth() + 1).padStart(2, '0');
		const d = String(monday.getDate()).padStart(2, '0');
		return `${y}-${m}-${d}`;
	}
</script>

<div class="container mx-auto px-6 py-8">
	<h1 class="mb-6 text-3xl font-semibold dark:text-white">Dashboard</h1>

	<div class="rounded bg-white p-4 shadow dark:bg-gray-800">
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-xl font-semibold dark:text-white">My Timelogs</h2>
			<div class="mt-2 flex items-center gap-2">
				<button
					class="flex items-center gap-1 rounded border bg-white px-2 py-1 text-sm hover:bg-gray-100 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
					on:click={() => {
						showWeeks = showWeeks === 'show' ? 'hide' : 'show';
					}}
					aria-label="Toggle weeks"
					title="Toggle weeks"
				>
					<Icon
						icon={showWeeks === 'show' ? 'mdi:chevron-down' : 'mdi:chevron-right'}
						class="h-4 w-4"
					/>
				</button>
			</div>
		</div>
		{#if showWeeks === 'show'}
			<div class="overflow-x-auto">
				<table class="min-w-full text-sm">
					<thead>
						<tr class="text-left">
							<th class="p-2">Week</th>
							<th class="p-2">Total Logged hours</th>
							<th class="p-2">Deficient hours</th>
							<th class="p-2 text-blue-600">For Approval</th>
							<th class="p-2 text-red-600">Rejected hours</th>
							<th class="p-2 text-green-600">Approved hours</th>
						</tr>
					</thead>
					<tbody>
						{#each summary as row (row.week_start)}
							<tr class="border-t">
								<td class="p-2"
									><a
										class="text-blue-600 hover:underline"
										href={resolve('/tasks') + `?weekStart=${ymdForCalendar(row.week_start)}`}
										>{formatWeek(row.week_start, row.week_end)}</a
									></td
								>
								<td class="p-2">{row.total_logged_hours.toFixed(2)}</td>
								<td class="p-2" class:text-green-600={row.deficient_hours === 0}
									>{row.deficient_hours.toFixed(2)}</td
								>
								<td class="p-2">{row.for_approval_hours.toFixed(2)}</td>
								<td class="p-2">{row.rejected_hours.toFixed(2)}</td>
								<td class="p-2">{row.approved_hours.toFixed(2)}</td>
							</tr>
						{/each}
						<tr class="totals-row border-t bg-gray-100 dark:bg-gray-900">
							<td class="p-2 font-semibold text-gray-900 dark:text-white">Total:</td>
							<td class="p-2 font-semibold text-gray-900 dark:text-white"
								>{totals().total_logged_hours.toFixed(2)}</td
							>
							<td
								class="p-2 font-semibold text-gray-900 dark:text-white"
								class:text-green-600={totals().deficient_hours === 0}
								>{totals().deficient_hours.toFixed(2)}</td
							>
							<td class="p-2 font-semibold text-gray-900 dark:text-white"
								>{totals().for_approval_hours.toFixed(2)}</td
							>
							<td class="p-2 font-semibold text-gray-900 dark:text-white"
								>{totals().rejected_hours.toFixed(2)}</td
							>
							<td class="p-2 font-semibold text-gray-900 dark:text-white"
								>{totals().approved_hours.toFixed(2)}</td
							>
						</tr>
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
