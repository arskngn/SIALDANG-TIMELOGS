<script lang="ts">
	import '../app.css';
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';
	import { isAuthenticated, userRole, username, logout, userId } from '$lib/stores';
	import api, { userAPI } from '$lib/api';
	import Avatar from '$lib/Avatar.svelte';
	import Icon from '@iconify/svelte';
	import ConfirmModal from '$lib/ConfirmModal.svelte';
	import NotificationToast from '$lib/NotificationToast.svelte';
	import {
		unreadCount,
		notifications,
		currentToast,
		addNotification,
		markAllAsRead,
		markNotificationRead,
		removeNotification,
		clearAllNotifications
	} from '$lib/notifications';

	let darkMode = false;
	let userFirstName = '';
	let userLastName = '';
	let userAvatarUrl = '';
	let currentUserId: number | null = null;
	// Realtime clock
	let nowStr = '';
	let clockInterval: any = null;
	let autoRefreshInterval: any = null;
	const autoRefreshMs = 3000000;
	// Track route changes
	let routeKey = '';

	onMount(() => {
		// Check for saved theme preference
		const theme = localStorage.getItem('theme');
		if (theme === 'dark' || (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
			darkMode = true;
			document.documentElement.classList.add('dark');
		} else {
			darkMode = false;
			document.documentElement.classList.remove('dark');
		}

		// Start realtime clock (local time)
		const updateClock = () => {
			nowStr = new Date().toLocaleTimeString([], {
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit'
			});
		};
		updateClock();
		clockInterval = setInterval(updateClock, 1000);
		autoRefreshInterval = setInterval(() => {
			if (document.visibilityState === 'visible') {
				goto($page.url.pathname, { replaceState: true });
			}
		}, autoRefreshMs);
		// Ensure notifications polling starts even if userId doesn't change
		if (authenticated) {
			startGlobalNotificationsPolling();
		}
	});

	function toggleDarkMode() {
		darkMode = !darkMode;
		if (darkMode) {
			document.documentElement.classList.add('dark');
			localStorage.setItem('theme', 'dark');
		} else {
			document.documentElement.classList.remove('dark');
			localStorage.setItem('theme', 'light');
		}
	}

	async function clearCaches() {
		try {
			if ('caches' in window) {
				const keys = await caches.keys();
				for (const k of keys) await caches.delete(k);
			}
		} catch {}
	}
	let authenticated = false;
	let role = '';
	let user = '';
	let showAdminDropdown = false;
	let showMyWorksDropdown = false;
	let showUserProfileDropdown = false;
	let canApprove = false;
	let hasManagedProjects = false;
	let showNotificationsModal = false;
	let notifTab: 'All' | 'Unread' = 'All';
	let openMenuId: string | null = null;
	let toastItem: any = null;
	$: $currentToast && (toastItem = $currentToast);
	let fatalError: string | null = null;
	// Global notifications polling
	let notifInterval: any = null;
	let lastCheckedTime = 0;

	const unsubAuth = isAuthenticated.subscribe((v) => (authenticated = v));
	const unsubRole = userRole.subscribe((v) => (role = v));
	const unsubUser = username.subscribe((v) => (user = v));
	const unsubUserId = userId.subscribe((v) => {
		currentUserId = v;
		// Fetch user profile when userId changes
		if (v) {
			userAPI
				.getMe()
				.then((profile) => {
					userFirstName = profile.first_name || '';
					userLastName = profile.last_name || '';
					userAvatarUrl = profile.profile_picture_url || '';
				})
				.catch(() => {
					// If fetch fails, keep using username
					userFirstName = '';
					userLastName = '';
					userAvatarUrl = '';
				});
			// Determine approval capability
			api.projectAPI
				.getMyManaged()
				.then((projects) => {
					hasManagedProjects = !!(projects && projects.length > 0);
				})
				.catch(() => {
					hasManagedProjects = false;
				});

			showNotificationsModal = false;
			showUserProfileDropdown = false;
			showAdminDropdown = false;
			showMyWorksDropdown = false;
			openMenuId = null;
			notifTab = 'All';
			// Kick off notifications polling globally so all pages receive updates
			startGlobalNotificationsPolling();
		}
	});

	onDestroy(() => {
		unsubAuth();
		unsubRole();
		unsubUser();
		unsubUserId();
		if (clockInterval) clearInterval(clockInterval);
		if (autoRefreshInterval) clearInterval(autoRefreshInterval);
		if (notifInterval) clearInterval(notifInterval);
	});

	onMount(() => {
		const onProfileUpdated = () => {
			if (currentUserId) {
				userAPI
					.getUser(currentUserId)
					.then((profile) => {
						userFirstName = profile.first_name || '';
						userLastName = profile.last_name || '';
						userAvatarUrl = profile.profile_picture_url || '';
					})
					.catch(() => void 0);
			}
		};
		window.addEventListener('profile-updated', onProfileUpdated);
		return () => window.removeEventListener('profile-updated', onProfileUpdated);
	});

	let showLogoutConfirm = false;
	function resetApp() {
		try {
			localStorage.removeItem('project_auth_v2');
		} catch {}
		clearCaches().finally(() => location.reload());
	}
	let _onErr: any = null;
	let _onRej: any = null;
	onMount(() => {
		_onErr = (e: ErrorEvent) => {
			const msg = e?.message ? String(e.message) : 'Unexpected error';
			fatalError = msg;
			if (
				/ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module|CSS chunk/i.test(
					msg
				)
			) {
				clearCaches().finally(() => location.reload());
			}
		};
		_onRej = (e: PromiseRejectionEvent) => {
			const r: any = e?.reason;
			const msg = r && (r.message || r.detail) ? String(r.message || r.detail) : 'Unexpected error';
			fatalError = msg;
			if (
				/ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module|CSS chunk/i.test(
					msg
				)
			) {
				clearCaches().finally(() => location.reload());
			}
		};
		window.addEventListener('error', _onErr);
		window.addEventListener('unhandledrejection', _onRej);
	});
	onDestroy(() => {
		if (_onErr) window.removeEventListener('error', _onErr);
		if (_onRej) window.removeEventListener('unhandledrejection', _onRej);
	});

	// Open confirmation modal for logout
	function doLogout() {
		showLogoutConfirm = true;
	}

	function confirmLogout() {
		logout();
		goto(resolve('/login'));
		showLogoutConfirm = false;
	}

	$: isAdmin = (role || '').toLowerCase() === 'admin';
	$: isManager = (role || '').toLowerCase() === 'manager';
	$: isUser = (role || '').toLowerCase() === 'user';
	$: canApprove = isAdmin || hasManagedProjects;
	$: if (!authenticated && $page.url.pathname !== '/login') {
		goto(resolve('/login'));
	}

	// Menu Items Configuration
	$: adminMenuItems = (() => {
		let items: { label: string; href: string; icon: string }[] = [];
		if (isAdmin) {
			items = [
				{ label: '201 Approvals', href: '/201-files', icon: 'mdi:file-document' },
				{ label: 'Set up', href: '/setup', icon: 'mdi:source-branch' },
				{ label: 'Projects', href: '/customers', icon: 'mdi:domain' },
				{ label: 'Detailed Timelogs', href: '/my-reports', icon: 'mdi:file-chart' },
				{ label: 'For Approval', href: '/approval', icon: 'mdi:check-circle' },
				{ label: 'Leaves', href: '/team-leaves', icon: 'mdi:clipboard-text' },
				{ label: 'Users', href: '/users', icon: 'mdi:account-group' }
			];
		} else if (isManager && hasManagedProjects) {
			items = [
				{ label: 'Projects', href: '/customers', icon: 'mdi:domain' },
				{ label: 'Leaves', href: '/team-leaves', icon: 'mdi:clipboard-text' },
				{ label: 'For Approval', href: '/approval', icon: 'mdi:check-circle' }
			];
		} else if (isManager) {
			items = [
				{ label: 'Projects', href: '/customers', icon: 'mdi:domain' },
				{ label: 'Leaves', href: '/team-leaves', icon: 'mdi:clipboard-text' }
			];
		}		
		return items.sort((a, b) => a.label.localeCompare(b.label));
	})();

	$: myWorksMenuItems = (() => {
		// Generate today's date in YYYY-MM-DD format for the calendar link
		const today = new Date();
		const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
		const items: { label: string; href: string; icon: string }[] = [
			{ label: 'My Task Calendar', href: `/tasks?weekStart=${todayStr}`, icon: 'mdi:calendar' },
			{ label: 'My Leaves', href: '/my-leaves', icon: 'mdi:clipboard-text' }
		];
		if (!isAdmin) {
			items.push({ label: 'My Timelogs Report', href: '/my-reports', icon: 'mdi:file-chart' });
		}
		return items;
	})();


	// Kick a lightweight refresh on route change to keep notifications in sync
	$: routeKey = `${$page.url.pathname}${$page.url.search}`;
	$: if (authenticated && routeKey) {
		fetchBackendNotifications();
	}

	// Global notifications fetching (moved from dashboard so all pages get notifications)
	async function fetchBackendNotifications() {
		try {
			const result = await api.notificationAPI.getNotifications();
			if (result.notifications && Array.isArray(result.notifications)) {
				for (const notif of result.notifications) {
					if (!$notifications.find((n) => n.id === String(notif.id))) {
						const routeFor201 = isAdmin ? '/201-files?status=Pending' : '/profile?tab=employment';
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
							read: notif.is_read === 1,
							skipToast: false
						});
					}
				}
			}
		} catch (e) {
			// Silent fail to avoid breaking layout
			console.warn('Global notifications fetch failed:', e);
		}
	}

	async function checkForStatusUpdates() {
		try {
			const result = await api.notificationAPI.getStatusUpdates();
			if (result.updates && result.updates.length > 0) {
				const now = Date.now();
				const recentUpdates = result.updates.filter((u: any) => {
					const updateTime = new Date(u.approved_at || 0).getTime();
					return updateTime > lastCheckedTime;
				});
				for (const update of recentUpdates) {
					addNotification({
						title: update.status === 'Approved' ? 'Timelog Approved' : 'Timelog Rejected',
						message: update.description || `${update.type} entry · ${update.status}`,
						type: update.type === 'leave' ? 'leave' : 'timelog',
						action: update.status === 'Approved' ? 'approved' : 'rejected',
						target_route: update.type === 'leave' ? '/approval' : '/tasks',
						read: false
					});
				}
				lastCheckedTime = now;
			}
		} catch (e) {
			// User may not have permission for status updates
			//trigger
		}
	}

	function startGlobalNotificationsPolling() {
		if (!authenticated) return;
		// Clear any previous interval
		if (notifInterval) clearInterval(notifInterval);
		// Run immediately then every 30 seconds while visible
		fetchBackendNotifications();
		checkForStatusUpdates();
		notifInterval = setInterval(() => {
			if (document.visibilityState === 'visible') {
				fetchBackendNotifications();
				checkForStatusUpdates();
			}
		}, 30000);
	}
