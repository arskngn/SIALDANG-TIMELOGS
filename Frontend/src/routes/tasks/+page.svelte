<script lang="ts">
	import { onMount } from 'svelte';
	import {
		timelogAPI,
		type TimelogCreate,
		type TaskTypeResponse,
		type TimelogResponse,
		type ProjectResponse,
		type UserResponse,
		type BranchResponse,
		type LeaveCreditResponse
	} from '$lib/api';
	import api from '$lib/api';
	import { isAuthenticated, userId, username as usernameStore, isAdmin } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { resolve } from '$app/paths';
	import IconCheck from '~icons/heroicons-solid/check';
	import IconXMark from '~icons/heroicons-solid/x-mark';
	import ConfirmModal from '$lib/ConfirmModal.svelte';
	import ErrorModal from '$lib/ErrorModal.svelte';

	let authed = false;
	let currentUserId: number | null = null;
	let currentUsername = '';
	let currentUserFirstName = '';
	let currentUserLastName = '';
	let admin = false;
	let isProjectManager = false;
	let canManageTasks = false;
	let leaveCredits: LeaveCreditResponse | null = null;
	let leaveCreditsError: string | null = null;
	let deleteLogOpen = false;
	let deleteLogMessage: string = '';
	let contractStartDate: Date | null = null;
	let contractEndDate: Date | null = null;
	let contractRangeKey = '';
	let dateValidationError: string | null = null;
	let showDateValidationError = false;
	$: deleteLogMessage = selectedLog
		? `Are you sure you want to delete this timelog${selectedLog?.description ? `: '${selectedLog.description}'` : ''}?`
		: '';
	const unsub = isAuthenticated.subscribe((v) => (authed = v));
	const unsubUid = userId.subscribe((v) => (currentUserId = v));
	const unsubUser = usernameStore.subscribe((v) => (currentUsername = v));
	const unsubIsAdmin = isAdmin.subscribe((v) => (admin = v));

	// React to URL changes (e.g. clicking Task Calendar in sidebar)
	$: {
		if ($page.url) {
			const ws = $page.url.searchParams.get('weekStart');
			computeWeekFrom(ws || undefined);
		}
	}

	onMount(async () => {
		if (!authed) {
			goto(resolve('/login'));
			return;
		}
		const [tt, pj, br, allUsers, managedProjects] = await Promise.all([
			api.task_typeAPI.getAllPublic().catch(() => []),
			api.userAPI.getMyProjects().catch(() => []),
			api.branchAPI.getAllBranchesPublic().catch(() => []),
			api.userAPI.getAllUsers().catch(() => []),
			api.projectAPI.getMyManaged().catch(() => [])
		]);
		taskTypes = tt as TaskTypeResponse[];
		allProjects = pj as ProjectResponse[];
		// Filter projects to only show "Ongoing" ones for task creation
		projects = allProjects.filter((p) => p.status === 'Ongoing');
		users = allUsers as UserResponse[];
		isProjectManager = Array.isArray(managedProjects) && managedProjects.length > 0;
		canManageTasks = admin || isProjectManager;
		try {
			const me = await api.userAPI.getMe();
			if (me) {
				currentUserFirstName = me.first_name || '';
				currentUserLastName = me.last_name || '';
			}
			if (me?.emp_start_date) {
				const [ys, ms, ds] = String(me.emp_start_date)
					.split('-')
					.map((x) => parseInt(x, 10));
				contractStartDate = new Date(ys, (ms || 1) - 1, ds || 1);
			}
			if (me?.emp_end_date) {
				const [ye, meo, de] = String(me.emp_end_date)
					.split('-')
					.map((x) => parseInt(x, 10));
				contractEndDate = new Date(ye, (meo || 1) - 1, de || 1);
			}
			try {
				leaveCredits = await api.leaveCreditsAPI.getMyCredits();
			} catch (e) {
				leaveCreditsError = e instanceof Error ? e.message : 'Failed to load leave credits';
			}
		} catch (e) {}
		if ((!projects || projects.length === 0) && currentUserId !== null) {
			const alt = await api.userAPI.getUserProjects(currentUserId as number).catch(() => []);
			allProjects = (alt as ProjectResponse[]) || [];
			// Also filter alternate projects
			projects = allProjects.filter((p) => p.status === 'Ongoing');
		}
		branches = br as BranchResponse[];
		// Fetch tasks based on role: admin sees all, PM sees managed, regular user sees own
		if (admin) {
			myLogs = await timelogAPI.listAll().catch((e) => {
				console.error('[Tasks] Error loading admin tasks:', e);
				return [];
			});
		} else if (isProjectManager) {
			myLogs = await timelogAPI.listManaged('All').catch((e) => {
				console.error('[Tasks] Error loading managed tasks:', e);
				return [];
			});
		} else {
			myLogs = await timelogAPI.listMine().catch((e) => {
				console.error('[Tasks] Error loading own tasks:', e);
				return [];
			});
		}
		try {
			// URL params handled by reactive statement
		} catch (e) {}

		// CRITICAL: For calendar view, ONLY display current user's tasks
		// This is a security measure to ensure users only see their own calendar
		if (currentUserId !== null) {
			myLogs = myLogs.filter((log) => log.user_id === currentUserId);
			console.log(
				`[Tasks] Filtered logs to current user (${currentUserId}): ${myLogs.length} tasks`
			);
		}

		// load any previously saved colors from localStorage then ensure missing mappings
		if (typeof localStorage !== 'undefined') {
			loadEntityColorsFromStorage();
			// Load view mode preference
			const savedViewMode = localStorage.getItem('calendarViewMode');
			if (
				savedViewMode === 'work-hours' ||
				savedViewMode === '12-hours' ||
				savedViewMode === '24-hours'
			) {
				viewMode = savedViewMode;
			}
		}
		ensureEntityColors();
		// Force hours array to update after logs are loaded to ensure logs display in default view
		if (viewMode === '24-hours') {
			hours = allHours;
		} else if (viewMode === '12-hours') {
			hours = allHours.filter((h) => h >= 8 && h < 20);
		} else {
			hours = allHours.filter((h) => h >= 8 && h < 18);
		}
		unsub();
		unsubUid();
		unsubUser();
	});

	// Calendar grid configuration
	const startHour = 0; // 12:00 AM (00:00)
	const endHour = 24; // 11:59 PM (end of day)
	const slotMinutes = 15;
	const slotsPerHour = 60 / slotMinutes;
	const slotPixelHeight = 12;
	const allHours = Array.from({ length: endHour - startHour }, (_, i) => startHour + i);

	const sundayFirstOrder = [0, 1, 2, 3, 4, 5, 6];
	const dayLabelsBySundayFirst = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

	function dayLabelForOffset(dayOffset: number): string {
		return dayLabelsBySundayFirst[dayOffset];
	}

	function dateForOffset(dayOffset: number): Date {
		const sunday =
			weekDates && weekDates.length
				? weekDates[0]
				: (() => {
						const n = new Date();
						const today = new Date(n.getFullYear(), n.getMonth(), n.getDate());
						const sundayOffset = -today.getDay();
						return new Date(today.getFullYear(), today.getMonth(), today.getDate() + sundayOffset);
					})();
		return new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + dayOffset);
	}

	// View mode: 'work-hours' (8-6), '12-hours' (8am-8pm), or '24-hours' (12am-11:59pm)
	let viewMode: 'work-hours' | '12-hours' | '24-hours' = 'work-hours';

	// Initialize hours array with default work hours
	let hours: number[] = allHours.filter((h) => h >= 8 && h < 18);

	// Computed hours array based on view mode - reactive to viewMode and myLogs
	$: {
		const logCount = myLogs.length;
		if (viewMode === '24-hours') {
			// 12:00 AM to 11:59 PM (full 24 hours)
			hours = allHours;
		} else if (viewMode === '12-hours') {
			// 8 AM to 8 PM (12 hours)
			hours = allHours.filter((h) => h >= 8 && h < 20);
		} else {
			// Work hours: 8 AM to 6 PM
			hours = allHours.filter((h) => h >= 8 && h < 18);
		}
	}

	let weekDates: Date[] = [];
	let weekRangeLabel = '';

	// Track current hour for highlighting in calendar
	let currentHour: number = new Date().getHours();
	let currentUpdateInterval: NodeJS.Timeout | null = null;

	// Update current hour every second to keep highlighting accurate and smooth
	$: if (typeof window !== 'undefined') {
		if (currentUpdateInterval) clearInterval(currentUpdateInterval);
		currentUpdateInterval = setInterval(() => {
			const newHour = new Date().getHours();
			if (newHour !== currentHour) {
				currentHour = newHour;
			}
		}, 1000); // Update every second for smooth transitions
	}

	// Check if today is in the visible week
	function isTodayInWeek(): boolean {
		if (!weekDates || weekDates.length === 0) return false;
		const today = new Date();
		const todayNormalized = new Date(today.getFullYear(), today.getMonth(), today.getDate());

		for (let i = 0; i < 7; i++) {
			const dayDate = dateForOffset(i);
			const dayDateNormalized = new Date(
				dayDate.getFullYear(),
				dayDate.getMonth(),
				dayDate.getDate()
			);
			if (todayNormalized.getTime() === dayDateNormalized.getTime()) {
				return true;
			}
		}
		return false;
	}

	// Check if given hour is the current hour (today only)
	function isCurrentHour(hour: number, dayOffset: number): boolean {
		const today = new Date();
		const todayNormalized = new Date(today.getFullYear(), today.getMonth(), today.getDate());

		// Only highlight if viewing today
		if (!weekDates || weekDates.length === 0) return false;
		const hourDate = dateForOffset(dayOffset);
		const hourDateNormalized = new Date(
			hourDate.getFullYear(),
			hourDate.getMonth(),
			hourDate.getDate()
		);

		if (todayNormalized.getTime() !== hourDateNormalized.getTime()) return false;

		// Check if current time is within this hour (e.g., 9:00-9:59 for hour 9)
		return currentHour === hour;
	}

	// Check if hour label should be highlighted (for left sidebar)
	function isCurrentHourLabel(hour: number): boolean {
		if (!isTodayInWeek()) return false;
		return currentHour === hour;
	}

	// Reactive variable to track if we're at the latest week (depends on weekDates)
	$: isAtLatestWeek = (() => {
		if (!weekDates || weekDates.length === 0) return false;
		const cur = currentWeekSunday();
		const w = weekDates[0];
		const viewedWeekSunday = new Date(w.getFullYear(), w.getMonth(), w.getDate(), 0, 0, 0, 0);
		const currentWeekSundayDate = new Date(
			cur.getFullYear(),
			cur.getMonth(),
			cur.getDate(),
			0,
			0,
			0,
			0
		);
		const nextWeekSunday = new Date(viewedWeekSunday);
		nextWeekSunday.setDate(viewedWeekSunday.getDate() + 7);
		const nextWeekSundayNormalized = new Date(
			nextWeekSunday.getFullYear(),
			nextWeekSunday.getMonth(),
			nextWeekSunday.getDate(),
			0,
			0,
			0,
			0
		);

		// Only block navigation if next week starts after contract end date
		if (contractEndDate) {
			return nextWeekSundayNormalized.getTime() > contractEndDate.getTime();
		}

		// If no contract end date, allow unlimited navigation forward
		return false;
	})();

	$: contractRangeKey = `${contractStartDate ? contractStartDate.getTime() : 'null'}-${contractEndDate ? contractEndDate.getTime() : 'null'}`;

	// Calculate the earliest allowed date for navigation
	$: earliestAllowedDate = (() => {
		if (contractStartDate) {
			// If contract exists, allow navigation to the start of the week containing the contract start date
			const cs = new Date(contractStartDate);
			const day = cs.getDay();
			const diff = cs.getDate() - day;
			return new Date(cs.getFullYear(), cs.getMonth(), diff);
		}
		// Default to Jan 1 of current year
		return new Date(new Date().getFullYear(), 0, 1);
	})();

	$: isAtEarliestYear = (() => {
		if (!weekDates || weekDates.length === 0) return false;
		const w = weekDates[0];
		const viewedWeekSunday = new Date(w.getFullYear(), w.getMonth(), w.getDate(), 0, 0, 0, 0);
		const prevWeekSunday = new Date(viewedWeekSunday);
		prevWeekSunday.setDate(viewedWeekSunday.getDate() - 7);

		const prevNorm = new Date(
			prevWeekSunday.getFullYear(),
			prevWeekSunday.getMonth(),
			prevWeekSunday.getDate(),
			0,
			0,
			0,
			0
		);
		// Check against earliestAllowedDate instead of hardcoded Jan 1
		return prevNorm.getTime() < earliestAllowedDate.getTime();
	})();

	function computeWeekFrom(isoOrNull?: string) {
		let base: Date;
		if (isoOrNull) {
			base = parseISOasLocal(isoOrNull);
		} else {
			const n = new Date();
			base = new Date(n.getFullYear(), n.getMonth(), n.getDate());
		}
		// Calculate Sunday as the start of the week (getDay() returns 0 for Sunday)
		const sundayOffset = -base.getDay();
		const weekStart = new Date(base.getFullYear(), base.getMonth(), base.getDate() + sundayOffset);
		// Create new array to ensure reactivity
		const newWeekDates = Array.from(
			{ length: 7 },
			(_, i) => new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + i)
		);
		weekDates = newWeekDates;
		const startLabelDate = new Date(
			weekStart.getFullYear(),
			weekStart.getMonth(),
			weekStart.getDate()
		);
		const endLabelDate = new Date(
			weekStart.getFullYear(),
			weekStart.getMonth(),
			weekStart.getDate() + 6
		);
		const startMonth = startLabelDate.toLocaleString('en-US', { month: 'short' });
		const endMonth = endLabelDate.toLocaleString('en-US', { month: 'short' });
		const startYear = startLabelDate.getFullYear();
		const endYear = endLabelDate.getFullYear();

		if (startYear !== endYear) {
			weekRangeLabel = `${startMonth} ${startLabelDate.getDate()}, ${startYear} - ${endMonth} ${endLabelDate.getDate()}, ${endYear}`;
		} else if (startMonth !== endMonth) {
			weekRangeLabel = `${startMonth} ${startLabelDate.getDate()} - ${endMonth} ${endLabelDate.getDate()}, ${endYear}`;
		} else {
			weekRangeLabel = `${startMonth} ${startLabelDate.getDate()}-${endLabelDate.getDate()}, ${endYear}`;
		}
		// Force reactivity by creating a new array reference
		weekDates = [...weekDates];
		// Force reactivity by creating a new array reference
		weekDates = [...weekDates];
	}

	// initialize to current week by default
	// computeWeekFrom(); -> handled by reactive statement

	function formatDateYMD(d: Date) {
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, '0');
		const dd = String(d.getDate()).padStart(2, '0');
		return `${y}-${m}-${dd}`;
	}

	function currentWeekSunday(): Date {
		const n = new Date();
		const today = new Date(n.getFullYear(), n.getMonth(), n.getDate());
		const sundayOffset = -today.getDay();
		return new Date(today.getFullYear(), today.getMonth(), today.getDate() + sundayOffset);
	}

	function isLatestWeek(): boolean {
		if (!weekDates || weekDates.length === 0) return false;
		const cur = currentWeekSunday();
		const w = weekDates[0];
		const viewedWeekStart = new Date(w.getFullYear(), w.getMonth(), w.getDate(), 0, 0, 0, 0);
		const currentWeekStart = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate(), 0, 0, 0, 0);
		const nextWeekStart = new Date(viewedWeekStart);
		nextWeekStart.setDate(viewedWeekStart.getDate() + 7);
		const nextWeekStartNormalized = new Date(
			nextWeekStart.getFullYear(),
			nextWeekStart.getMonth(),
			nextWeekStart.getDate(),
			0,
			0,
			0,
			0
		);

		if (contractEndDate) {
			return nextWeekStartNormalized.getTime() > contractEndDate.getTime();
		}

		const shouldBlock = nextWeekStartNormalized.getTime() > currentWeekStart.getTime();
		return shouldBlock;
	}

	function shiftWeek(days: number) {
		if (!weekDates || weekDates.length === 0) return;
		const newSunday = new Date(
			weekDates[0].getFullYear(),
			weekDates[0].getMonth(),
			weekDates[0].getDate() + days
		);
		// Use earliestAllowedDate instead of hardcoded Jan 1
		if (newSunday.getTime() < earliestAllowedDate.getTime()) return;

		const dateStr = formatDateYMD(newSunday);
		const q = new URLSearchParams($page.url.searchParams);
		q.set('weekStart', dateStr);
		goto(`?${q.toString()}`, { replaceState: true, keepFocus: true, noScroll: true });
	}

	function goPrevWeek() {
		shiftWeek(-7);
	}

	function goNextWeek() {
		if (isLatestWeek()) return;
		shiftWeek(7);
	}

	function onDatePickerChange(e: Event) {
		const target = e.target as HTMLInputElement;
		if (target.value) {
			const q = new URLSearchParams($page.url.searchParams);
			q.set('weekStart', target.value);
			goto(`?${q.toString()}`, { replaceState: true, keepFocus: true, noScroll: true });
		}
	}

	let datePickerInput: HTMLInputElement | null = null;
	let jumpToButtonElement: HTMLElement | null = null;

	function openDatePicker(event: MouseEvent) {
		// Get the button position to position the date picker
		const button = event.currentTarget as HTMLElement;
		jumpToButtonElement = button;

		// Calculate the maximum selectable date based on contract end date
		const cur = currentWeekSunday();
		const currentWeekSaturday = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 6);
		let maxDate: string;
		if (contractEndDate && contractEndDate.getTime() > currentWeekSaturday.getTime()) {
			maxDate = formatDateYMD(contractEndDate);
		} else {
			maxDate = formatDateYMD(currentWeekSaturday);
		}
		const minDate = formatDateYMD(earliestAllowedDate);

		// Use a hidden input element that's always in the DOM
		if (!datePickerInput) {
			datePickerInput = document.createElement('input');
			datePickerInput.type = 'date';
			datePickerInput.style.position = 'fixed';
			datePickerInput.style.opacity = '0';
			datePickerInput.style.pointerEvents = 'none';
			datePickerInput.style.width = '1px';
			datePickerInput.style.height = '1px';
			datePickerInput.style.left = '0';
			datePickerInput.style.top = '0';
			document.body.appendChild(datePickerInput);

			datePickerInput.onchange = async (e) => {
				const target = e.target as HTMLInputElement;
				if (target.value) {
					// Validate that the selected date is not in a future week
					const selectedDate = parseISOasLocal(target.value);
					const selectedDay = selectedDate.getDay();
					const sundayOffset = -selectedDay;
					const selectedWeekStart = new Date(
						selectedDate.getFullYear(),
						selectedDate.getMonth(),
						selectedDate.getDate() + sundayOffset
					);

					if (selectedWeekStart.getTime() < earliestAllowedDate.getTime()) {
						if (contractStartDate) {
							dateValidationError = `Cannot navigate to dates before the week of your contract start date (${contractStartDate.toLocaleDateString()}).`;
						} else {
							dateValidationError =
								'Cannot navigate to previous years. Please select a date within the current year.';
						}
						showDateValidationError = true;
						if (datePickerInput) {
							datePickerInput.value = formatDateYMD(weekDates[0]);
						}
						return;
					}

					// Check if selected week is after contract end date
					if (contractEndDate && selectedWeekStart.getTime() > contractEndDate.getTime()) {
						dateValidationError = `Cannot navigate beyond your contract end date (${contractEndDate.toLocaleDateString()}).`;
						showDateValidationError = true;
						if (datePickerInput) {
							datePickerInput.value = formatDateYMD(weekDates[0]);
						}
						return;
					}

					const q = new URLSearchParams($page.url.searchParams);
					q.set('weekStart', target.value);
					goto(`?${q.toString()}`, { replaceState: true, keepFocus: true, noScroll: true });
				}
			};
		}

		// Set max date to restrict selection to current week
		if (datePickerInput) {
			datePickerInput.min = minDate;
			datePickerInput.max = maxDate;
		}

		// Position the input near the button
		if (button) {
			const rect = button.getBoundingClientRect();
			datePickerInput.style.left = `${rect.left}px`;
			datePickerInput.style.top = `${rect.bottom + 5}px`;
		}

		// Set the current value and trigger click
		datePickerInput.value = formatDateYMD(weekDates[0]);
		// Use setTimeout to ensure the input is positioned before showing
		setTimeout(() => {
			if (datePickerInput) {
				if (datePickerInput.showPicker) {
					datePickerInput.showPicker();
				} else {
					datePickerInput.click();
				}
			}
		}, 0);
	}

	function isoFor(dayOffset: number, hour: number, slotIndex: number): string {
		// Use the selected week's Sunday as the base
		const sunday =
			weekDates && weekDates.length
				? weekDates[0]
				: (() => {
						const n = new Date();
						const today = new Date(n.getFullYear(), n.getMonth(), n.getDate());
						const sundayOffset = -today.getDay();
						return new Date(today.getFullYear(), today.getMonth(), today.getDate() + sundayOffset);
					})();
		const baseDate = new Date(
			sunday.getFullYear(),
			sunday.getMonth(),
			sunday.getDate() + dayOffset
		);
		const base = new Date(
			baseDate.getFullYear(),
			baseDate.getMonth(),
			baseDate.getDate(),
			hour,
			slotIndex * slotMinutes,
			0,
			0
		);
		return localOffsetISO(base);
	}

	function localOffsetISO(d: Date): string {
		const pad = (n: number) => String(n).padStart(2, '0');
		const y = d.getFullYear();
		const m = pad(d.getMonth() + 1);
		const day = pad(d.getDate());
		const hh = pad(d.getHours());
		const mm = pad(d.getMinutes());
		const ss = pad(d.getSeconds());
		const offMin = -d.getTimezoneOffset();
		const sign = offMin >= 0 ? '+' : '-';
		const abs = Math.abs(offMin);
		const offH = pad(Math.floor(abs / 60));
		const offM = pad(abs % 60);
		return `${y}-${m}-${day}T${hh}:${mm}:${ss}${sign}${offH}:${offM}`;
	}

	// Parse ISO string into a Date object treating naive (no timezone) strings
	// as local datetimes. If the ISO contains a timezone offset or 'Z', use
	// the built-in parser which respects the offset.
	function parseISOasLocal(iso: string): Date {
		if (!iso) return new Date();
		const withoutTz = iso.replace(/[zZ]|[+-]\d{2}:?\d{2}$/, '');
		const dateOnly = withoutTz.match(/^(\d{4})-(\d{2})-(\d{2})$/);
		if (dateOnly) {
			const y = +dateOnly[1];
			const mo = +dateOnly[2];
			const d = +dateOnly[3];
			return new Date(y, mo - 1, d, 0, 0, 0, 0);
		}
		const m = withoutTz.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?/);
		if (!m) return new Date();
		const y = +m[1];
		const mo = +m[2];
		const d = +m[3];
		const h = +m[4];
		const mi = +m[5];
		const s = m[6] ? +m[6] : 0;
		const ms = m[7] ? parseInt((m[7] + '000').slice(0, 3), 10) : 0;
		return new Date(y, mo - 1, d, h, mi, s, ms);
	}

	function formatHourLabel(h: number): string {
		// For 24-hour view, hours >= 24 represent next day (e.g., 25 = 1 AM, 31 = 7 AM)
		const actualHour = h >= 24 ? h - 24 : h;
		const suffix = actualHour < 12 ? 'AM' : 'PM';
		const hour12 = ((actualHour + 11) % 12) + 1;
		return `${hour12}:00 ${suffix}${h >= 24 ? ' (next)' : ''}`;
	}

	function formatHalfHourLabel(h: number): string {
		// For 24-hour view, hours >= 24 represent next day
		const actualHour = h >= 24 ? h - 24 : h;
		const suffix = actualHour < 12 ? 'AM' : 'PM';
		const hour12 = ((actualHour + 11) % 12) + 1;
		return `${hour12}:30 ${suffix}${h >= 24 ? ' (next)' : ''}`;
	}

	function formatTimeRange(start: Date, end: Date): string {
		const pad = (n: number) => String(n).padStart(2, '0');
		const formatTime = (d: Date) => {
			const h = d.getHours();
			const m = pad(d.getMinutes());
			const suffix = h < 12 ? 'AM' : 'PM';
			const hour12 = ((h + 11) % 12) + 1;
			return `${hour12}:${m} ${suffix}`;
		};
		return `${formatTime(start)}-${formatTime(end)}`;
	}
	function formatLeaveCreditValue(value?: number | null): string {
		if (value === null || value === undefined) return '—';
		const rounded = Math.round(value * 2) / 2;
		const formatted = rounded.toFixed(1).replace(/\.0$/, '');
		return formatted;
	}
	function leaveCreditColorClass(value?: number | null): string {
		if (value === null || value === undefined) return '';
		if (value <= 0) return 'text-red-600 dark:text-red-400';
		return 'text-green-600 dark:text-green-400';
	}

	let myLogs: TimelogResponse[] = [];
	let projects: ProjectResponse[] = [];
	let allProjects: ProjectResponse[] = [];
	let branches: BranchResponse[] = [];
	let users: UserResponse[] = [];
	let showEditor = false;
	let isEditMode = false;
	let showDuplicatePanel = false;
	let notesOpen = true;
	let projectsOpen = true;
	let otherTasksOpen = true;
	let leavesOpen = true;
	let editorType: 'project' | 'other' | 'leave' = 'project';
	let editorProjectId: number | undefined = undefined;
	let editorTaskTypeId: number | undefined = undefined;
	let editorDescription = '';
	let editorLocation = '';
	let editorStartISO = '';
	let editorEndISO = '';
	let duplicateStartDate = '';
	let duplicateDaysCount = 1;
	let isEditingDaysCount = false;
	let duplicateDaysMode: 'end-date' | 'days-count' = 'days-count';
	let duplicateEndDate = '';
	let duplicateFrequency: 'daily-weekends' | 'daily-no-weekends' | 'weekly' = 'daily-weekends';
	let duplicateCustomDay = 'Monday';
	let taskTypes: TaskTypeResponse[] = [];
	let selectedLog: TimelogResponse | null = null;
	let warningMessage = '';

	// Drag selection state (moved earlier so TypeScript sees it before usage)
	let dragSelection: {
		day: number;
		startHour: number;
		startSlot: number;
		endHour: number;
		endSlot: number;
	} | null = null;

	let isSelecting = false;
	let selectionStartTime: number | null = null;

	let selectionStartCoord: { day: number; hour: number; slot: number } | null = null;

	// Long press detection
	let longPressTimeout: number | null = null;
	const LONG_PRESS_DELAY = 400;

	// Colors are generated on demand (golden-angle hue rotation) instead of picked from a
	// fixed palette, so the pool never runs out. entityColors caches the generated hex per
	// entity key; colorAssignCounter drives the rotation and persists across reloads.
	const entityColors: Map<string, string> = new Map(); // entity key -> hex color
	let colorAssignCounter = 0;
	const DRAG_PREVIEW_COLOR = '#3b82f6'; // neutral placeholder while dragging, before a project/task is picked

	let dragColorName: string | null = null; // color used during current drag selection
	let editorColorName: string | null = null; // color chosen for the editor / created entry

	function hslToHex(h: number, s: number, l: number): string {
		s /= 100;
		l /= 100;
		const k = (n: number) => (n + h / 30) % 12;
		const a = s * Math.min(l, 1 - l);
		const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
		const toHex = (x: number) =>
			Math.round(255 * x)
				.toString(16)
				.padStart(2, '0');
		return `#${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`;
	}

	function generateColorForIndex(index: number): string {
		const hueStep = 137.508; // golden angle - spreads hues evenly, never clusters
		const hue = (index * hueStep) % 360;
		// After each full pass around the hue wheel, nudge saturation/lightness so
		// later entities stay visually distinct from earlier ones at the same hue.
		const cycle = Math.floor((index * hueStep) / 360);
		const saturation = 55 + ((cycle * 17) % 30); // 55-85%
		const lightness = 42 - ((cycle * 7) % 20); // 22-42%, stays legible under white text
		return hslToHex(hue, saturation, lightness);
	}

	// Colors are assigned per entity (a project, or an "other"/"leave" task type) rather than
	// per individual timelog, so every entry for the same project/task always renders in the
	// same color — both on the calendar grid and in the sidebar. Assignment happens the first
	// time an entity is encountered (or is restored from localStorage) and stays fixed from then on.
	function entityKeyForLog(log: {
		type: string;
		project_id?: number;
		task_type_id?: number;
	}): string {
		return log.type === 'project' ? `project-${log.project_id}` : `task-${log.task_type_id}`;
	}

	function getEntityColor(key: string): string {
		let c = entityColors.get(key);
		if (!c) {
			const usedHexes = new Set(entityColors.values());
			let candidate = generateColorForIndex(colorAssignCounter++);
			// Explicit guarantee: keep advancing until the hex is genuinely unused,
			// rather than trusting the hue math never to repeat.
			while (usedHexes.has(candidate)) {
				candidate = generateColorForIndex(colorAssignCounter++);
			}
			c = candidate;
			entityColors.set(key, c);
			saveEntityColorsToStorage();
		}
		return c;
	}

	// Keep the editor's preview color in sync with whichever project/task type is selected,
	// so the same entity always previews (and saves) with its established color.
	$: if (showEditor) {
		if (editorType === 'project' && editorProjectId) {
			editorColorName = getEntityColor(`project-${editorProjectId}`);
		} else if ((editorType === 'other' || editorType === 'leave') && editorTaskTypeId) {
			editorColorName = getEntityColor(`task-${editorTaskTypeId}`);
		}
	}

	async function createEntry() {
		warningMessage = '';
		if (!editorType) {
			warningMessage = 'Please select Project, Other Task, or Leave';
			return;
		}
		// Require non-empty summary/description for new task creation
		if (!selectedLog && (!editorDescription || editorDescription.trim() === '')) {
			warningMessage = 'Please enter a summary/description of the task';
			return;
		}
		if (editorType === 'project') {
			if (!editorProjectId) {
				warningMessage = 'Please select a project';
				return;
			}
		} else if (editorType === 'other') {
			if (!editorTaskTypeId) {
				warningMessage = 'Please select a task type';
				return;
			}
		} else if (editorType === 'leave') {
			if (!editorTaskTypeId) {
				warningMessage = 'Please select a leave type';
				return;
			}
		}
		if (!editorLocation || editorLocation.trim() === '') {
			warningMessage = 'Please select a branch';
			return;
		}

		if (!editorDescription || editorDescription.trim() === '') {
			warningMessage = 'Please enter a description';
			return;
		}

		if (!editorStartISO || !editorEndISO) {
			warningMessage = 'Please set start and end time';
			return;
		}
		if (contractStartDate || contractEndDate) {
			const s = parseISOasLocal(editorStartISO);
			const e = parseISOasLocal(editorEndISO);
			const sDate = new Date(s.getFullYear(), s.getMonth(), s.getDate());
			const eDate = new Date(e.getFullYear(), e.getMonth(), e.getDate());
			if (
				(contractStartDate && sDate.getTime() < contractStartDate.getTime()) ||
				(contractEndDate && eDate.getTime() > contractEndDate.getTime())
			) {
				warningMessage = 'You can only create timelogs within your contract period.';
				return;
			}
		}

		if (hasOverlapForRange(editorStartISO, editorEndISO, selectedLog?.id)) {
			warningMessage = 'This time range overlaps with an existing timelog.';
			return;
		}
		const payload: TimelogCreate = {
			type: editorType,
			project_id: editorType === 'project' ? editorProjectId : undefined,
			task_type_id: editorType !== 'project' ? editorTaskTypeId : undefined,
			description: editorDescription || undefined,
			location: editorLocation || undefined,
			start_time: editorStartISO,
			end_time: editorEndISO
		};
		// Ensure this entity (project or task type) has a persisted color assignment
		getEntityColor(
			entityKeyForLog(payload as { type: string; project_id?: number; task_type_id?: number })
		);
		try {
			let result;
			if (selectedLog) {
				const logId = selectedLog.id;
				// Update existing log
				result = await timelogAPI.update(logId, { ...payload });
				// Optimistically update the log in the array
				const idx = myLogs.findIndex((l) => l.id === logId);
				if (idx >= 0 && result) {
					myLogs[idx] = result;
					// Trigger Svelte reactivity by reassigning the entire array
					myLogs = [...myLogs];
				}
			} else {
				// Create new log
				result = await timelogAPI.create(payload);
				// Optimistically add to array
				if (result && result.id) {
					myLogs = [...myLogs, result];
				}
			}
			showEditor = false;
			dragSelection = null;
			selectedLog = null;
		} catch (err) {
			console.error('Error saving timelog:', err);
			warningMessage = `Error saving: ${err instanceof Error ? err.message : String(err)}`;
			// Refresh to revert any optimistic updates
			const refreshedLogs = await timelogAPI.listMine();
			myLogs = refreshedLogs; // Force reactivity on refresh
		}
	}

	function promptDeleteSelectedLog() {
		if (!selectedLog) return;
		deleteLogOpen = true;
	}

	async function performDeleteSelectedLog() {
		if (!selectedLog) {
			deleteLogOpen = false;
			return;
		}
		const deletedId = selectedLog.id;
		// Optimistically remove from array
		myLogs = myLogs.filter((l) => l.id !== deletedId);

		try {
			await timelogAPI.remove(deletedId);
		} catch (err) {
			console.error('Error deleting timelog:', err);
			// Refresh to restore if deletion failed
			myLogs = await timelogAPI.listMine();
		}

		showEditor = false;
		dragSelection = null;
		selectedLog = null;
		ensureEntityColors();
		deleteLogOpen = false;
	}

	async function approveTask() {
		if (!selectedLog) return;
		const logId = selectedLog.id;
		try {
			// Update the status to Approved
			const result = await timelogAPI.update(logId, { status: 'Approved' });
			// Optimistically update the log in the array
			const idx = myLogs.findIndex((l) => l.id === logId);
			if (idx >= 0 && result) {
				myLogs[idx] = result;
				myLogs = myLogs;
				selectedLog = result;
			}
			// Record approval notification
			try {
				await api.notificationAPI.recordTimelogApproval(logId, 'Approved');
			} catch (e) {
				console.error(`Failed to record approval notification for timelog ${logId}:`, e);
			}
		} catch (err) {
			console.error('Error approving timelog:', err);
			warningMessage = `Error approving: ${err instanceof Error ? err.message : String(err)}`;
			// Refresh to revert optimistic update
			myLogs = await timelogAPI.listAll().catch(() => []);
		}
	}

	async function rejectTask() {
		if (!selectedLog) return;
		const logId = selectedLog.id;
		try {
			// Update the status to Rejected
			const result = await timelogAPI.update(logId, { status: 'Rejected' });
			// Optimistically update the log in the array
			const idx = myLogs.findIndex((l) => l.id === logId);
			if (idx >= 0 && result) {
				myLogs[idx] = result;
				myLogs = myLogs;
				selectedLog = result;
			}
			// Record rejection notification
			try {
				await api.notificationAPI.recordTimelogApproval(logId, 'Rejected');
			} catch (e) {
				console.error(`Failed to record rejection notification for timelog ${logId}:`, e);
			}
		} catch (err) {
			console.error('Error rejecting timelog:', err);
			warningMessage = `Error rejecting: ${err instanceof Error ? err.message : String(err)}`;
			// Refresh to revert optimistic update
			myLogs = await timelogAPI.listAll().catch(() => []);
		}
	}

	async function duplicateSelectedLog() {
		if (!selectedLog) return;

		try {
			let created: TimelogResponse[] = [];

			if (duplicateDaysMode === 'days-count' && duplicateDaysCount > 0) {
				// Calculate specific dates based on number of days
				// Start from the day after the original log's date
				const originalDate = parseISOasLocal(selectedLog.start_time);
				// Get the date part only (midnight)
				const originalDateOnly = new Date(
					originalDate.getFullYear(),
					originalDate.getMonth(),
					originalDate.getDate()
				);
				// Start from next day
				const nextDay = new Date(originalDateOnly);
				nextDay.setDate(nextDay.getDate() + 1);

				// Calculate the specific dates to duplicate to
				const targetDates: string[] = [];
				for (let i = 0; i < duplicateDaysCount; i++) {
					const targetDate = new Date(nextDay);
					targetDate.setDate(nextDay.getDate() + i);
					// Format as YYYY-MM-DD
					const dateStr = `${targetDate.getFullYear()}-${String(targetDate.getMonth() + 1).padStart(2, '0')}-${String(targetDate.getDate()).padStart(2, '0')}`;
					targetDates.push(dateStr);
				}

				if (contractStartDate || contractEndDate) {
					for (const ds of targetDates) {
						const [y, m, d] = ds.split('-').map((x) => parseInt(x, 10));
						const td = new Date(y, (m || 1) - 1, d || 1);
						if (
							(contractStartDate && td.getTime() < contractStartDate.getTime()) ||
							(contractEndDate && td.getTime() > contractEndDate.getTime())
						) {
							alert('You can only create timelogs within your contract period.');
							return;
						}
					}
				}
				// Use the new duplicateToDates API
				created = await timelogAPI.duplicateToDates(selectedLog.id, targetDates);
			} else if (duplicateStartDate) {
				// Use the old frequency-based approach for backward compatibility
				let endDate = duplicateEndDate;
				if (duplicateDaysMode === 'days-count') {
					const start = new Date(duplicateStartDate);
					const end = new Date(start);
					end.setDate(end.getDate() + duplicateDaysCount - 1);
					endDate = end.toISOString().split('T')[0];
				}

				if (contractStartDate || contractEndDate) {
					const [ys, ms, ds] = String(duplicateStartDate)
						.split('-')
						.map((x) => parseInt(x, 10));
					const sDate = new Date(ys, (ms || 1) - 1, ds || 1);
					const [ye, meo, de] = String(endDate)
						.split('-')
						.map((x) => parseInt(x, 10));
					const eDate = new Date(ye, (meo || 1) - 1, de || 1);
					if (
						(contractStartDate && sDate.getTime() < contractStartDate.getTime()) ||
						(contractEndDate && eDate.getTime() > contractEndDate.getTime())
					) {
						alert('You can only create timelogs within your contract period.');
						return;
					}
				}
				// Map new frequency values to API format
				let apiFrequency: 'daily' | 'weekdays' | 'weekly' = 'daily';
				if (duplicateFrequency === 'daily-no-weekends') apiFrequency = 'weekdays';
				else if (duplicateFrequency === 'weekly') apiFrequency = 'weekly';

				created = await timelogAPI.duplicate(selectedLog.id, {
					start_date: duplicateStartDate,
					end_date: endDate,
					frequency: apiFrequency
				});
			} else {
				alert('Please specify how many days to duplicate or select a start date');
				return;
			}

			showEditor = false;
			showDuplicatePanel = false;
			dragSelection = null;
			selectedLog = null;
			duplicateStartDate = '';
			duplicateEndDate = '';
			duplicateDaysCount = 1;
			duplicateFrequency = 'daily-weekends';

			// Optimistically add created duplicates to the array
			if (created && Array.isArray(created)) {
				myLogs = [...myLogs, ...created];
			}

			// Refresh from backend to ensure consistency
			const freshLogs = await timelogAPI.listMine();
			myLogs = freshLogs;
			ensureEntityColors();
		} catch (e) {
			console.error('Duplicate timelog failed:', e);
			alert('Failed to duplicate timelog');
			// Refresh to revert optimistic updates
			myLogs = await timelogAPI.listMine();
		} finally {
			// Ensure UI state is consistent even if an error occurs
			showDuplicatePanel = false;
		}
	}

	function openEditorForLog(log: TimelogResponse) {
		selectedLog = log;
		editorType = log.type;
		editorProjectId = log.project_id;
		editorTaskTypeId = log.task_type_id;
		editorDescription = log.description || '';
		editorLocation = log.location || '';
		// Normalize stored times to local-aware ISO so datetime-local inputs show local values
		editorStartISO = localOffsetISO(parseISOasLocal(log.start_time));
		editorEndISO = localOffsetISO(parseISOasLocal(log.end_time));
		isEditMode = false;
		showEditor = true;

		// Auto-set start date to next day when opening duplicate panel
		if (selectedLog && !duplicateStartDate) {
			const nextDay = new Date(parseISOasLocal(log.end_time));
			nextDay.setDate(nextDay.getDate() + 1);
			duplicateStartDate = nextDay.toISOString().split('T')[0];
		}

		// Ensure the editor color reflects this entity's established color
		editorColorName = getEntityColor(entityKeyForLog(log));
	}

	function cancelEditor() {
		showEditor = false;
		isEditMode = false;
		showDuplicatePanel = false;
		dragSelection = null;
		selectedLog = null;
		duplicateStartDate = '';
		duplicateEndDate = '';
		duplicateFrequency = 'daily-weekends';
	}

	// Pointer event handlers
	function handlePointerDown(day: number, hour: number, slot: number) {
		if (isTileBlocked(day, hour, slot)) return;

		selectionStartTime = Date.now();
		selectionStartCoord = { day, hour, slot };
		longPressTimeout = setTimeout(() => {
			startDragSelection(day, hour, slot);
		}, LONG_PRESS_DELAY) as unknown as number;
	}

	function handlePointerMove(day: number, hour: number, slot: number) {
		// If we're in the middle of a potential drag (long press started but not yet isSelecting)
		// and the user moves to a different tile, start the drag immediately
		if (selectionStartTime && selectionStartCoord && !isSelecting) {
			const { day: startDay, hour: startHour, slot: startSlot } = selectionStartCoord;
			if (day === startDay && (hour !== startHour || slot !== startSlot)) {
				// User moved to a different tile, start drag immediately
				if (longPressTimeout) {
					clearTimeout(longPressTimeout);
					longPressTimeout = null;
				}
				startDragSelection(startDay, startHour, startSlot);
				updateDragSelection(hour, slot);
			}
			return;
		}

		// During active selection, the global handler takes over, but we can still use this as a fallback
		// Normal drag update
		if (!isSelecting || !dragSelection || dragSelection.day !== day) return;
		updateDragSelection(hour, slot);
	}

	// Global pointer move handler to track dragging across tiles
	function handleGlobalPointerMove(event: PointerEvent) {
		// Only process if pointer is pressed and we're actively selecting
		if (event.buttons === 0 || !isSelecting || !dragSelection) return;

		// Auto-scroll when dragging near viewport edges
		const scrollThreshold = 50; // pixels from edge to trigger scroll
		const scrollSpeed = 10; // pixels to scroll per movement

		// Scroll window vertically
		if (event.clientY < scrollThreshold) {
			// Scroll up
			window.scrollBy(0, -scrollSpeed);
		} else if (event.clientY > window.innerHeight - scrollThreshold) {
			// Scroll down
			window.scrollBy(0, scrollSpeed);
		}

		// Scroll container horizontally
		const scrollContainer = document.querySelector('.mb-6.overflow-x-auto') as HTMLElement;
		if (scrollContainer) {
			const containerRect = scrollContainer.getBoundingClientRect();

			// Check if pointer is near right edge and scroll right
			if (event.clientX > containerRect.right - scrollThreshold) {
				scrollContainer.scrollLeft += scrollSpeed;
			}
			// Check if pointer is near left edge and scroll left
			else if (event.clientX < containerRect.left + scrollThreshold) {
				scrollContainer.scrollLeft -= scrollSpeed;
			}
		}

		// Find all hour boxes for the current day
		const hourBoxes = document.querySelectorAll(
			`[data-day="${dragSelection.day}"][data-hour]`
		) as NodeListOf<HTMLElement>;

		// Find which hour box contains the pointer
		let targetHourBox: HTMLElement | null = null;
		for (const box of hourBoxes) {
			const rect = box.getBoundingClientRect();
			if (
				event.clientX >= rect.left &&
				event.clientX <= rect.right &&
				event.clientY >= rect.top &&
				event.clientY <= rect.bottom
			) {
				targetHourBox = box;
				break;
			}
		}

		// Fallback: try elementFromPoint if we didn't find a containing box
		if (!targetHourBox) {
			const target = document.elementFromPoint(event.clientX, event.clientY);
			if (target) {
				targetHourBox = target.closest(
					`[data-day="${dragSelection.day}"][data-hour]`
				) as HTMLElement;
			}
		}

		if (!targetHourBox) return;

		// Extract day and hour from the container
		const day = parseInt(targetHourBox.getAttribute('data-day') || '-1', 10);
		const hour = parseInt(targetHourBox.getAttribute('data-hour') || '-1', 10);

		// Only process if we're on the same day and have valid hour
		if (day !== dragSelection.day || hour < 0 || hour >= 24) return;

		// Calculate which slot the pointer is over based on Y position relative to the hour box
		const rect = targetHourBox.getBoundingClientRect();
		const relativeY = event.clientY - rect.top;

		// Calculate slot index (0-based), clamped to valid range
		const slot = Math.max(0, Math.min(slotsPerHour - 1, Math.floor(relativeY / slotPixelHeight)));

		// Only update if the selection actually changed to avoid unnecessary reactivity triggers
		if (dragSelection.endHour !== hour || dragSelection.endSlot !== slot) {
			updateDragSelection(hour, slot);
		}
	}

	function handlePointerUp() {
		if (longPressTimeout) {
			clearTimeout(longPressTimeout);
			longPressTimeout = null;
		}

		if (!isSelecting && selectionStartTime && selectionStartCoord) {
			const delta = Date.now() - selectionStartTime;
			const { day, hour, slot } = selectionStartCoord;
			if (delta < LONG_PRESS_DELAY && !isTileBlocked(day, hour, slot)) {
				editorStartISO = isoFor(day, hour, slot);
				const endSlot = slot + 1;
				const endHour = hour + Math.floor(endSlot / slotsPerHour);
				const endSlotIndex = endSlot % slotsPerHour;
				editorEndISO = isoFor(day, endHour, endSlotIndex);
				selectedLog = null;
				// Reset editorType to default 'project' for new entries
				editorType = 'project';
				showEditor = true;
			}
		}

		if (isSelecting && dragSelection) {
			finalizeDragSelection();
		}

		isSelecting = false;
		selectionStartTime = null;
		selectionStartCoord = null;
	}

	function startDragSelection(day: number, hour: number, slot: number) {
		isSelecting = true;
		// neutral placeholder until a project/task is actually chosen in the editor
		dragColorName = DRAG_PREVIEW_COLOR;
		// propagate chosen color to editor on finalize
		editorColorName = dragColorName;
		dragSelection = {
			day,
			startHour: hour,
			startSlot: slot,
			endHour: hour,
			endSlot: slot
		};
	}

	// Walks slot-by-slot from anchorMin toward candidateMin and stops at the last free slot before
	// hitting a real block (existing timelog / contract range), so a drag can never grow on top of
	// an occupied slot — it just stops there.
	function clampToUnblockedRange(day: number, anchorMin: number, candidateMin: number): number {
		if (candidateMin === anchorMin) return candidateMin;
		const forward = candidateMin > anchorMin;
		const step = forward ? slotMinutes : -slotMinutes;
		let last = anchorMin;
		for (let m = anchorMin; forward ? m <= candidateMin : m >= candidateMin; m += step) {
			const h = Math.floor(m / 60);
			const s = Math.floor((m % 60) / slotMinutes);
			if (isTileReallyBlocked(day, h, s)) break;
			last = m;
		}
		return last;
	}

	function updateDragSelection(hour: number, slot: number) {
		if (!dragSelection) return;

		const { day, startHour, startSlot } = dragSelection;
		const anchorMin = startHour * 60 + startSlot * slotMinutes;
		const candidateMin = hour * 60 + slot * slotMinutes;
		const clampedMin = clampToUnblockedRange(day, anchorMin, candidateMin);
		const clampedHour = Math.floor(clampedMin / 60);
		const clampedSlot = Math.floor((clampedMin % 60) / slotMinutes);

		dragSelection = {
			...dragSelection,
			endHour: clampedHour,
			endSlot: clampedSlot
		};

		dragSelection = { ...dragSelection };

		const { startHour: sh, startSlot: ss, endHour, endSlot } = dragSelection;
		const startMinutes = sh * 60 + ss * slotMinutes;
		const endMinutes = endHour * 60 + endSlot * slotMinutes;
		const sMin = Math.min(startMinutes, endMinutes);
		const eMin = Math.max(startMinutes, endMinutes) + slotMinutes;

		const sHour = Math.floor(sMin / 60);
		const sSlot = Math.floor((sMin % 60) / slotMinutes);
		const eHour = Math.floor(eMin / 60);
		const eSlot = Math.floor((eMin % 60) / slotMinutes);

		editorStartISO = isoFor(day, sHour, sSlot);
		editorEndISO = isoFor(day, eHour, eSlot);
	}

	function finalizeDragSelection() {
		if (!dragSelection) return;

		const { day, startHour, startSlot, endHour, endSlot } = dragSelection;

		const startMinutes = startHour * 60 + startSlot * slotMinutes;
		const endMinutes = endHour * 60 + endSlot * slotMinutes;

		const sMin = Math.min(startMinutes, endMinutes);
		const eMin = Math.max(startMinutes, endMinutes) + slotMinutes; // Add slotMinutes to include the end slot

		const sHour = Math.floor(sMin / 60);
		const sSlot = Math.floor((sMin % 60) / slotMinutes);
		const eHour = Math.floor(eMin / 60);
		const eSlot = Math.floor((eMin % 60) / slotMinutes);

		editorStartISO = isoFor(day, sHour, sSlot);
		editorEndISO = isoFor(day, eHour, eSlot);
		// Reset editorType to default 'project' for new entries created via drag
		editorType = 'project';
		showEditor = true;
		// keep editorColorName set from dragColorName (set in startDragSelection)
		if (!editorColorName && dragColorName) editorColorName = dragColorName;
		dragSelection = null;
	}

	// Calculate and format duration for drag selection
	function getDragSelectionDuration(): string {
		if (!dragSelection) return '';

		const { startHour, startSlot, endHour, endSlot } = dragSelection;

		// Calculate total minutes from midnight for start and end
		const startMinutes = startHour * 60 + startSlot * slotMinutes;
		const endMinutes = endHour * 60 + endSlot * slotMinutes;

		// Determine the actual selection bounds (handle drag in either direction)
		const sMin = Math.min(startMinutes, endMinutes);
		const eMin = Math.max(startMinutes, endMinutes) + slotMinutes; // Add slotMinutes to include the end slot
		let totalMinutes = eMin - sMin;

		const hours = Math.floor(totalMinutes / 60);
		const minutes = totalMinutes % 60;

		if (hours === 0) {
			return `${minutes} min`;
		} else if (minutes === 0) {
			return hours === 1 ? '1 hour' : `${hours} hours`;
		} else {
			const hourText = hours === 1 ? '1 hour' : `${hours} hours`;
			const minText = minutes === 1 ? '1 min' : `${minutes} min`;
			return `${hourText} ${minText}`;
		}
	}

	// Format time range for drag selection (e.g., "8:00 AM - 9:00 AM")
	function getDragSelectionTimeRange(): string {
		if (!dragSelection) return '';

		const { startHour, startSlot, endHour, endSlot, day } = dragSelection;

		// Calculate total minutes from midnight for start and end
		const startMinutes = startHour * 60 + startSlot * slotMinutes;
		const endMinutes = endHour * 60 + endSlot * slotMinutes;

		// Determine the actual selection bounds (handle drag in either direction)
		const sMin = Math.min(startMinutes, endMinutes);
		const eMin = Math.max(startMinutes, endMinutes) + slotMinutes;

		// Convert to Date objects for formatting
		const sunday = weekDates && weekDates.length ? weekDates[0] : new Date();
		const baseDate = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + day);

		const startDate = new Date(baseDate);
		startDate.setHours(Math.floor(sMin / 60), sMin % 60, 0, 0);

		const endDate = new Date(baseDate);
		endDate.setHours(Math.floor(eMin / 60), eMin % 60, 0, 0);

		return formatTimeRange(startDate, endDate);
	}

	// Check if this is the start hour of the drag selection
	function isDragSelectionStartHour(h: number, day: number): boolean {
		if (!dragSelection || dragSelection.day !== day) return false;

		const { startHour, endHour } = dragSelection;
		const startMinutes = startHour * 60 + dragSelection.startSlot * slotMinutes;
		const endMinutes = endHour * 60 + dragSelection.endSlot * slotMinutes;
		const sMin = Math.min(startMinutes, endMinutes);
		const sHour = Math.floor(sMin / 60);

		return h === sHour;
	}

	// Calculate selection overlay for a specific hour
	function getSelectionOverlayForHour(h: number, day: number): string {
		if (!dragSelection || dragSelection.day !== day) return '';

		const { startHour, startSlot, endHour, endSlot } = dragSelection;

		const startMinutes = startHour * 60 + startSlot * slotMinutes;
		const endMinutes = endHour * 60 + endSlot * slotMinutes + slotMinutes;

		const sMin = Math.min(startMinutes, endMinutes);
		const eMin = Math.max(startMinutes, endMinutes);

		const hourStart = h * 60;
		const hourEnd = (h + 1) * 60;

		const segStart = Math.max(sMin, hourStart);
		const segEnd = Math.min(eMin, hourEnd);

		if (segEnd <= segStart) return '';

		const startSlotLocal = Math.floor((segStart - hourStart) / slotMinutes);
		const spanSlots = Math.max(1, Math.round((segEnd - segStart) / slotMinutes));

		const top = startSlotLocal * slotPixelHeight;
		const height = spanSlots * slotPixelHeight;

		const bg = dragColorName || DRAG_PREVIEW_COLOR;
		return `position: absolute; top: ${top}px; height: ${height}px; left: 0; right: 0; z-index: 10; background: ${bg}; pointer-events: none;`;
	}

	function getEditorOverlayForHour(h: number, day: number): string {
		if (!showEditor || !editorStartISO || !editorEndISO) return '';
		const dStart = parseISOasLocal(editorStartISO);
		const dEnd = parseISOasLocal(editorEndISO);
		const startMinutes = dStart.getHours() * 60 + dStart.getMinutes();
		const endMinutes = dEnd.getHours() * 60 + dEnd.getMinutes();
		const sMin = Math.min(startMinutes, endMinutes);
		const eMin = Math.max(startMinutes, endMinutes);
		const sunday = new Date(
			dStart.getFullYear(),
			dStart.getMonth(),
			dStart.getDate() - dStart.getDay()
		);
		const base = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + day);
		const sameDay =
			base.getFullYear() === dStart.getFullYear() &&
			base.getMonth() === dStart.getMonth() &&
			base.getDate() === dStart.getDate();
		if (!sameDay) return '';
		const hourStart = h * 60;
		const hourEnd = (h + 1) * 60;
		const segStart = Math.max(sMin, hourStart);
		const segEnd = Math.min(eMin, hourEnd);
		if (segEnd <= segStart) return '';
		const startSlotLocal = Math.floor((segStart - hourStart) / slotMinutes);
		const spanSlots = Math.max(1, Math.round((segEnd - segStart) / slotMinutes));
		const top = startSlotLocal * slotPixelHeight;
		const height = spanSlots * slotPixelHeight;
		const bg = editorColorName || DRAG_PREVIEW_COLOR;
		return `position: absolute; top: ${top}px; height: ${height}px; left: 0; right: 0; z-index: 9; background: ${bg}; pointer-events: none;`;
	}

	// Check if a tile is part of the current selection
	function isTileInSelection(day: number, hour: number, slot: number): boolean {
		if (!dragSelection || dragSelection.day !== day) return false;

		const { startHour, startSlot, endHour, endSlot } = dragSelection;

		const startMinutes = startHour * 60 + startSlot * slotMinutes;
		const endMinutes = endHour * 60 + endSlot * slotMinutes + slotMinutes;

		const sMin = Math.min(startMinutes, endMinutes);
		const eMin = Math.max(startMinutes, endMinutes);

		const tileStart = hour * 60 + slot * slotMinutes;
		const tileEnd = tileStart + slotMinutes;

		return tileEnd > sMin && tileStart < eMin;
	}

	function computeDayOffsetForDate(d: Date): number {
		if (!weekDates || weekDates.length === 0) return -1;
		const w0 = weekDates[0];
		const dayMid = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
		const w0Mid = new Date(w0.getFullYear(), w0.getMonth(), w0.getDate()).getTime();
		return Math.round((dayMid - w0Mid) / (24 * 60 * 60 * 1000));
	}

	function hasOverlapForRange(startISO: string, endISO: string, excludeLogId?: number): boolean {
		const s = parseISOasLocal(startISO);
		const e = parseISOasLocal(endISO);
		const day = computeDayOffsetForDate(s);
		const sMin = s.getHours() * 60 + s.getMinutes();
		const eMin = e.getHours() * 60 + e.getMinutes();
		for (const log of dayColumnLogs(day)) {
			if (excludeLogId !== undefined && log.id === excludeLogId) continue;
			const ld = parseISOasLocal(log.start_time);
			const startMin = ld.getHours() * 60 + ld.getMinutes();
			const end = parseISOasLocal(log.end_time);
			const endMin = end.getHours() * 60 + end.getMinutes();
			if (eMin > startMin && sMin < endMin) return true;
		}
		return false;
	}

	function dayColumnLogs(day: number) {
		// Use the viewed week's Monday from weekDates instead of current week
		let monday: Date;
		if (weekDates && weekDates.length > 0) {
			const w = weekDates[0];
			monday = new Date(w.getFullYear(), w.getMonth(), w.getDate());
		} else {
			// Fallback to current week if weekDates not set
			const today = new Date();
			const d0 = new Date(today.getFullYear(), today.getMonth(), today.getDate());
			monday = new Date(
				d0.getFullYear(),
				d0.getMonth(),
				d0.getDate() + (d0.getDay() === 0 ? -6 : 1 - d0.getDay())
			);
		}
		const mMidnight = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate()).getTime();
		return myLogs.filter((l) => {
			const d = parseISOasLocal(l.start_time);
			const dayMidnight = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
			const diffDays = Math.floor((dayMidnight - mMidnight) / (24 * 60 * 60 * 1000));
			return diffDays === day;
		});
	}

	// Sum total hours for a given day using server-calculated duration_minutes. Returns string like '0.00'
	// Excludes leave type logs from the total.
	function calculateDayTotalHours(day: number): string {
		const logs = dayColumnLogs(day);
		let totalMins = 0;
		for (const l of logs) {
			let logMins = l.duration_minutes || 0;
			if (logMins === 0 && l.start_time && l.end_time) {
				const s = parseISOasLocal(l.start_time);
				const e = parseISOasLocal(l.end_time);
				logMins = Math.round((e.getTime() - s.getTime()) / 60000);
			}
			totalMins += logMins;
		}
		return (totalMins / 60).toFixed(2);
	}

	// Reactive computed day totals - updates whenever myLogs changes
	$: dayTotalHoursMap = (() => {
		// Explicit dependency on myLogs for reactivity
		const logCount = myLogs.length;
		// Explicit dependency on weekDates for reactivity when navigating weeks
		const _w = weekDates;
		const map = new Map<number, string>();
		for (let day = -1; day <= 5; day++) {
			map.set(day, calculateDayTotalHours(day));
		}
		return map;
	})();

	// Helper function to get day total hours from reactive map
	function dayTotalHours(day: number): string {
		return dayTotalHoursMap.get(day) ?? '0.00';
	}

	// Check if a day is blocked (outside contract date range)
	function isDayBlocked(day: number): boolean {
		if (!weekDates || weekDates.length === 0) return false;
		const dayDate = dateForOffset(day);
		const dayDateOnly = new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate());
		if (contractStartDate && dayDateOnly.getTime() < contractStartDate.getTime()) {
			return true;
		}
		if (contractEndDate && dayDateOnly.getTime() > contractEndDate.getTime()) {
			return true;
		}
		return false;
	}

	// Sum total hours for the entire week using server-calculated duration_minutes. Returns string like '40.00'
	// Excludes leave type logs from the total; reactive to myLogs and weekDates changes.
	$: weekTotalHours = (() => {
		// Ensure dependency on myLogs for reactivity
		const logCount = myLogs.length;
		const dates = weekDates;
		if (!dates || dates.length === 0) return '0.00';
		let totalMins = 0;
		for (const day of [-1, 0, 1, 2, 3, 4, 5]) {
			const dayLogs = dayColumnLogs(day);
			for (const l of dayLogs) {
				let logMins = l.duration_minutes || 0;
				if (logMins === 0 && l.start_time && l.end_time) {
					const s = parseISOasLocal(l.start_time);
					const e = parseISOasLocal(l.end_time);
					logMins = Math.round((e.getTime() - s.getTime()) / 60000);
				}
				totalMins += logMins;
			}
		}
		return (totalMins / 60).toFixed(2);
	})();

	// Helper to get a log's duration in minutes (falls back to computing from start/end)
	function logDurationMinutes(log: TimelogResponse): number {
		let mins = log.duration_minutes || 0;
		if (mins === 0 && log.start_time && log.end_time) {
			const s = parseISOasLocal(log.start_time);
			const e = parseISOasLocal(log.end_time);
			mins = Math.round((e.getTime() - s.getTime()) / 60000);
		}
		return mins;
	}

	// All logs visible in the currently displayed week (Sun-Sat) — feeds the sidebar
	$: weekLogsForSidebar = (() => {
		const _dep = myLogs.length; // explicit dependency for reactivity
		if (!weekDates || weekDates.length === 0) return [] as TimelogResponse[];
		let all: TimelogResponse[] = [];
		for (const dayOffset of sundayFirstOrder) {
			all = all.concat(dayColumnLogs(dayOffset));
		}
		return all;
	})();

	// Distinct projects logged this week, in the color used on the calendar, with total hours per project
	$: sidebarProjects = (() => {
		const map = new Map<number, { id: number; name: string; color: string; minutes: number }>();
		for (const log of weekLogsForSidebar) {
			if (log.type === 'project' && log.project_id) {
				const existing = map.get(log.project_id);
				if (existing) {
					existing.minutes += logDurationMinutes(log);
				} else {
					const proj = allProjects.find((p) => p.id === log.project_id);
					map.set(log.project_id, {
						id: log.project_id,
						name: proj ? proj.project_name : `Project #${log.project_id}`,
						color: getEntityColor(entityKeyForLog(log)),
						minutes: logDurationMinutes(log)
					});
				}
			}
		}
		return Array.from(map.values());
	})();

	// Distinct "other" tasks logged this week, with total hours per task type
	$: sidebarOtherTasks = (() => {
		const map = new Map<number, { id: number; name: string; color: string; minutes: number }>();
		for (const log of weekLogsForSidebar) {
			if (log.type === 'other' && log.task_type_id) {
				const existing = map.get(log.task_type_id);
				if (existing) {
					existing.minutes += logDurationMinutes(log);
				} else {
					const tt = taskTypes.find((t) => t.id === log.task_type_id);
					map.set(log.task_type_id, {
						id: log.task_type_id,
						name: tt ? tt.name : `Task #${log.task_type_id}`,
						color: getEntityColor(entityKeyForLog(log)),
						minutes: logDurationMinutes(log)
					});
				}
			}
		}
		return Array.from(map.values());
	})();

	// Distinct leave/holiday types logged this week, with total hours per type
	$: sidebarLeaves = (() => {
		const map = new Map<number, { id: number; name: string; color: string; minutes: number }>();
		for (const log of weekLogsForSidebar) {
			if (log.type === 'leave' && log.task_type_id) {
				const existing = map.get(log.task_type_id);
				if (existing) {
					existing.minutes += logDurationMinutes(log);
				} else {
					const tt = taskTypes.find((t) => t.id === log.task_type_id);
					map.set(log.task_type_id, {
						id: log.task_type_id,
						name: tt ? tt.name : `Leave #${log.task_type_id}`,
						color: getEntityColor(entityKeyForLog(log)),
						minutes: logDurationMinutes(log)
					});
				}
			}
		}
		return Array.from(map.values());
	})();

	// Computes one continuous overlay spanning the log's full duration, positioned
	// relative to the day column (not per-hour), so the label renders exactly once.
	function fullOverlayStyleForLog(log: TimelogResponse): string {
		const dStart = parseISOasLocal(log.start_time);
		const dEnd = parseISOasLocal(log.end_time);
		const sMin = dStart.getHours() * 60 + dStart.getMinutes();
		const eMin = dEnd.getHours() * 60 + dEnd.getMinutes();

		const visibleStartMin = hours[0] * 60;
		const visibleEndMin = (hours[hours.length - 1] + 1) * 60;

		const segStart = Math.max(sMin, visibleStartMin);
		const segEnd = Math.min(eMin, visibleEndMin);
		if (segEnd <= segStart) return ''; // entirely outside the visible hour range

		const pixelsPerMinute = slotPixelHeight / slotMinutes;
		const top = (segStart - visibleStartMin) * pixelsPerMinute;
		const height = (segEnd - segStart) * pixelsPerMinute;

		const bg = getEntityColor(entityKeyForLog(log));
		return `position: absolute; top: ${top}px; height: ${height}px; left: 0; right: 0; z-index: 8; background: ${bg};`;
	}

	// "Really" blocked = contract date range or an existing timelog overlap — independent of
	// whatever is currently being drag-selected. Used both for tile rendering and for clamping drags.
	function isTileReallyBlocked(day: number, hour: number, slotIndex: number): boolean {
		const tileStartMin = hour * 60 + slotIndex * slotMinutes;
		const tileEndMin = tileStartMin + slotMinutes;

		try {
			if (weekDates && weekDates.length > 0 && (contractStartDate || contractEndDate)) {
				const w = weekDates[0];
				const tileDate = new Date(w.getFullYear(), w.getMonth(), w.getDate() + day);
				const tileDateOnly = new Date(
					tileDate.getFullYear(),
					tileDate.getMonth(),
					tileDate.getDate()
				);
				if (
					(contractStartDate && tileDateOnly.getTime() < contractStartDate.getTime()) ||
					(contractEndDate && tileDateOnly.getTime() > contractEndDate.getTime())
				) {
					return true;
				}
			}
		} catch (e) {}

		for (const log of dayColumnLogs(day)) {
			const d = parseISOasLocal(log.start_time);
			const startMin = d.getHours() * 60 + d.getMinutes();
			const end = parseISOasLocal(log.end_time);
			const endMin = end.getHours() * 60 + end.getMinutes();
			if (tileEndMin > startMin && tileStartMin < endMin) return true;
		}

		return false;
	}

	function isTileBlocked(day: number, hour: number, slotIndex: number): boolean {
		if (isSelecting && isTileInSelection(day, hour, slotIndex)) return true;
		return isTileReallyBlocked(day, hour, slotIndex);
	}

	// Structural/hover classes only — the actual background color comes from tileStyleFor,
	// since generated hex colors can't be expressed as static Tailwind classes.
	function tileClassFor(day: number, h: number, slotIndex: number): string {
		const blocked = isTileBlocked(day, h, slotIndex);

		if (
			isSelecting &&
			dragSelection &&
			dragSelection.day === day &&
			isTileInSelection(day, h, slotIndex)
		) {
			return 'cursor-not-allowed';
		}

		if (!blocked) return 'hover:bg-blue-100 dark:hover:bg-gray-700';

		return 'cursor-not-allowed';
	}

	// Background color for a tile, kept in sync with whatever color the overlay bars use.
	function tileStyleFor(day: number, h: number, slotIndex: number): string {
		if (
			isSelecting &&
			dragSelection &&
			dragSelection.day === day &&
			isTileInSelection(day, h, slotIndex)
		) {
			return `background: ${dragColorName || DRAG_PREVIEW_COLOR};`;
		}

		if (!isTileBlocked(day, h, slotIndex)) return '';

		// Otherwise, find the first overlapping log and use its assigned color
		for (const log of dayColumnLogs(day)) {
			const d = parseISOasLocal(log.start_time);
			const startMin = d.getHours() * 60 + d.getMinutes();
			const end = parseISOasLocal(log.end_time);
			const endMin = end.getHours() * 60 + end.getMinutes();
			const tileStart = h * 60 + slotIndex * slotMinutes;
			const tileEnd = tileStart + slotMinutes;
			if (tileEnd > startMin && tileStart < endMin) {
				return `background: ${getEntityColor(entityKeyForLog(log))};`;
			}
		}

		// fallback
		return 'background: #d1d5db;';
	}

	function toLocalInput(iso: string): string {
		if (!iso) return '';
		// Parse ISO treating naive datetimes as local
		const d = parseISOasLocal(iso);
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		const hh = String(d.getHours()).padStart(2, '0');
		const mm = String(d.getMinutes()).padStart(2, '0');
		return `${y}-${m}-${day}T${hh}:${mm}`;
	}

	function ensureEntityColors() {
		for (const l of myLogs) {
			getEntityColor(entityKeyForLog(l));
		}
	}

	function loadEntityColorsFromStorage() {
		try {
			const raw = localStorage.getItem('entityColors');
			if (raw) {
				const obj = JSON.parse(raw) as Record<string, string>;
				const hexPattern = /^#[0-9a-fA-F]{6}$/;
				for (const k of Object.keys(obj)) {
					const v = obj[k];
					if (typeof v === 'string' && hexPattern.test(v)) {
						entityColors.set(k, v);
					}
				}
			}
			const counterRaw = localStorage.getItem('entityColorCounter');
			if (counterRaw) {
				const n = parseInt(counterRaw, 10);
				if (!isNaN(n) && n > colorAssignCounter) colorAssignCounter = n;
			}
		} catch (e) {
			// ignore parse errors
		}
	}

	function saveEntityColorsToStorage() {
		try {
			const obj: Record<string, string> = {};
			for (const [k, v] of entityColors.entries()) {
				obj[k] = v;
			}
			localStorage.setItem('entityColors', JSON.stringify(obj));
			localStorage.setItem('entityColorCounter', String(colorAssignCounter));
		} catch (e) {
			// ignore storage errors (e.g., privacy mode)
		}
	}

	function fromLocalInput(val: string): string {
		if (!val) return '';
		const d = new Date(val);
		return localOffsetISO(d);
	}

	function recalcSpentHours(): string {
		if (!editorStartISO || !editorEndISO) return '0.00';

		const s = parseISOasLocal(editorStartISO);
		const e = parseISOasLocal(editorEndISO);

		// Check if dates are valid
		if (isNaN(s.getTime()) || isNaN(e.getTime())) {
			console.error('Invalid dates:', { start: editorStartISO, end: editorEndISO, s, e });
			return '0.00';
		}

		// Calculate difference in milliseconds, then convert to minutes
		const diffMs = e.getTime() - s.getTime();
		let mins = Math.max(0, Math.round(diffMs / 60000));

		// Debug logging (can be removed later)
		if (mins === 0 && diffMs !== 0) {
			console.log('Hours calculation debug:', {
				startISO: editorStartISO,
				endISO: editorEndISO,
				startDate: s,
				endDate: e,
				diffMs,
				mins,
				startTime: s.getTime(),
				endTime: e.getTime()
			});
		}

		const startHour = s.getHours();
		const startMin = s.getMinutes();
		const endHour = e.getHours();
		const endMin = e.getMinutes();
		const startMinutes = startHour * 60 + startMin;
		const endMinutes = endHour * 60 + endMin;

		// If result is 0 but we have valid different times, ensure minimum slot
		if (mins === 0) {
			if (diffMs > 0) {
				// Times are different but rounded to 0, use actual difference or minimum slot
				mins = Math.max(slotMinutes, Math.round(diffMs / 60000));
			} else if (diffMs === 0 && editorStartISO && editorEndISO) {
				// Same time, but we have valid times set - use minimum slot
				mins = slotMinutes;
			}
		}

		return (mins / 60).toFixed(2);
	}

	function managerName(): string {
		if (editorType !== 'project' || !editorProjectId) return 'Select Project first';
		const p = projects.find((x) => x.id === editorProjectId);
		if (!p || !p.manager_id) return 'Unassigned';
		const u = users.find((x) => x.id === p.manager_id);
		if (!u) return String(p.manager_id);

		// Return full name if available, otherwise username
		const fullName = `${u.first_name || ''} ${u.last_name || ''}`.trim();
		return fullName || u.username;
	}

	function getTaskTypeName(id?: number): string {
		if (!id) return '';
		const t = taskTypes.find((x) => x.id === id);
		return t ? t.name : '';
	}
