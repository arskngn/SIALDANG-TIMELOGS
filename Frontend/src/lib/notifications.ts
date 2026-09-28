import { writable, derived } from 'svelte/store';
import { userId, isAuthenticated } from './stores';
import api from './api';

export type NotificationType = 'timelog' | 'leave' | 'user201' | 'project' | 'generic';
export type NotificationAction = 'approved' | 'rejected' | 'created' | 'declined';

export interface NotificationItem {
	id: string;
	title: string;
	message: string;
	type: NotificationType;
	created_at: string;
	read: boolean;
	// Facebook-style notification data
	approver_id?: number;
	approver_name?: string;
	approver_avatar?: string;
	action?: NotificationAction;
	target_route?: string; // Route to navigate to when clicked (e.g., '/approval')
	target_item_id?: number; // ID of timelog or 201 file
}

function uid() {
	return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

const notifications = writable<NotificationItem[]>([]);
const unreadCount = derived(notifications, (list) => list.filter((n) => !n.read).length);
const currentToast = writable<NotificationItem | null>(null);
let _prevUserId: number | null = null;
userId.subscribe((v) => {
	if (_prevUserId !== v) {
		notifications.set([]);
		currentToast.set(null);
		_prevUserId = v;
	}
});
isAuthenticated.subscribe((authed) => {
	if (!authed) {
		notifications.set([]);
		currentToast.set(null);
	}
});

function addNotification(payload: {
	id?: string;
	title: string;
	message: string;
	type?: NotificationType;
	approver_id?: number;
	approver_name?: string;
	approver_avatar?: string;
	action?: NotificationAction;
	target_route?: string;
	target_item_id?: number;
	read?: boolean;
	skipToast?: boolean; // Skip showing as a popup toast
}) {
	const item: NotificationItem = {
		id: payload.id || uid(),
		title: payload.title,
		message: payload.message,
		type: payload.type || 'generic',
		created_at: new Date().toISOString(),
		read: payload.read || false,
		approver_id: payload.approver_id,
		approver_name: payload.approver_name,
		approver_avatar: payload.approver_avatar,
		action: payload.action,
		target_route: payload.target_route,
		target_item_id: payload.target_item_id
	};
	notifications.update((list) => [item, ...list].slice(0, 200));
	if (!payload.read && !payload.skipToast) {
		currentToast.set(item);
	}
	return item;
}

async function markNotificationRead(id: string) {
	// Update frontend immediately
	notifications.update((list) => list.map((n) => (n.id === id ? { ...n, read: true } : n)));

	// Update backend if id is numeric (from database)
	if (!isNaN(Number(id))) {
		try {
			await api.notificationAPI.markAsRead(Number(id));
		} catch (e) {
			console.error(`Failed to mark notification ${id} as read on backend:`, e);
		}
	}
}

async function markAllAsRead() {
	// Get current notifications
	let currentNotifications: NotificationItem[] = [];
	const unsub = notifications.subscribe((n) => {
		currentNotifications = n;
	});
	unsub();

	// Update frontend immediately
	notifications.update((list) => list.map((n) => ({ ...n, read: true })));

	// Mark all unread notifications on backend
	const unreadIds = currentNotifications
		.filter((n) => !n.read && !isNaN(Number(n.id)))
		.map((n) => Number(n.id));
	for (const id of unreadIds) {
		try {
			await api.notificationAPI.markAsRead(id);
		} catch (e) {
			console.error(`Failed to mark notification ${id} as read on backend:`, e);
		}
	}
}

async function clearAllNotifications() {
	let currentNotifications: NotificationItem[] = [];
	const unsub = notifications.subscribe((n) => {
		currentNotifications = n;
	});
	unsub();

	notifications.set([]);

	const numericIds = currentNotifications
		.filter((n) => !isNaN(Number(n.id)))
		.map((n) => Number(n.id));
	for (const id of numericIds) {
		try {
			await api.notificationAPI.deleteNotification(id);
		} catch (e) {
			console.error(`Failed to delete notification ${id}:`, e);
		}
	}
}

function removeNotification(id: string) {
	// Remove from frontend immediately
	notifications.update((list) => list.filter((n) => n.id !== id));

	// Delete from backend if id is numeric (from database)
	if (!isNaN(Number(id))) {
		try {
			api.notificationAPI.deleteNotification(Number(id));
		} catch (e) {
			console.error(`Failed to delete notification ${id}:`, e);
		}
	}
}

export {
	notifications,
	unreadCount,
	currentToast,
	addNotification,
	markNotificationRead,
	markAllAsRead,
	removeNotification,
	clearAllNotifications
};