</script>

<svelte:head>
	<title>Timelogs</title>
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<link rel="icon" href="/favicon.png" type="image/png" />
	<script>
		// Initialize dark mode on page load
		const theme = localStorage.getItem('theme');
		if (theme === 'dark' || (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
			document.documentElement.classList.add('dark');
		}
	</script>
</svelte:head>

{#if fatalError}
	<div
		class="fixed inset-0 z-[100] flex items-center justify-center p-4"
		style="background: rgba(0,0,0,0.1); backdrop-filter: blur(2px);"
	>
		<div class="w-full max-w-md rounded-lg bg-white p-6 shadow-lg dark:bg-gray-800">
			<h2 class="mb-3 text-xl font-bold dark:text-white">An error occurred</h2>
			<p class="mb-5 text-sm text-gray-700 dark:text-gray-300">{fatalError}</p>
			<div class="flex gap-3">
				<button
					class="flex-1 rounded bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
					on:click={() => location.reload()}>Reload</button
				>
				<button
					class="flex-1 rounded bg-gray-600 px-4 py-2 font-medium text-white hover:bg-gray-700"
					on:click={resetApp}>Clear Session</button
				>
			</div>
		</div>
	</div>
{/if}

<!-- Simple top navigation with auth awareness (hidden on /login) -->

{#if $page.url.pathname !== '/login'}
	<header class="border-b border-gray-200 bg-white shadow dark:border-transparent dark:bg-gray-800">
		<div class="container mx-auto flex items-center justify-between px-4 py-3">
			<div class="flex items-center space-x-4">
				<a href={resolve('/')} class="flex items-center text-xl font-semibold dark:text-white">
					<Icon icon="mdi:view-dashboard" class="mr-2 h-6 w-6" />
					Timelogs
				</a>
				{#if authenticated}
					<!-- My Works dropdown - accessible to all authenticated users -->
					<div class="relative">
						<button
							on:click={() => {
								showMyWorksDropdown = !showMyWorksDropdown;
								showAdminDropdown = false;
							}}
							class="flex items-center gap-2 text-sm text-gray-600 hover:underline dark:text-gray-300"
							aria-haspopup="true"
							aria-expanded={showMyWorksDropdown}
						>
							<Icon icon="mdi:briefcase" class="h-5 w-5 text-gray-600 dark:text-gray-300" />
							<span class="hidden sm:inline">My Works</span>
							<Icon icon="mdi:chevron-down" class="h-4 w-4 text-gray-600 dark:text-gray-300" />
						</button>
						{#if showMyWorksDropdown}
							<div
								class="absolute left-0 z-50 mt-2 w-64 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800"
							>
								{#each myWorksMenuItems as item}
									<a
										href={resolve(item.href as any)}
										class="block px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
										on:click={() => (showMyWorksDropdown = false)}
									>
										<Icon icon={item.icon} class="mr-2 inline-block h-4 w-4" />
										{item.label}
									</a>
								{/each}
							</div>
						{/if}
					</div>


					<!-- Admin/Manager menu - only show for Admin and Manager roles -->
					{#if isAdmin || isManager}
						<div class="relative">
							<button
								on:click={() => {
									showAdminDropdown = !showAdminDropdown;
									showMyWorksDropdown = false;
								}}
								class="flex items-center gap-2 text-sm text-gray-600 hover:underline dark:text-gray-300"
								aria-haspopup="true"
								aria-expanded={showAdminDropdown}
							>
								<Icon icon="mdi:shield" class="h-5 w-5 text-gray-600 dark:text-gray-300" />
								<span class="hidden capitalize sm:inline">{role}</span>
								<Icon icon="mdi:chevron-down" class="h-4 w-4 text-gray-600 dark:text-gray-300" />
							</button>
							{#if showAdminDropdown}
								<div
									class="absolute left-0 z-50 mt-2 w-48 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800"
								>
									{#each adminMenuItems as item}
										<a
											href={resolve(item.href as any)}
											class="block px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
											on:click={() => (showAdminDropdown = false)}
										>
											<Icon icon={item.icon} class="mr-2 inline-block h-4 w-4" />
											{item.label}
										</a>
									{/each}
								</div>
							{/if}
						</div>
					{/if}

					<a
						href={resolve('/about')}
						class="flex items-center gap-2 text-sm text-gray-600 hover:underline dark:text-gray-300"
					>
						<Icon icon="mdi:information-outline" class="h-5 w-5 text-gray-600 dark:text-gray-300" />
						<span class="hidden sm:inline">About</span>
					</a>
				{/if}
			</div>

			<div class="flex items-center gap-5">
				{#if authenticated}
					<div
						class="hidden items-center gap-1 rounded-lg px-2 py-1 text-sm text-gray-700 sm:flex dark:text-gray-300"
					>
						<Icon icon="mdi:clock-outline" class="h-4 w-4 text-gray-600 dark:text-gray-300" />
						<span>{nowStr}</span>
					</div>
					<button
						on:click={toggleDarkMode}
						class="rounded-full p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
						aria-label="Toggle dark mode"
					>
						{#if darkMode}
							<Icon icon="mdi:weather-sunny" class="h-5 w-5 text-gray-600 dark:text-gray-300" />
						{:else}
							<Icon icon="mdi:weather-night" class="h-5 w-5 text-gray-600" />
						{/if}
					</button>
					<div class="relative ml-1">
						<button
							on:click={() => {
								showNotificationsModal = !showNotificationsModal;
								if (showNotificationsModal) showUserProfileDropdown = false;
							}}
							class="relative rounded-full p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
							aria-label="Notifications"
						>
							<Icon icon="mdi:bell-outline" class="h-5 w-5 text-gray-600 dark:text-gray-300" />
							{#if $unreadCount > 0}
								<span
									class="absolute -top-1 -right-1 inline-flex min-w-[18px] items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold text-white"
									>{$unreadCount}</span
								>
							{/if}
						</button>
						{#if showNotificationsModal}
							<div
								class="absolute -right-40 z-50 mt-2 w-[460px] rounded-lg border border-neutral-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800"
							>
								<div
									class="flex items-center justify-between border-b border-neutral-200 px-3 py-2 dark:border-gray-700"
								>
									<div class="text-base font-semibold text-neutral-900 dark:text-white">
										Notifications
									</div>
									<a
										href={resolve('/notifications')}
										class="rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-gray-700"
										>See all</a
									>
								</div>
								<div class="flex items-center gap-2 px-3 pt-2">
									<button
										class="rounded px-2 py-1 text-xs font-medium hover:bg-neutral-100 dark:hover:bg-gray-700 {notifTab ===
										'All'
											? 'bg-neutral-100 dark:bg-gray-700'
											: ''}"
										on:click={() => (notifTab = 'All')}>All</button
									>
									<button
										class="rounded px-2 py-1 text-xs font-medium hover:bg-neutral-100 dark:hover:bg-gray-700 {notifTab ===
										'Unread'
											? 'bg-neutral-100 dark:bg-gray-700'
											: ''}"
										on:click={() => (notifTab = 'Unread')}>Unread</button
									>
									<div class="ml-auto flex items-center gap-1">
										<button
											class="rounded px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100 dark:text-gray-300 dark:hover:bg-gray-700"
											on:click={() => markAllAsRead()}>Mark all as read</button
										>
										<button
											class="rounded px-2 py-1 text-xs text-red-600 hover:bg-neutral-100 dark:text-red-400 dark:hover:bg-gray-700"
											on:click={() => clearAllNotifications()}>Delete all</button
										>
									</div>
								</div>
								<div class="px-3 pb-2 text-xs text-neutral-500 dark:text-gray-400">Earlier</div>
								<div class="max-h-[60vh] overflow-y-auto px-2 pb-2">
									{#if $notifications.length === 0}
										<div class="py-6 text-center text-sm text-neutral-600 dark:text-gray-300">
											No notifications
										</div>
									{:else}
										<div class="space-y-1.5">
											{#each notifTab === 'All' ? $notifications : $notifications.filter((n) => !n.read) as n (n.id)}
												<button
													type="button"
													class="group relative flex w-full cursor-pointer items-start gap-3 rounded px-2 py-2 text-left transition-colors hover:bg-neutral-50 dark:hover:bg-gray-700"
													on:click={() => {
														if (n.target_route) {
															showNotificationsModal = false;
															goto(n.target_route as any);
															markNotificationRead(n.id);
														}
													}}
													on:keydown={(e) => {
														if (e.key === 'Enter' && n.target_route) {
															showNotificationsModal = false;
															goto(n.target_route as any);
															markNotificationRead(n.id);
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
																<Icon
																	icon="mdi:account"
																	class="h-4 w-4 text-gray-600 dark:text-gray-300"
																/>
															</div>
														{/if}
													</div>
													<div class="min-w-0 flex-1">
														<div class="flex items-center justify-between">
															<div class="text-sm font-medium text-neutral-900 dark:text-white">
																{n.title}
															</div>
															<div class="ml-2 text-xs text-neutral-500 dark:text-gray-400">
																{new Date(n.created_at).toLocaleString()}
															</div>
														</div>
														<div
															class="text-sm wrap-break-word text-neutral-600 dark:text-gray-300"
														>
															{#if n.approver_name}
																<span class="font-semibold text-neutral-900 dark:text-white"
																	>{n.approver_name}</span
																>
																<span class="text-neutral-600 dark:text-gray-300">{n.message}</span>
															{:else}
																{n.message}
															{/if}
														</div>
													</div>
													{#if !n.read}
														<span class="inline-block h-2 w-2 shrink-0 rounded-full bg-blue-600"
														></span>
													{/if}
													<!-- Three-dot menu -->
													<div
														class="relative shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
													>
														<div
															class="cursor-pointer rounded p-1 hover:bg-neutral-200 dark:hover:bg-gray-600"
															role="button"
															tabindex="0"
															on:click|stopPropagation={() => {
																openMenuId = openMenuId === n.id ? null : n.id;
															}}
															on:keydown|stopPropagation={(e) => {
																if (e.key === 'Enter' || e.key === ' ') {
																	e.preventDefault();
																	openMenuId = openMenuId === n.id ? null : n.id;
																}
															}}
														>
															<Icon
																icon="mdi:dots-vertical"
																class="h-4 w-4 text-neutral-500 dark:text-gray-400"
															/>
														</div>
														{#if openMenuId === n.id}
															<div
																class="absolute top-full right-0 z-50 mt-1 min-w-[120px] rounded border border-neutral-200 bg-white shadow-lg dark:border-gray-600 dark:bg-gray-700"
															>
																<div
																	class="flex w-full cursor-pointer items-center gap-2 px-3 py-1.5 text-left text-sm text-neutral-700 hover:bg-neutral-100 dark:text-gray-300 dark:hover:bg-gray-600"
																	role="button"
																	tabindex="0"
																	on:click|stopPropagation={() => {
																		if (n.target_route) {
																			showNotificationsModal = false;
																			goto(n.target_route as any);
																		}
																		openMenuId = null;
																	}}
																	on:keydown|stopPropagation={(e) => {
																		if (e.key === 'Enter' || e.key === ' ') {
																			e.preventDefault();
																			if (n.target_route) {
																				showNotificationsModal = false;
																				goto(n.target_route as any);
																			}
																			openMenuId = null;
																		}
																	}}
																>
																	<Icon icon="mdi:eye" class="h-4 w-4" />
																	View
																</div>
																<div
																	class="flex w-full cursor-pointer items-center gap-2 px-3 py-1.5 text-left text-sm text-red-600 hover:bg-neutral-100 dark:text-red-400 dark:hover:bg-gray-600"
																	role="button"
																	tabindex="0"
																	on:click|stopPropagation={() => {
																		removeNotification(n.id);
																		openMenuId = null;
																	}}
																	on:keydown|stopPropagation={(e) => {
																		if (e.key === 'Enter' || e.key === ' ') {
																			e.preventDefault();
																			removeNotification(n.id);
																			openMenuId = null;
																		}
																	}}
																>
																	<Icon icon="mdi:delete" class="h-4 w-4" />
																	Delete
																</div>
															</div>
														{/if}
													</div>
												</button>
											{/each}
										</div>
									{/if}
								</div>
							</div>
						{/if}
					</div>
					<div class="relative">
						<button
							on:click={() => {
								showUserProfileDropdown = !showUserProfileDropdown;
								if (showUserProfileDropdown) showNotificationsModal = false;
							}}
							class="flex items-center gap-2 rounded-lg px-3 py-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
						>
							<Avatar
								firstName={userFirstName}
								lastName={userLastName}
								username={user}
								src={userAvatarUrl}
								size="sm"
							/>
							<div
								class="hidden flex-col items-start text-sm text-gray-700 sm:flex dark:text-gray-300"
							>
								<span class="font-medium"
									>{(() => {
										const fullName = `${userFirstName} ${userLastName}`.trim();
										return fullName || user;
									})()}</span
								>
								<span class="text-xs text-gray-500 dark:text-gray-400">{role}</span>
							</div>
						</button>
						{#if showUserProfileDropdown}
							<div
								class="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800"
							>
								<div class="border-b border-gray-200 px-4 py-3 dark:border-gray-700">
									<p class="font-semibold text-gray-900 dark:text-white">
										{(() => {
											const fullName = `${userFirstName} ${userLastName}`.trim();
											return fullName || user;
										})()}
									</p>
									<p class="text-xs text-gray-500 dark:text-gray-400">@{user}</p>
								</div>
								<a
									href={resolve('/profile')}
									class="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
									on:click={() => (showUserProfileDropdown = false)}
								>
									<Icon icon="mdi:account-circle" class="h-4 w-4" />
									My Profile
								</a>
								<button
									on:click={doLogout}
									class="flex w-full items-center gap-2 border-t border-gray-200 px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:border-gray-700 dark:text-red-400 dark:hover:bg-gray-700"
								>
									<Icon icon="mdi:logout" class="h-4 w-4" />
									Log Out
								</button>
							</div>
						{/if}
					</div>
				{:else}
					<a
						href={resolve('/login')}
						class="flex items-center rounded bg-blue-500 px-3 py-1.5 text-white hover:bg-blue-700"
					>
						<Icon icon="mdi:login" class="mr-1 h-4 w-4" />
						Login
					</a>
				{/if}
			</div>
		</div>
	</header>
{/if}

<main class="min-h-[calc(100vh-64px)] bg-white transition-colors dark:bg-gray-900">
	<div class="dark:text-white">
		<slot />
	</div>
</main>

<!-- Toast notifications area with Facebook-style design -->
<div class="fixed right-4 bottom-4 z-50 w-96 space-y-2">
	{#if toastItem}
		<NotificationToast notification={toastItem} />
	{/if}
</div>

<ConfirmModal
	bind:open={showLogoutConfirm}
	title="Confirm logout"
	message="Are you sure you want to log out?"
	confirmText="Logout"
	cancelText="Cancel"
	on:confirm={confirmLogout}
/>
