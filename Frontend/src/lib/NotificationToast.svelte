<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount, onDestroy } from 'svelte';
	import Icon from '@iconify/svelte';
	import { removeNotification, currentToast } from '$lib/notifications';
	import type { NotificationItem } from '$lib/notifications';

	export let notification: NotificationItem;

	let isVisible = true;

	function handleClose() {
		if (dismissTimer) {
			clearTimeout(dismissTimer);
			dismissTimer = null;
		}
		isVisible = false;
		setTimeout(() => {
			currentToast.set(null);
		}, 300);
	}

	function handleClick() {
		if (notification.target_route) {
			goto(notification.target_route as any);
		}
	}

	let dismissTimer: any = null;
	onMount(() => {
		dismissTimer = setTimeout(() => {
			handleClose();
		}, 5000);
	});
	onDestroy(() => {
		if (dismissTimer) {
			clearTimeout(dismissTimer);
			dismissTimer = null;
		}
	});

	// Facebook-style notification styling
	const bgColor =
		notification.type === 'leave'
			? 'bg-blue-50 border-blue-200 dark:bg-blue-900 dark:border-blue-700'
			: notification.type === 'user201'
				? 'bg-purple-50 border-purple-200 dark:bg-purple-900 dark:border-purple-700'
				: 'bg-green-50 border-green-200 dark:bg-green-900 dark:border-green-700';

	const iconColor =
		notification.type === 'leave'
			? 'text-blue-600 dark:text-blue-300'
			: notification.type === 'user201'
				? 'text-purple-600 dark:text-purple-300'
				: 'text-green-600 dark:text-green-300';

	const textColor = 'text-gray-900 dark:text-white';
	const actionColor =
		notification.action === 'approved'
			? 'text-green-600 dark:text-green-300'
			: notification.action === 'rejected' || notification.action === 'declined'
				? 'text-red-600 dark:text-red-300'
				: 'text-blue-600 dark:text-blue-300';
</script>

{#if isVisible}
	<div class="group mb-3 transform transition-all duration-300 ease-out">
		<!-- Facebook-style notification card -->
		<div
			class="flex items-start gap-3 rounded-lg border {bgColor} p-4 shadow-md transition-shadow hover:shadow-lg {notification.target_route
				? 'cursor-pointer'
				: ''}"
			on:click={handleClick}
			on:keydown={(e) => e.key === 'Enter' && handleClick()}
			role="button"
			tabindex="0"
		>
			<!-- Left: Type Icon -->
			<div class="shrink-0">
				{#if notification.type === 'timelog' || notification.type === 'leave'}
					<Icon icon="mdi:clock-outline" class={`text-2xl ${iconColor}`} />
				{:else if notification.type === 'user201'}
					<Icon icon="mdi:file-document-outline" class={`text-2xl ${iconColor}`} />
				{:else if notification.type === 'project'}
					<Icon icon="mdi:folder-outline" class={`text-2xl ${iconColor}`} />
				{:else}
					<Icon icon="mdi:bell-outline" class={`text-2xl ${iconColor}`} />
				{/if}
			</div>

			<!-- Center: Notification content -->
			<div class="grow">
				<!-- Approver info (if available) -->
				{#if notification.approver_name}
					<div class="mb-1 flex items-center gap-2">
						{#if notification.approver_avatar}
							<img
								src={notification.approver_avatar}
								alt={notification.approver_name}
								class="h-6 w-6 rounded-full"
							/>
						{:else}
							<Icon icon="mdi:account-circle" class="text-xl text-gray-400" />
						{/if}
						<span class="font-semibold {textColor}">{notification.approver_name}</span>
						<span class="text-sm text-gray-600 dark:text-gray-400">
							{#if notification.action === 'approved'}
								approved
							{:else if notification.action === 'rejected'}
								rejected
							{:else if notification.action === 'declined'}
								declined
							{:else}
								updated
							{/if}
						</span>
					</div>
				{/if}

				<!-- Title -->
				<div class="font-semibold {textColor} mb-1">
					{notification.title}
				</div>

				<!-- Message/Description -->
				<div class="text-sm text-gray-700 dark:text-gray-300">
					{notification.message}
				</div>

				<!-- Timestamp -->
				<div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
					{new Date(notification.created_at).toLocaleTimeString([], {
						hour: '2-digit',
						minute: '2-digit'
					})}
				</div>
			</div>

			<!-- Right: Close button + arrow (if clickable) -->
			<div class="flex shrink-0 gap-1">
				{#if notification.target_route}
					<div
						class="p-1 text-gray-500 opacity-0 transition-colors group-hover:opacity-100 hover:text-blue-600 dark:hover:text-blue-300"
						title="Go to details"
					>
						<Icon icon="mdi:arrow-right" class="text-lg" />
					</div>
				{/if}
				<button
					type="button"
					class="p-1 text-gray-400 transition-colors hover:text-gray-600 dark:hover:text-gray-300"
					on:click|stopPropagation={handleClose}
					title="Dismiss"
				>
					<Icon icon="mdi:close" class="text-lg" />
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	:global(.notification-enter) {
		animation: slideIn 0.3s ease-out;
	}

	@keyframes slideIn {
		from {
			transform: translateX(400px);
			opacity: 0;
		}
		to {
			transform: translateX(0);
			opacity: 1;
		}
	}
</style>