</script>

<svelte:window on:pointerup={handlePointerUp} />

<div class="container mx-auto px-4 py-6">
	<h1 class="mb-1 text-2xl font-semibold dark:text-white">
		Task Calendar - {(() => {
			const fullName = `${currentUserFirstName} ${currentUserLastName}`.trim();
			return fullName || currentUsername;
		})()}
	</h1>

	<div class="flex flex-col gap-4 lg:flex-row">
		<!-- Sidebar -->
		<aside class="w-full flex-shrink-0 space-y-4 lg:w-72">
			<!-- Notes -->
			<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
				<button
					type="button"
					class="flex w-full items-center justify-between bg-gray-100 px-4 py-2 text-left text-sm font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-100"
					on:click={() => (notesOpen = !notesOpen)}
				>
					<span>Notes</span>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class={`h-4 w-4 flex-shrink-0 transition-transform ${notesOpen ? '' : '-rotate-90'}`}
						viewBox="0 0 20 20"
						fill="currentColor"
					>
						<path
							fill-rule="evenodd"
							d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
							clip-rule="evenodd"
						/>
					</svg>
				</button>
				{#if notesOpen}
					<div class="bg-white px-4 py-3 text-sm text-gray-700 dark:bg-gray-900 dark:text-gray-200">
						<ul class="list-disc space-y-1 pl-4">
							<li>For task timelogs, do not log time for lunch breaks.</li>
							<li>For onsite time adjustments, include time for lunch breaks.</li>
							<li>
								For any clarifications/suggestions, please contact admin, or email to:
								<a href="mailto:arieskingnieto@gmail.com" class="text-blue-600 hover:underline"
									>arieskingnieto@gmail.com</a
								>
							</li>
						</ul>
					</div>
				{/if}
			</div>

			<!-- Projects -->
			<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
				<button
					type="button"
					class="flex w-full items-center justify-between bg-gray-100 px-4 py-2 text-left text-sm font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-100"
					on:click={() => (projectsOpen = !projectsOpen)}
				>
					<span>Projects</span>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class={`h-4 w-4 flex-shrink-0 transition-transform ${projectsOpen ? '' : '-rotate-90'}`}
						viewBox="0 0 20 20"
						fill="currentColor"
					>
						<path
							fill-rule="evenodd"
							d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
							clip-rule="evenodd"
						/>
					</svg>
				</button>
				{#if projectsOpen}
					<div class="bg-white dark:bg-gray-900">
						{#if sidebarProjects.length === 0}
							<div class="px-4 py-3 text-sm text-gray-400 dark:text-gray-500">
								No projects logged this week
							</div>
						{:else}
							{#each sidebarProjects as p (p.id)}
								<div
									class="flex items-center gap-2 border-t border-gray-100 px-4 py-2 text-sm text-gray-800 first:border-t-0 dark:border-gray-800 dark:text-gray-100"
								>
									<span class="h-3 w-3 flex-shrink-0 rounded-sm" style={`background: ${p.color};`}
									></span>
									<span class="flex-1 truncate">{p.name}</span>
									<span
										class="flex-shrink-0 rounded-full bg-gray-500 px-2 py-0.5 text-xs text-white"
									>
										{(p.minutes / 60).toFixed(2)}
									</span>
								</div>
							{/each}
						{/if}
					</div>
				{/if}
			</div>

			<!-- Other Tasks -->
			<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
				<button
					type="button"
					class="flex w-full items-center justify-between bg-gray-100 px-4 py-2 text-left text-sm font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-100"
					on:click={() => (otherTasksOpen = !otherTasksOpen)}
				>
					<span>Other Tasks</span>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class={`h-4 w-4 flex-shrink-0 transition-transform ${otherTasksOpen ? '' : '-rotate-90'}`}
						viewBox="0 0 20 20"
						fill="currentColor"
					>
						<path
							fill-rule="evenodd"
							d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
							clip-rule="evenodd"
						/>
					</svg>
				</button>
				{#if otherTasksOpen}
					<div class="bg-white dark:bg-gray-900">
						{#if sidebarOtherTasks.length === 0}
							<div class="px-4 py-3 text-sm text-gray-400 dark:text-gray-500">
								No other tasks logged this week
							</div>
						{:else}
							{#each sidebarOtherTasks as t (t.id)}
								<div
									class="flex items-center gap-2 border-t border-gray-100 px-4 py-2 text-sm text-gray-800 first:border-t-0 dark:border-gray-800 dark:text-gray-100"
								>
									<span class="h-3 w-3 flex-shrink-0 rounded-sm" style={`background: ${t.color};`}
									></span>
									<span class="flex-1 truncate">{t.name}</span>
									<span
										class="flex-shrink-0 rounded-full bg-gray-500 px-2 py-0.5 text-xs text-white"
									>
										{(t.minutes / 60).toFixed(2)}
									</span>
								</div>
							{/each}
						{/if}
					</div>
				{/if}
			</div>

			<!-- Leaves and Holidays -->
			<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
				<button
					type="button"
					class="flex w-full items-center justify-between bg-gray-100 px-4 py-2 text-left text-sm font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-100"
					on:click={() => (leavesOpen = !leavesOpen)}
				>
					<span>Leaves and Holidays</span>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class={`h-4 w-4 flex-shrink-0 transition-transform ${leavesOpen ? '' : '-rotate-90'}`}
						viewBox="0 0 20 20"
						fill="currentColor"
					>
						<path
							fill-rule="evenodd"
							d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
							clip-rule="evenodd"
						/>
					</svg>
				</button>
				{#if leavesOpen}
					<div class="bg-white dark:bg-gray-900">
						{#if sidebarLeaves.length === 0}
							<div class="px-4 py-3 text-sm text-gray-400 dark:text-gray-500">
								No leaves logged this week
							</div>
						{:else}
							{#each sidebarLeaves as l (l.id)}
								<div
									class="flex items-center gap-2 border-t border-gray-100 px-4 py-2 text-sm text-gray-800 first:border-t-0 dark:border-gray-800 dark:text-gray-100"
								>
									<span class="h-3 w-3 flex-shrink-0 rounded-sm" style={`background: ${l.color};`}
									></span>
									<span class="flex-1 truncate">{l.name}</span>
									<span
										class="flex-shrink-0 rounded-full bg-gray-500 px-2 py-0.5 text-xs text-white"
									>
										{(l.minutes / 60).toFixed(2)}
									</span>
								</div>
							{/each}
						{/if}
					</div>
				{/if}
			</div>
		</aside>

		<!-- Main calendar area -->
		<div class="min-w-0 flex-1">
			<div class="mb-4 flex items-center justify-between text-sm text-gray-600 dark:text-gray-300">
				<div class="flex items-center gap-2">
					<span>{weekRangeLabel}</span>
					<span class="font-medium">•</span>
					<span
						class="font-semibold {parseFloat(weekTotalHours) > 0
							? 'text-green-600 dark:text-green-400'
							: 'text-red-600 dark:text-red-400'}"
					>
						{weekTotalHours} hrs
					</span>
				</div>
				<div class="flex items-center gap-2">
					<!-- View Mode Toggle -->
					<div class="flex items-center gap-1 rounded border bg-white p-1 dark:bg-gray-800">
						<button
							class={`rounded px-2 py-1 text-xs ${viewMode === 'work-hours' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}`}
							on:click={() => {
								viewMode = 'work-hours';
								if (typeof localStorage !== 'undefined')
									localStorage.setItem('calendarViewMode', 'work-hours');
							}}
							title="Work Hours (8AM-6PM)"
						>
							8-6
						</button>
						<button
							class={`rounded px-2 py-1 text-xs ${viewMode === '12-hours' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}`}
							on:click={() => {
								viewMode = '12-hours';
								if (typeof localStorage !== 'undefined')
									localStorage.setItem('calendarViewMode', '12-hours');
							}}
							title="12 Hours (7AM-7PM)"
						>
							12h
						</button>
						<button
							class={`rounded px-2 py-1 text-xs ${viewMode === '24-hours' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}`}
							on:click={() => {
								viewMode = '24-hours';
								if (typeof localStorage !== 'undefined')
									localStorage.setItem('calendarViewMode', '24-hours');
							}}
							title="24 Hours (12AM-11:59PM)"
						>
							24h
						</button>
					</div>
					<button
						class="rounded border bg-white px-2 py-1 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700"
						on:click={goPrevWeek}
						aria-label="Previous week"
						disabled={isAtEarliestYear}
						class:opacity-50={isAtEarliestYear}
						class:cursor-not-allowed={isAtEarliestYear}
					>
						<!-- left chevron -->
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="h-4 w-4"
							viewBox="0 0 20 20"
							fill="currentColor"
						>
							<path
								fill-rule="evenodd"
								d="M7.707 3.707a1 1 0 010 1.414L4.414 9H16a1 1 0 110 2H4.414l3.293 3.293a1 1 0 01-1.414 1.414l-5-5a1 1 0 010-1.414l5-5a1 1 0 011.414 0z"
								clip-rule="evenodd"
							/>
						</svg>
					</button>
					<button
						class="flex items-center gap-1 rounded border bg-white px-2 py-1 text-sm hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700"
						on:click={(e) => openDatePicker(e)}
						aria-label="Jump to date"
					>
						Jump to
						<!-- calendar icon -->
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="h-4 w-4"
							viewBox="0 0 20 20"
							fill="currentColor"
						>
							<path
								d="M4 4a2 2 0 00-2 2v9a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1.586a1 1 0 00-.707.293l-1.414-1.414A1 1 0 0010 2H8a1 1 0 00-.707.293l-1.414 1.414A1 1 0 005.172 4H4zm0 2h12v9H4V6z"
							/>
						</svg>
					</button>
					<button
						class="rounded border bg-white px-2 py-1 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700"
						on:click={goNextWeek}
						aria-label="Next week"
						disabled={isAtLatestWeek}
						class:opacity-50={isAtLatestWeek}
						class:cursor-not-allowed={isAtLatestWeek}
					>
						<!-- right chevron -->
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="h-4 w-4"
							viewBox="0 0 20 20"
							fill="currentColor"
						>
							<path
								fill-rule="evenodd"
								d="M12.293 16.293a1 1 0 010-1.414L15.586 11H4a1 1 0 110-2h11.586l-3.293-3.293a1 1 0 011.414-1.414l5 5a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0z"
								clip-rule="evenodd"
							/>
						</svg>
					</button>
				</div>
			</div>

			<div class="mb-6 overflow-x-auto">
				<div
					class="grid"
					role="presentation"
					style="grid-template-columns: 120px repeat(7, 1fr);"
					on:pointerup={handlePointerUp}
				>
					<div></div>
					{#key `${formatDateYMD(weekDates[0])}-${myLogs.length}`}
						{#each sundayFirstOrder as dayOffset, i (dayOffset)}
							<div
								class="border-b p-2 text-center text-sm dark:text-white"
								class:final-day={i === 6}
							>
								<div class="font-medium">{dayLabelForOffset(dayOffset)}</div>
								<div class="text-xs text-gray-500 dark:text-gray-300">
									{String(dateForOffset(dayOffset).getMonth() + 1).padStart(2, '0')}/{String(
										dateForOffset(dayOffset).getDate()
									).padStart(2, '0')}
								</div>
								<div
									class="text-xs {isDayBlocked(dayOffset)
										? 'text-orange-500 dark:text-orange-400'
										: parseFloat(dayTotalHours(dayOffset)) >= 8
											? 'text-green-500 dark:text-green-400'
											: 'text-red-500 dark:text-red-400'} mt-1"
								>
									{isDayBlocked(dayOffset) ? 'blocked' : dayTotalHours(dayOffset) + ' hrs'}
								</div>
							</div>
						{/each}
					{/key}
					{#key `${viewMode}-${weekDates.length > 0 ? formatDateYMD(weekDates[0]) : 'default'}-${myLogs.map((l) => l.id + ':' + l.updated_at).join(',')}-${isSelecting && dragSelection ? `${dragSelection.startHour}-${dragSelection.startSlot}-${dragSelection.endHour}-${dragSelection.endSlot}` : ''}-${contractRangeKey}`}
						<!-- Hour label column: one grid item, all hour labels stacked vertically -->
						<div>
							{#each hours as h (h)}
								<div
									class="hour-label-box p-2 text-xs text-gray-500 dark:text-gray-300"
									class:last-hour-label={h === hours[hours.length - 1]}
									class:current-hour-label={isCurrentHourLabel(h)}
									style={`height: ${slotsPerHour * slotPixelHeight}px; position: relative;`}
								>
									<!-- Top-aligned hour label (aligns with the 1st 15-min slot) -->
									<div style="position: absolute; top: 0; left: 0;">{formatHourLabel(h)}</div>
									<!-- Half-hour label aligned with the 3rd slot (2 * slotPixelHeight) -->
									<div style={`position: absolute; top: ${2 * slotPixelHeight}px; left: 0;`}>
										{formatHalfHourLabel(h)}
									</div>
								</div>
							{/each}
						</div>

						<!-- One grid item per day: relative-positioned column holding the hour rows plus one continuous overlay per log -->
						{#each sundayFirstOrder as dayOffset, i (dayOffset)}
							<div class="relative" class:day-divider={i > 0} class:last-day={i === 6}>
								{#each hours as h (h)}
									<div
										class="minute-grid hour-box relative grid"
										class:last-hour={h === hours[hours.length - 1]}
										role="presentation"
										style={`grid-template-rows: repeat(${slotsPerHour}, ${slotPixelHeight}px); position: relative;`}
										data-day={dayOffset}
										data-hour={h}
									>
										{#each [...Array(slotsPerHour).keys()] as slot (slot)}
											<button
												aria-label={`Add entry ${h}:${(slot * slotMinutes).toString().padStart(2, '0')}`}
												class={`h-full w-full ${tileClassFor(dayOffset, h, slot)}`}
												style={tileStyleFor(dayOffset, h, slot)}
												data-day={dayOffset}
												data-hour={h}
												data-slot={slot}
												on:pointerdown={() => handlePointerDown(dayOffset, h, slot)}
												on:pointerenter={() => handlePointerMove(dayOffset, h, slot)}
												aria-disabled={isTileBlocked(dayOffset, h, slot)}
												disabled={isTileBlocked(dayOffset, h, slot)}
											></button>
										{/each}

										{#if isSelecting && dragSelection?.day === dayOffset && dragSelection}
											{@const overlayStyle = getSelectionOverlayForHour(h, dayOffset)}
											{#if overlayStyle}
												<div class="pointer-events-none absolute" style={overlayStyle}>
													{#if isDragSelectionStartHour(h, dayOffset)}
														<div class="px-1 text-[10px] leading-tight text-white">
															<div class="font-semibold">{getDragSelectionDuration()}</div>
															<div class="mt-0.5 text-[9px] opacity-90">
																{getDragSelectionTimeRange()}
															</div>
														</div>
													{/if}
												</div>
											{/if}
										{/if}

										{#if showEditor && getEditorOverlayForHour(h, dayOffset)}
											<div class="absolute" style={getEditorOverlayForHour(h, dayOffset)}></div>
										{/if}
									</div>
								{/each}

								<!-- One continuous overlay per log, spanning its full duration -->
								{#each dayColumnLogs(dayOffset) as log (log.id)}
									{#if fullOverlayStyleForLog(log)}
										<button
											type="button"
											class="absolute cursor-pointer overflow-hidden text-white"
											style={fullOverlayStyleForLog(log)}
											on:click={() => openEditorForLog(log)}
											tabindex="0"
										>
											<div class="sticky top-0 px-1 text-[10px] leading-tight">
												<div class="font-semibold">
													{formatTimeRange(
														parseISOasLocal(log.start_time),
														parseISOasLocal(log.end_time)
													)}
												</div>
												{#if log.type === 'leave' && log.task_type_id}
													<div class="mt-0.5 text-[9px] opacity-90">
														leave-{getTaskTypeName(log.task_type_id)}
													</div>
												{/if}
												{#if log.description}
													<div class="mt-0.5 {log.type === 'leave' ? 'text-xs' : ''}">
														{log.description}
													</div>
												{/if}
											</div>
											<div class="absolute top-0 right-0 p-0.5 opacity-90">
												{#if log.status === 'Approved'}
													<IconCheck class="h-3 w-3 text-white" />
												{:else}
													<IconXMark class="h-3 w-3 text-white" />
												{/if}
											</div>
										</button>
									{/if}
								{/each}
							</div>
						{/each}
					{/key}
				</div>
			</div>
		</div>
	</div>

	<div
		class={showEditor
			? 'fixed inset-0 z-50 flex items-center justify-center overflow-y-auto'
			: 'hidden'}
		style="background: rgba(0, 0, 0, 0.1); backdrop-filter: blur(2px);"
	>
		<div
			class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto"
			style="background: rgba(0, 0, 0, 0.1); backdrop-filter: blur(2px);"
		>
			<div class="my-6 w-full max-w-4xl rounded-2xl bg-white p-6 font-sans shadow-2xl">
				<!-- Header with Title and Status Badge -->
				<div class="mb-6 flex items-start justify-between">
					<h3 class="text-2xl font-semibold text-neutral-900">
						{selectedLog ? 'Edit Timelog' : 'Timelog'}
					</h3>
					<div class="rounded-full bg-gray-500 px-4 py-1 text-sm text-white">
						{#if selectedLog}
							{#if selectedLog.status === 'Approved'}
								✓ Approved
							{:else if selectedLog.status === 'Rejected'}
								✗ Rejected
							{:else}
								⏳ For Approval
							{/if}
						{:else}
							New
						{/if}
					</div>
				</div>

				{#if warningMessage}
					<div
						class="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700"
					>
						{warningMessage}
					</div>
				{/if}

				<!-- Main Content Area: Left (Form) + Right (Info Box) -->
				<div class="grid grid-cols-12 gap-4">
					<!-- Left Column: Form Fields -->
					<div class="col-span-8">
						<!-- From, To, Spent Hours Row -->
						<div class="grid grid-cols-12 gap-4">
							<div class="col-span-4">
								<label for="from" class="mb-1 block text-sm font-medium text-neutral-700"
									>From</label
								>
								<input
									id="from"
									type="datetime-local"
									disabled={selectedLog && !isEditMode}
									class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
									value={toLocalInput(editorStartISO)}
									on:change={(e) => {
										const newValue = fromLocalInput((e.target as HTMLInputElement).value);
										if (editorType === 'leave') {
											const startDate = parseISOasLocal(newValue);
											const hour = startDate.getHours();
											const min = startDate.getMinutes();
											const minutes = hour * 60 + min;

											// No restriction; allow any start time for leave
										}
										editorStartISO = newValue;
									}}
								/>
							</div>
							<div class="col-span-4">
								<label for="to" class="mb-1 block text-sm font-medium text-neutral-700">To</label>
								<input
									id="to"
									type="datetime-local"
									disabled={selectedLog && !isEditMode}
									class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
									value={toLocalInput(editorEndISO)}
									on:change={(e) => {
										const newValue = fromLocalInput((e.target as HTMLInputElement).value);
										if (editorType === 'leave') {
											const endDate = parseISOasLocal(newValue);
											const hour = endDate.getHours();
											const min = endDate.getMinutes();
											const minutes = hour * 60 + min;

											// Check if start time is set
											if (editorStartISO) {
												const startDate = parseISOasLocal(editorStartISO);
												const startHour = startDate.getHours();
												const startMin = startDate.getMinutes();
												const startMinutes = startHour * 60 + startMin;

												// No restriction; allow any end time for leave
											}
										}
										editorEndISO = newValue;
									}}
								/>
							</div>
							<div class="col-span-4">
								<label for="spent-hours" class="mb-1 block text-sm font-medium text-neutral-700"
									>Spent Hours</label
								>
								{#key `${editorStartISO}-${editorEndISO}`}
									<input
										id="spent-hours"
										class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm"
										value={recalcSpentHours()}
										readonly
									/>
								{/key}
							</div>
						</div>

						<!-- Select Type Buttons -->
						<div class="mt-4 flex gap-2">
							<button
								disabled={selectedLog && !isEditMode}
								class={(editorType === 'project'
									? 'bg-blue-600 text-white '
									: 'bg-neutral-100 text-neutral-800 ') +
									'rounded-md border border-neutral-300 px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50'}
								on:click={() => {
									editorType = 'project';
									editorTaskTypeId = undefined;
								}}>Project</button
							>
							<button
								disabled={selectedLog && !isEditMode}
								class={(editorType === 'other'
									? 'bg-blue-600 text-white '
									: 'bg-neutral-100 text-neutral-800 ') +
									'rounded-md border border-neutral-300 px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50'}
								on:click={() => {
									editorType = 'other';
									editorProjectId = undefined;
								}}>Other Task</button
							>
							<button
								disabled={selectedLog && !isEditMode}
								class={(editorType === 'leave'
									? 'bg-blue-600 text-white '
									: 'bg-neutral-100 text-neutral-800 ') +
									'rounded-md border border-neutral-300 px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50'}
								on:click={() => {
									editorType = 'leave';
									editorProjectId = undefined;
								}}>Leave</button
							>
						</div>

						<!-- Project and Task Type -->
						<div class="mt-5 grid grid-cols-12 gap-4">
							<div class="col-span-12 sm:col-span-6">
								{#if editorType === 'project'}
									<label for="project" class="mb-1 block text-sm font-medium text-neutral-700"
										>Project</label
									>
									<select
										id="project"
										disabled={selectedLog && !isEditMode}
										class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
										on:change={(e) => {
											const v = (e.target as HTMLSelectElement).value;
											editorProjectId = v ? Number(v) : undefined;
										}}
									>
										<option value="">Select</option>
										{#each projects as p (p.id)}
											<option value={p.id} selected={editorProjectId === p.id}
												>{p.project_name}</option
											>
										{/each}
									</select>
								{:else if editorType === 'other'}
									<label
										for="task-type-other"
										class="mb-1 block text-sm font-medium text-neutral-700">Task</label
									>
									<select
										id="task-type"
										disabled={selectedLog && !isEditMode}
										class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
										on:change={(e) => {
											const v = (e.target as HTMLSelectElement).value;
											editorTaskTypeId = v ? Number(v) : undefined;
										}}
									>
										<option value="">Select</option>
										{#each taskTypes.filter((t) => t.category === (editorType === 'other' ? 'other' : 'leave')) as tt (tt.id)}
											<option value={tt.id} selected={editorTaskTypeId === tt.id}>{tt.name}</option>
										{/each}
									</select>
								{:else}
									<label
										for="task-type-leave"
										class="mb-1 block text-sm font-medium text-neutral-700">Leave Type</label
									>
									<select
										id="task-type-leave"
										disabled={selectedLog && !isEditMode}
										class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
										on:change={(e) => {
											const v = (e.target as HTMLSelectElement).value;
											editorTaskTypeId = v ? Number(v) : undefined;
										}}
									>
										<option value="">Select</option>
										{#each taskTypes.filter((t) => t.category === 'leave') as tt (tt.id)}
											<option value={tt.id} selected={editorTaskTypeId === tt.id}>{tt.name}</option>
										{/each}
									</select>
								{/if}
							</div>
						</div>

						<!-- Summary of Task Done -->
						<div class="mt-5">
							<label for="summary" class="mb-1 block text-sm font-medium text-neutral-700"
								>Summary of Task Done</label
							>
							<textarea
								id="summary"
								disabled={selectedLog && !isEditMode}
								class="w-full rounded-lg border border-neutral-300 bg-white p-3 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
								rows="4"
								bind:value={editorDescription}
							></textarea>
						</div>

						<div class="mt-5">
							<label for="location" class="mb-1 block text-sm font-medium text-neutral-700"
								>Branch</label
							>
							<select
								id="location"
								disabled={selectedLog && !isEditMode}
								class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
								bind:value={editorLocation}
							>
								<option value="">Select</option>
								{#each branches as b (b.id)}
									<option value={b.branch_name}>{b.branch_name}</option>
								{/each}
							</select>
						</div>
					</div>

					<!-- Right Column: Info Box -->
					<div class="col-span-4">
						<div class="rounded-lg border border-neutral-200 bg-neutral-50 p-5">
							{#if selectedLog}
								<div class="mb-4">
									<div class="text-xs font-semibold text-neutral-600">Date Created:</div>
									<div class="text-sm text-neutral-800">
										{selectedLog?.created_at
											? new Date(selectedLog.created_at).toLocaleTimeString([], {
													hour: '2-digit',
													minute: '2-digit',
													hour12: true,
													timeZone: 'Asia/Manila'
												})
											: '—'}
									</div>
								</div>
								{#if selectedLog.status === 'Approved'}
									<div>
										<div class="text-xs font-semibold text-neutral-600">Approved by</div>
										<div class="text-sm text-neutral-800">Manager Name</div>
										<div class="text-xs text-neutral-600">
											{new Date(selectedLog.updated_at).toLocaleString()}
										</div>
									</div>
								{:else}
									<div>
										<div class="text-xs font-semibold text-neutral-600">For Approval of:</div>
										<div class="text-sm text-neutral-800">{managerName()}</div>
										<div class="text-xs text-neutral-600">Project Manager</div>
									</div>
								{/if}
							{:else}
								<div class="text-sm text-neutral-600">Fill in the details and click Create</div>
							{/if}
							{#if editorType === 'leave'}
								<div class="mt-4 border-t border-neutral-200 pt-3">
									<div class="text-xs font-semibold text-neutral-600">Leave Credits</div>
									{#if leaveCredits}
										<div class="mt-1 text-sm text-neutral-800">
											<div>
												Sick:
												<span class={leaveCreditColorClass(leaveCredits.sick_leave_balance)}>
													{formatLeaveCreditValue(leaveCredits.sick_leave_balance)}
												</span>
												{#if editorTaskTypeId}
													{@const isSick = taskTypes
														.find((t) => t.id === editorTaskTypeId)
														?.name.toLowerCase()
														.includes('sick')}
													{#if isSick}
														→ {formatLeaveCreditValue(leaveCredits.sick_leave_balance - 1)}
													{/if}
												{/if}
											</div>
											<div>
												Vacation:
												<span class={leaveCreditColorClass(leaveCredits.vacation_leave_balance)}>
													{formatLeaveCreditValue(leaveCredits.vacation_leave_balance)}
												</span>
												{#if editorTaskTypeId}
													{@const isVacation = taskTypes
														.find((t) => t.id === editorTaskTypeId)
														?.name.toLowerCase()
														.includes('vacation')}
													{#if isVacation}
														→ {formatLeaveCreditValue(leaveCredits.vacation_leave_balance - 1)}
													{/if}
												{/if}
											</div>
										</div>
									{:else if leaveCreditsError}
										<div class="mt-1 text-xs text-red-600">{leaveCreditsError}</div>
									{:else}
										<div class="mt-1 text-xs text-neutral-500">Loading leave credits...</div>
									{/if}
								</div>
							{/if}
						</div>
					</div>
				</div>

				<!-- Duplicate Panel (shown when duplicate button is clicked) -->
				{#if showDuplicatePanel && selectedLog && !isEditMode && selectedLog.status !== 'Approved'}
					<div class="mt-6 border-t pt-6">
						<div class="mt-4 rounded-lg border border-neutral-200 bg-neutral-50 p-5">
							<div class="mb-4">
								<h3 class="mb-2 text-sm font-semibold text-neutral-700">Duplicate This Timelog</h3>
								<p class="mb-4 text-xs text-neutral-600">
									Select how many days to duplicate this timelog. It will be duplicated starting
									from the next day.
								</p>
							</div>

							<!-- Simple days count with +/- buttons -->
							<div class="mb-4 grid grid-cols-12 items-center gap-3">
								<div class="col-span-4 text-sm font-semibold text-neutral-700">Number of Days</div>
								<div class="col-span-8">
									<div class="flex items-center gap-2">
										<button
											type="button"
											on:click={() => (duplicateDaysCount = Math.max(1, duplicateDaysCount - 1))}
											class="rounded-lg bg-gray-200 px-3 py-1 text-lg font-semibold hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600"
										>
											−
										</button>
										{#if isEditingDaysCount}
											<input
												type="number"
												min="1"
												max="6"
												inputmode="numeric"
												bind:value={duplicateDaysCount}
												on:input={() => {
													duplicateDaysCount = Math.max(1, Math.min(6, duplicateDaysCount));
												}}
												on:blur={() => {
													isEditingDaysCount = false;
													duplicateDaysCount = Math.max(1, Math.min(6, duplicateDaysCount));
												}}
												on:keydown={(e) => {
													if (e.key === 'Enter') {
														isEditingDaysCount = false;
														duplicateDaysCount = Math.max(1, Math.min(6, duplicateDaysCount));
													}
												}}
												class="w-12 rounded-lg border border-blue-400 bg-blue-50 p-1 text-center text-sm font-semibold dark:border-blue-600 dark:bg-blue-900"
											/>
										{:else}
											<button
												type="button"
												on:click={() => (isEditingDaysCount = true)}
												on:keydown={(e) => {
													if (e.key === 'Enter' || e.key === ' ') {
														e.preventDefault();
														isEditingDaysCount = true;
													}
												}}
												class="w-12 cursor-pointer rounded-lg px-2 py-1 text-center text-sm font-semibold transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
												title="Click to edit number of days"
											>
												{duplicateDaysCount}
											</button>
										{/if}
										<button
											type="button"
											on:click={() => (duplicateDaysCount = Math.min(6, duplicateDaysCount + 1))}
											class="rounded-lg bg-gray-200 px-3 py-1 text-lg font-semibold hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600"
										>
											+
										</button>
									</div>
									<p class="mt-1 text-xs text-neutral-500">
										{#if selectedLog}
											{@const originalDate = parseISOasLocal(selectedLog.start_time)}
											{@const nextDay = new Date(
												originalDate.getFullYear(),
												originalDate.getMonth(),
												originalDate.getDate() + 1
											)}
											Will duplicate to {duplicateDaysCount} day{duplicateDaysCount !== 1
												? 's'
												: ''} starting from {nextDay.toLocaleDateString('en-US', {
												weekday: 'long',
												month: 'short',
												day: 'numeric'
											})}
										{/if}
									</p>
								</div>
							</div>

							<!-- Advanced options (collapsed by default) -->
							<details class="mt-4">
								<summary class="mb-3 cursor-pointer text-sm font-semibold text-neutral-700"
									>Advanced Options</summary
								>
								<div class="mt-3 grid grid-cols-12 gap-4">
									<!-- Left column: Frequency options -->
									<div class="col-span-5">
										<fieldset>
											<legend class="mb-3 block text-sm font-semibold text-neutral-700"
												>Frequency</legend
											>
											<div class="space-y-3">
												<label class="flex items-center gap-2">
													<input
														type="radio"
														bind:group={duplicateFrequency}
														value="daily-no-weekends"
														class="h-4 w-4"
													/>
													<span class="text-sm text-neutral-700">Daily except weekends</span>
												</label>
												<label class="flex items-center gap-2">
													<input
														type="radio"
														bind:group={duplicateFrequency}
														value="daily-weekends"
														class="h-4 w-4"
													/>
													<span class="text-sm text-neutral-700">Daily including weekends</span>
												</label>
												<label class="flex items-center gap-2">
													<input
														type="radio"
														bind:group={duplicateFrequency}
														value="weekly"
														class="h-4 w-4"
													/>
													<span class="text-sm text-neutral-700">Weekly, every</span>
													{#if duplicateFrequency === 'weekly'}
														<select
															bind:value={duplicateCustomDay}
															class="ml-2 rounded border p-1 text-sm"
														>
															<option value="Monday">Monday</option>
															<option value="Tuesday">Tuesday</option>
															<option value="Wednesday">Wednesday</option>
															<option value="Thursday">Thursday</option>
															<option value="Friday">Friday</option>
															<option value="Saturday">Saturday</option>
															<option value="Sunday">Sunday</option>
														</select>
													{/if}
												</label>
											</div>
										</fieldset>
									</div>

									<!-- Right column: Start / End dates -->
									<div class="col-span-7">
										<div class="grid grid-cols-12 items-center gap-3">
											<div class="col-span-4 text-sm font-semibold text-neutral-700">
												Start Date
											</div>
											<div class="col-span-8">
												<input
													id="dup-start"
													type="date"
													class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm"
													bind:value={duplicateStartDate}
												/>
											</div>

											<div class="col-span-4 text-sm font-semibold text-neutral-700">End Date</div>
											<div class="col-span-8">
												<input
													id="dup-end"
													type="date"
													class="w-full rounded-lg border border-neutral-300 bg-white p-2 text-sm"
													bind:value={duplicateEndDate}
													disabled={duplicateDaysMode === 'days-count'}
												/>
											</div>
										</div>
									</div>
								</div>
							</details>

							<!-- Action Buttons -->
							<div class="mt-5 flex justify-end gap-2">
								<button
									class="rounded-md bg-neutral-500 px-4 py-2 text-sm text-white hover:bg-neutral-600"
									on:click={() => (showDuplicatePanel = false)}
								>
									Cancel Duplicate
								</button>
								<button
									class="rounded-md bg-green-500 px-4 py-2 text-sm text-white hover:bg-green-600"
									on:click={duplicateSelectedLog}
									disabled={!duplicateStartDate}
								>
									Duplicate
								</button>
							</div>
						</div>
					</div>
				{/if}
				<!-- Bottom Action Buttons -->
				<div class="mt-8 flex justify-end gap-2 border-t pt-6">
					<button
						class="rounded-md bg-neutral-700 px-4 py-2 text-sm text-white hover:bg-neutral-800"
						on:click={cancelEditor}
					>
						Cancel
					</button>
					{#if selectedLog}
						{#if !isEditMode}
							{#if selectedLog.status === 'Approved'}
								<!-- Approved tasks cannot be deleted or edited -->
							{:else}
								<!-- Approve/Reject buttons for project managers on team members' tasks -->
								{#if canManageTasks && selectedLog.user_id !== currentUserId && selectedLog.status !== 'Rejected'}
									<button
										class="rounded-md bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700"
										on:click={approveTask}
									>
										✓ Approve
									</button>
									<button
										class="rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
										on:click={rejectTask}
									>
										✗ Reject
									</button>
								{/if}
								<button
									class="rounded-md bg-blue-500 px-4 py-2 text-sm text-white hover:bg-blue-600"
									on:click={() => (isEditMode = true)}
								>
									Edit
								</button>
								<button
									class="rounded-md bg-green-500 px-4 py-2 text-sm text-white hover:bg-green-600"
									on:click={() => (showDuplicatePanel = !showDuplicatePanel)}
								>
									Duplicate
								</button>
								<button
									class="rounded-md bg-red-500 px-4 py-2 text-sm text-white hover:bg-red-600"
									on:click={promptDeleteSelectedLog}
								>
									Delete
								</button>
							{/if}
						{:else}
							<button
								class="rounded-md bg-orange-500 px-4 py-2 text-sm text-white hover:bg-orange-600"
								on:click={createEntry}
							>
								Save
							</button>
						{/if}
					{:else}
						<button
							class="rounded-md bg-orange-500 px-4 py-2 text-sm text-white hover:bg-orange-600"
							on:click={createEntry}
						>
							Create
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
</div>

<ConfirmModal
	open={deleteLogOpen}
	title="Delete Timelog"
	message={deleteLogMessage}
	confirmText="Delete"
	cancelText="Cancel"
	on:confirm={performDeleteSelectedLog}
/>

<ErrorModal
	open={showDateValidationError}
	title="Navigation Error"
	message={dateValidationError || ''}
	on:close={() => (showDateValidationError = false)}
/>

<style>
	button {
		cursor: pointer;
	}
</style>
