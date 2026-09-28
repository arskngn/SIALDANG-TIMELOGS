<script lang="ts">
	import {
		notifications,
		unreadCount,
		markAllAsRead,
		markNotificationRead,
		clearAllNotifications
	} from '$lib/notifications';
	import Icon from '@iconify/svelte';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import api from '$lib/api';
	import { goto } from '$app/navigation';

	let dbNotifications: any[] = [];
	let loading = true;
	let error = '';

	onMount(async () => {
		try {
			const response = await api.notificationAPI.getNotifications();
			dbNotifications = response.notifications || [];
		} catch (err) {
			error = 'Failed to load notifications';
			console.error(err);
		} finally {
			loading = false;
		}
	});

	async function markDbNotificationAsRead(notificationId: number) {
		try {
			await api.notificationAPI.markAsRead(notificationId);
			// Update the local array
			dbNotifications = dbNotifications.map((n) =>
				n.id === notificationId ? { ...n, is_read: 1 } : n
			);
		} catch (err) {
			console.error('Failed to mark notification as read:', err);
		}
	}

	// Combine in-memory notifications and database notifications
	$: allNotifications = [...$notifications, ...dbNotifications].sort((a, b) => {
		const timeA = new Date(a.created_at).getTime();
		const timeB = new Date(b.created_at).getTime();
		return timeB - timeA;
	});
</script>

<div class="container mx-auto px-4 py-6">
	<div class="mb-4 flex items-center justify-between">
		<h1 class="text-3xl font-bold dark:text-white">Notifications</h1>
		<div class="flex items-center gap-2">
			<div
				class="rounded bg-blue-50 px-3 py-1.5 text-sm text-blue-700 dark:bg-gray-700 dark:text-blue-300"
			>
				Unread: {$unreadCount + (dbNotifications.filter((n) => !n.is_read).length || 0)}
			</div>
			<button
				class="rounded px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-gray-300 dark:hover:bg-gray-700"
				on:click={markAllAsRead}
			>
				Mark all as read
			</button>
			<button
				class="rounded px-3 py-1.5 text-sm text-red-600 hover:bg-neutral-100 dark:text-red-400 dark:hover:bg-gray-700"
				on:click={async () => {
					try {
						const ids = dbNotifications.map((n) => n.id).filter((id) => typeof id === 'number');
						for (const id of ids) {
							try {
								await api.notificationAPI.deleteNotification(id);
							} catch (err) {
								console.error('Failed to delete notification', id, err);
							}
						}
						dbNotifications = [];
						clearAllNotifications();
					} catch (err) {
						console.error('Failed to delete all notifications:', err);
					}
				}}
			>
				Delete all
			</button>
			<a
				class="rounded px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-gray-300 dark:hover:bg-gray-700"
				href={resolve('/')}
			>
				Back
			</a>
		</div>
	</div>
	{#if loading}
		<div
			class="rounded border border-neutral-200 bg-white p-6 text-center text-neutral-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
		>
			Loading notifications...
		</div>
	{:else if error}
		<div
			class="rounded border border-red-200 bg-red-50 p-6 text-center text-red-600 dark:border-red-700 dark:bg-red-900 dark:text-red-300"
		>
			{error}
		</div>
	{:else if allNotifications.length === 0}
		<div
			class="rounded border border-neutral-200 bg-white p-6 text-center text-neutral-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
		>
			No notifications
		</div>
	{:else}
		<ul class="space-y-2">
			{#each allNotifications as n (n.id)}
				<li
					class="rounded border border-neutral-200 bg-white dark:border-gray-700 dark:bg-gray-800"
				>
					<button
						type="button"
						class="flex w-full cursor-pointer items-start gap-3 px-3 py-3 text-left hover:bg-neutral-50 dark:hover:bg-gray-700"
						on:click={() => {
							const route = (n.target_route as any) || '/tasks';
							goto(route);
							if (typeof n.id === 'number' || !isNaN(Number(n.id))) {
								markDbNotificationAsRead(Number(n.id));
							} else {
								markNotificationRead(String(n.id));
							}
						}}
						on:keydown={(e) => {
							if (e.key === 'Enter' || e.key === ' ') {
								const route = (n.target_route as any) || '/tasks';
								goto(route);
							}
						}}
					>
						<div class="mt-0.5 shrink-0">
							{#if n.approver_avatar}
								<img
									src={n.approver_avatar}
									alt={n.approver_name || 'Approver'}
									class="h-6 w-6 rounded-full object-cover"
								/>
							{:else}
								<div
									class="flex h-6 w-6 items-center justify-center rounded-full bg-gray-300 dark:bg-gray-600"
								>
									<Icon icon="mdi:account" class="h-4 w-4 text-gray-600 dark:text-gray-300" />
								</div>
							{/if}
						</div>
						<div class="flex-1">
							<div class="flex items-center justify-between">
								<div class="text-sm font-semibold text-neutral-900 dark:text-white">
									{n.item_title || n.title || 'Notification'}
								</div>
								<div class="text-xs text-neutral-500 dark:text-gray-400">
									{new Date(n.created_at).toLocaleString()}
								</div>
							</div>
							<div class="mt-1 text-sm text-neutral-700 dark:text-gray-300">
								{n.approver_name}
								{n.action} your {n.item_type}
							</div>
							<div class="mt-1 text-xs text-neutral-600 dark:text-gray-400">
								{n.item_description}
							</div>
							{#if (n.read === false || n.is_read === 0) && !n.read}
								<div
									class="mt-2 rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-gray-700"
									on:click|stopPropagation={() =>
										n.id < 1000000 ? markDbNotificationAsRead(n.id) : markNotificationRead(n.id)}
									on:keydown|stopPropagation={(e) => {
										if (e.key === 'Enter' || e.key === ' ') {
											n.id < 1000000 ? markDbNotificationAsRead(n.id) : markNotificationRead(n.id);
										}
									}}
									tabindex="0"
									role="button"
								>
									Mark as read
								</div>
							{/if}
						</div>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>
