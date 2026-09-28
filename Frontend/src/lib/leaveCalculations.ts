import type { TimelogResponse, TaskTypeResponse, UserResponse } from '$lib/api';

export interface LeaveSummary {
	typeId: number;
	typeName: string;
	earned: number;
	awarded: number;
	spent: number;
	earnedBalance: number;
	remaining: number;
	items: TimelogResponse[];
	isOpen: boolean;
}

const LEAVE_CREDIT_PER_TYPE_PER_YEAR = 12;

/**
 * Days earned "to date" for targetYear: one per full month elapsed since
 * the later of (contract start, Jan 1 of targetYear), capped at the current
 * month if targetYear is this year, or at contract end / Dec if earlier.
 * Capped at 12 (can't earn more than a year's worth of one leave type).
 */
export function calculateEarnedDays(user: UserResponse, targetYear: number): number {
	if (!user.emp_start_date) return 0;

	const now = new Date();
	const startDate = new Date(user.emp_start_date);
	const endDate = user.emp_end_date ? new Date(user.emp_end_date) : null;

	const yearStart = new Date(targetYear, 0, 1);
	const yearEnd = new Date(targetYear, 11, 31);

	if (endDate && endDate < yearStart) return 0;
	if (startDate > yearEnd) return 0;

	const actualStart = new Date(Math.max(startDate.getTime(), yearStart.getTime()));
	let actualEnd = endDate
		? new Date(Math.min(endDate.getTime(), yearEnd.getTime()))
		: new Date(yearEnd);

	if (targetYear === now.getFullYear() && actualEnd > now) {
		actualEnd = now;
	}

	let months = 0;
	const cursor = new Date(actualStart.getFullYear(), actualStart.getMonth(), 1);
	const endOfMonth = new Date(actualEnd.getFullYear(), actualEnd.getMonth() + 1, 0);

	while (cursor <= endOfMonth) {
		months++;
		cursor.setMonth(cursor.getMonth() + 1);
	}

	return Math.min(LEAVE_CREDIT_PER_TYPE_PER_YEAR, Math.max(0, months));
}

/**
 * Total days that WILL be earned for targetYear if the contract runs its
 * course — same as calculateEarnedDays but not capped at "today".
 */
export function calculateAwardedDays(user: UserResponse, targetYear: number): number {
	if (!user.emp_start_date) return 0;

	const startDate = new Date(user.emp_start_date);
	const endDate = user.emp_end_date ? new Date(user.emp_end_date) : null;

	const yearStart = new Date(targetYear, 0, 1);
	const yearEnd = new Date(targetYear, 11, 31);

	if (endDate && endDate < yearStart) return 0;
	if (startDate > yearEnd) return 0;

	const actualStart = new Date(Math.max(startDate.getTime(), yearStart.getTime()));
	const actualEnd = endDate
		? new Date(Math.min(endDate.getTime(), yearEnd.getTime()))
		: new Date(yearEnd);

	let months = 0;
	const cursor = new Date(actualStart.getFullYear(), actualStart.getMonth(), 1);
	const endOfMonth = new Date(actualEnd.getFullYear(), actualEnd.getMonth() + 1, 0);

	while (cursor <= endOfMonth) {
		months++;
		cursor.setMonth(cursor.getMonth() + 1);
	}

	return Math.min(LEAVE_CREDIT_PER_TYPE_PER_YEAR, Math.max(0, months));
}

function dayKey(dateStr: string): string {
	const d = new Date(dateStr);
	return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

/**
 * A day counts as "spent" for a leave type if there's at least one Approved
 * leave timelog of that type on that day. Duration and log count don't matter;
 * multiple same-day logs of the same type still count once.
 */
function countSpentDays(items: TimelogResponse[]): number {
	const days = new Set<string>();
	for (const item of items) {
		if (item.status !== 'Approved') continue;
		days.add(dayKey(item.start_time));
	}
	return days.size;
}

export function computeLeaveSummary(
	user: UserResponse,
	timelogs: TimelogResponse[],
	taskTypes: TaskTypeResponse[],
	targetYear: number
): LeaveSummary[] {
	const leaveTypes = taskTypes.filter(
		(t) =>
			t.category === 'leave' &&
			t.name !== 'holidays' &&
			t.name !== 'absent without office leave'
	);

	const relevantLogs = timelogs.filter((l) => {
		if (l.type !== 'leave') return false;
		return new Date(l.start_time).getFullYear() === targetYear;
	});

	const earned = calculateEarnedDays(user, targetYear);
	const awarded = calculateAwardedDays(user, targetYear);

	return leaveTypes.map((lt) => {
		const items = relevantLogs
			.filter((l) => l.task_type_id === lt.id)
			.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

		const spent = countSpentDays(items);

		return {
			typeId: lt.id,
			typeName: lt.name,
			earned,
			awarded,
			spent,
			earnedBalance: earned - spent,
			remaining: awarded - spent,
			items,
			isOpen: items.length > 0
		};
	});
}