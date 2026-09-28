<script lang="ts">
	import { onMount } from 'svelte';
	import {
		userAPI,
		branchAPI,
		rolesAPI,
		type UserResponse,
		type CreateUser,
		type BranchResponse,
		type LeaveCreditResponse,
		leaveCreditsAPI
	} from '$lib/api';
	import { isAdmin, isAuthenticated, userId } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import UserModal from '$lib/UserModal.svelte';
	import Avatar from '$lib/Avatar.svelte';
	import Icon from '@iconify/svelte';
	import ConfirmModal from '$lib/ConfirmModal.svelte';

	let users: UserResponse[] = [];
	let branches: BranchResponse[] = [];
	let userLeaveCredits: Record<number, LeaveCreditResponse | null> = {};
	let loading = true;
	let error: string | null = null;
	let success: string | null = null;

	// Pagination
	let rowsPerPage = 10;
	let currentPage = 1;

	// Filters and search
	let searchTerm = '';
	let filterRole: string = 'All';
	// Sorting controls: default Name A–Z ascending
	let sortDir: 'asc' | 'desc' = 'asc';
	// Status filter
	let filterStatus: 'All' | 'Active' | 'Inactive' = 'All';

	// Role options fetched from backend
	let roleOptions: string[] = [];

	// Filtered and processed users (search + filters + sort)
	$: filteredUsers = users.filter((u) => {
		const q = searchTerm.trim().toLowerCase();
		if (q) {
			const fullName = ((u.first_name || '') + ' ' + (u.last_name || '')).toLowerCase();
			if (
				!(
					(u.username || '').toLowerCase().includes(q) ||
					(u.email || '').toLowerCase().includes(q) ||
					fullName.includes(q) ||
					String(u.id || '').includes(q)
				)
			)
				return false;
		}
		if (filterRole && filterRole !== 'All' && u.role !== filterRole) return false;
		if (filterStatus && filterStatus !== 'All') {
			const isActive = (u.status || 'Active') === 'Active';
			if (filterStatus === 'Active' && !isActive) return false;
			if (filterStatus === 'Inactive' && isActive) return false;
		}
		return true;
	});

	$: processedUsers = (() => {
		const arr = filteredUsers.slice();
		const dir = sortDir === 'asc' ? 1 : -1;
		const valFor = (u: UserResponse) => {
			const fullName = `${u.first_name || ''} ${u.last_name || ''}`.trim();
			return (fullName || u.username || '').toLowerCase();
		};
		arr.sort((a, b) => {
			const va = valFor(a);
			const vb = valFor(b);
			if (va < vb) return -1 * dir;
			if (va > vb) return 1 * dir;
			return 0;
		});
		return arr;
	})();

	$: totalPages =
		processedUsers && processedUsers.length
			? Math.max(1, Math.ceil(processedUsers.length / rowsPerPage))
			: 1;
	$: paginatedUsers = processedUsers
		? processedUsers.slice((currentPage - 1) * rowsPerPage, currentPage * rowsPerPage)
		: [];

	let showModal = false;
	let isEditing = false;
	// Support fields from both CreateUser and UserResponse
	let selectedUser: Partial<CreateUser> & Partial<UserResponse> = {};

	let admin = false;
	let authed = false;
	let currentUserId: number | null = null;
	const unsubUserId = userId.subscribe((v) => (currentUserId = v));

	// Deletion confirmation state
	let deletingUserId: number | null = null;
	let deleteUserOpen = false;
	let deleteUserMessage: string = '';
	$: deleteUserMessage = deletingUserId
		? `Are you sure you want to delete '${users.find((u) => u.id === deletingUserId)?.username || String(deletingUserId)}'?`
		: '';

	// Hover detail modal state
	let hoveredUser: UserResponse | null = null;
	let hoverX = 0;
	let hoverY = 0;
	let hoverTimeout: any = null;

	// Reactivation modal state
	let showReactivationModal = false;
	let reactivatingUser: UserResponse | null = null;
	let reactivationStartDate = '';
	let reactivationEndDate = '';
	let reactivationLoading = false;
	let reactivationError: string | null = null;
	// Actions info modal
	let showActionsInfoModal = false;

	function showHover(u: UserResponse, e: MouseEvent) {
		if (hoverTimeout) {
			clearTimeout(hoverTimeout);
			hoverTimeout = null;
		}
		hoveredUser = u;
		// Position slightly offset from cursor
		hoverX = e.clientX + 14;
		hoverY = e.clientY + 14;
	}

	function hideHover() {
		// Small delay to avoid flicker when moving between elements in the cell
		hoverTimeout = setTimeout(() => {
			hoveredUser = null;
		}, 100);
	}

	const unsubRole = isAdmin.subscribe((r) => (admin = r));
	const unsubAuth = isAuthenticated.subscribe((v) => (authed = v));

	onMount(async () => {
		// Require authentication
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}

		// Only admin can access management UI
		if (!admin) {
			return;
		}

		await Promise.all([loadUsers(), loadRoles()]);
	});

	$: if (!authed) {
		goto(resolve('/login'));
	}

	async function loadUsers() {
		try {
			loading = true;
			error = null;
			success = null;
			users = await userAPI.getAllUsers();
			branches = await branchAPI.getAllBranches();
			const creditsList = await Promise.all(
				users.map((u) =>
					leaveCreditsAPI
						.getUserCredits(u.id)
						.then((c) => c)
						.catch(() => null)
				)
			);
			userLeaveCredits = {};
			users.forEach((u, i) => {
				userLeaveCredits[u.id] = creditsList[i];
			});
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load users';
			console.error('Error loading users:', err);
		} finally {
			loading = false;
		}
	}

	async function loadRoles() {
		try {
			roleOptions = await rolesAPI.getAll();
			if (!roleOptions || roleOptions.length === 0) roleOptions = ['admin', 'manager', 'user'];
		} catch (e) {
			console.warn('Failed to load roles; falling back', e);
			roleOptions = ['admin', 'manager', 'user'];
		}
	}

	function getBranchName(id?: number) {
		if (!id) return 'Unassigned';
		const b = branches.find((x) => x.id === id);
		return b ? b.branch_name : String(id);
	}
	function formatDate(d?: string) {
		if (!d) return '—';
		try {
			return new Date(d).toLocaleDateString();
		} catch {
			return d;
		}
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

	function openCreateModal() {
		isEditing = false;
		selectedUser = {
			username: '',
			password: '',
			role: 'user',
			date_created: new Date().toISOString(),
			date_updated: new Date().toISOString()
		};
		showModal = true;
	}

	function openEditModal(user: UserResponse) {
		isEditing = true;
		selectedUser = { ...user, date_updated: new Date().toISOString() };
		showModal = true;
	}

	function closeModal() {
		showModal = false;
	}

	async function handleUserSubmit(event: CustomEvent) {
		const user = event.detail as (Partial<CreateUser> & Partial<UserResponse>) & {
			branch_id?: number;
		};
		try {
			if (isEditing) {
				const updatePayload: any = {};
				if (user.username !== undefined) updatePayload.username = user.username;
				if (user.role !== undefined) updatePayload.role = user.role;
				if (user.branch_id !== undefined && user.branch_id !== null) {
					const bid = Number(user.branch_id);
					if (!Number.isNaN(bid)) updatePayload.branch_id = bid;
				}
				if (user.password) updatePayload.password = user.password;
				if (user.email !== undefined) updatePayload.email = user.email;
				if (user.phone_number !== undefined) updatePayload.phone_number = user.phone_number;
				if (user.civil_status !== undefined) updatePayload.civil_status = user.civil_status;
				if (user.birthdate !== undefined) updatePayload.birthdate = user.birthdate;
				if (user.permanent_address_line !== undefined)
					updatePayload.permanent_address_line = user.permanent_address_line;
				if (user.current_address_line !== undefined)
					updatePayload.current_address_line = user.current_address_line;
				if (user.permanent_address_psgc !== undefined)
					updatePayload.permanent_address_psgc = user.permanent_address_psgc;
				if (user.current_address_psgc !== undefined)
					updatePayload.current_address_psgc = user.current_address_psgc;
				if (user.salutation !== undefined) updatePayload.salutation = user.salutation;
				if (user.department !== undefined) updatePayload.department = user.department;
				if (user.job_level !== undefined) updatePayload.job_level = user.job_level;

				if (user.emergency_contact_name !== undefined)
					updatePayload.emergency_contact_name = user.emergency_contact_name;
				if (user.emergency_contact_number !== undefined)
					updatePayload.emergency_contact_number = user.emergency_contact_number;
				if (user.first_name !== undefined) updatePayload.first_name = user.first_name;
				if (user.last_name !== undefined) updatePayload.last_name = user.last_name;
				if (user.emp_start_date !== undefined) updatePayload.emp_start_date = user.emp_start_date;
				if (user.emp_end_date !== undefined) updatePayload.emp_end_date = user.emp_end_date;
				// removed: gender, location, birth_date, contact_number

				await userAPI.updateUser(user.id as number, updatePayload);
				success = `User '${user.username}' updated successfully`;
			} else {
				const createPayload: any = {
					username: user.username as string,
					password: user.password as string,
					role: (user.role as string) || 'user'
				};
				if (user.branch_id !== undefined && user.branch_id !== null) {
					const bid = Number(user.branch_id);
					if (!Number.isNaN(bid)) createPayload.branch_id = bid;
				}
				if (user.email !== undefined) createPayload.email = user.email;
				if (user.phone_number !== undefined) createPayload.phone_number = user.phone_number;
				if (user.civil_status !== undefined) createPayload.civil_status = user.civil_status;
				if (user.birthdate !== undefined) createPayload.birthdate = user.birthdate;
				if (user.permanent_address_line !== undefined)
					createPayload.permanent_address_line = user.permanent_address_line;
				if (user.current_address_line !== undefined)
					createPayload.current_address_line = user.current_address_line;
				if (user.permanent_address_psgc !== undefined)
					createPayload.permanent_address_psgc = user.permanent_address_psgc;
				if (user.current_address_psgc !== undefined)
					createPayload.current_address_psgc = user.current_address_psgc;
				if (user.salutation !== undefined) createPayload.salutation = user.salutation;
				if (user.department !== undefined) createPayload.department = user.department;
				if (user.job_level !== undefined) createPayload.job_level = user.job_level;

				if (user.emergency_contact_name !== undefined)
					createPayload.emergency_contact_name = user.emergency_contact_name;
				if (user.emergency_contact_number !== undefined)
					createPayload.emergency_contact_number = user.emergency_contact_number;
				if (user.first_name !== undefined) createPayload.first_name = user.first_name;
				if (user.last_name !== undefined) createPayload.last_name = user.last_name;
				if (user.emp_start_date !== undefined) createPayload.emp_start_date = user.emp_start_date;
				if (user.emp_end_date !== undefined) createPayload.emp_end_date = user.emp_end_date;
				// removed: gender, location, birth_date, contact_number

				const newUser = await userAPI.createUser(createPayload);
				success = `User '${user.username}' created successfully`;
			}
			await loadUsers();
			closeModal();
			setTimeout(() => (success = null), 3000);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to save user';
			console.error('Error saving user:', err);
		}
	}

	async function deleteUser(userId: number) {
		try {
			const userToDelete = users.find((u) => u.id === userId);
			await userAPI.deleteUser(userId);
			users = users.filter((user) => user.id !== userId);
			deletingUserId = null;
			success = `User '${userToDelete?.username}' deleted successfully`;
			setTimeout(() => (success = null), 3000);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to delete user';
			console.error('Error deleting user:', err);
		}
	}

	function confirmDelete(userId: number) {
		if (currentUserId !== null && userId === currentUserId) {
			error = 'You cannot delete your own account while logged in';
			deletingUserId = null;
			deleteUserOpen = false;
			return;
		}
		deletingUserId = userId;
		deleteUserOpen = true;
	}

	function cancelDelete() {
		deletingUserId = null;
		deleteUserOpen = false;
	}

	function openReactivationModal(user: UserResponse) {
		reactivatingUser = user;
		// Pre-fill with current dates if available
		reactivationStartDate = user.emp_start_date || '';
		reactivationEndDate = user.emp_end_date || '';
		reactivationError = null;
		showReactivationModal = true;
	}

	function closeReactivationModal() {
		showReactivationModal = false;
		reactivatingUser = null;
		reactivationStartDate = '';
		reactivationEndDate = '';
		reactivationError = null;
	}

	async function handleReactivation() {
		if (!reactivatingUser || !reactivationStartDate || !reactivationEndDate) {
			reactivationError = 'Please enter both start and end dates';
			return;
		}

		if (reactivationStartDate >= reactivationEndDate) {
			reactivationError = 'Start date must be before end date';
			return;
		}

		try {
			reactivationLoading = true;
			reactivationError = null;

			const response = await fetch(
				`http://127.0.0.1:8000/user/${reactivatingUser.id}/reactivate?emp_start_date=${reactivationStartDate}&emp_end_date=${reactivationEndDate}`,
				{
					method: 'POST',
					headers: {
						Authorization: `Bearer ${localStorage.getItem('access_token')}`
					}
				}
			);

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to reactivate user');
			}

			success = `User '${reactivatingUser.username}' reactivated successfully`;
			await loadUsers();
			closeReactivationModal();
			setTimeout(() => (success = null), 3000);
		} catch (err) {
			reactivationError = err instanceof Error ? err.message : 'Failed to reactivate user';
			console.error('Error reactivating user:', err);
		} finally {
			reactivationLoading = false;
		}
	}

	// (Removed timeAgo/Last Active column — joined date is displayed from `date_created`)

	import { onDestroy } from 'svelte';
	onDestroy(() => {
		unsubRole();
		unsubAuth();
		unsubUserId();
	});
</script>

{#if !admin}
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
	<div class="container mx-auto p-4 dark:text-white">
		<h1 class="mb-6 text-3xl font-bold dark:text-white">User Management</h1>

		{#if error}
			<div
				class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700 dark:border-red-600 dark:bg-red-900 dark:text-red-200"
			>
				{error}
			</div>
		{/if}

		{#if success}
			<div
				class="mb-4 rounded border border-green-400 bg-green-100 px-4 py-3 text-green-700 dark:border-green-600 dark:bg-green-900 dark:text-green-200"
			>
				{success}
			</div>
		{/if}

		<div class="mb-4 flex items-center justify-between gap-4">
			<div class="flex flex-1 flex-col md:flex-row md:items-center md:gap-3">
				<input
					type="search"
					placeholder="Search"
					class="w-full rounded border px-4 py-2 md:max-w-lg"
					bind:value={searchTerm}
				/>
				<div class="mt-2 grid grid-cols-2 gap-2 md:mt-0 md:flex md:items-center md:gap-3">
					<select
						class="rounded border px-3 py-2"
						bind:value={filterRole}
						on:change={() => (currentPage = 1)}
					>
						<option value="All">All Roles</option>
						{#each roleOptions as r}
							<option value={r}>{r}</option>
						{/each}
					</select>
					<select
						class="rounded border px-3 py-2"
						bind:value={sortDir}
						on:change={() => (currentPage = 1)}
					>
						<option value="asc">Ascending</option>
						<option value="desc">Descending</option>
					</select>
					<select
						class="rounded border px-3 py-2"
						bind:value={filterStatus}
						on:change={() => (currentPage = 1)}
					>
						<option value="All">All Statuses</option>
						<option value="Active">Active</option>
						<option value="Inactive">Inactive</option>
					</select>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button
					on:click={openCreateModal}
					class="flex items-center gap-2 rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
				>
					<Icon icon="mdi:user-plus" class="h-5 w-5" />
					<span class="hidden sm:inline">Add User</span>
				</button>
			</div>
		</div>

		<UserModal
			bind:showModal
			bind:user={selectedUser}
			bind:isEditing
			on:close={closeModal}
			on:submit={handleUserSubmit}
		/>

		{#if loading}
			<div class="py-8 text-center">
				<p class="text-gray-600 dark:text-gray-400">Loading users...</p>
			</div>
		{:else if users.length === 0}
			<div class="py-8 text-center">
				<p class="text-gray-600 dark:text-gray-400">No users found.</p>
			</div>
		{:else}
			<!-- Mobile card list -->
			<div class="space-y-2 sm:hidden">
				{#each paginatedUsers as user (user.id)}
					<div
						class="rounded border border-gray-200 bg-white p-3 shadow-sm dark:border-gray-700 dark:bg-gray-800"
					>
						<div class="flex items-center gap-2">
							<Avatar
								firstName={user.first_name}
								lastName={user.last_name}
								username={user.username}
								size="sm"
							/>
							<div>
								<a href={resolve(`/profile/${user.id}`)} class="font-medium hover:underline"
									>{(user.first_name || '') + (user.last_name ? ' ' + user.last_name : '') ||
										user.username}</a
								>
								<div class="text-xs text-gray-600 dark:text-gray-300">ID: {user.id}</div>
								<div class="text-xs text-gray-600 dark:text-gray-300">{user.role}</div>
							</div>
						</div>
						<div class="mt-2 grid grid-cols-1 gap-1 text-sm">
							<div class="text-gray-700 dark:text-gray-200">{user.email || '-'}</div>
							<div class="text-gray-700 dark:text-gray-200">
								Start: {formatDate(user.emp_start_date)}
							</div>
							<div class="text-gray-700 dark:text-gray-200">
								End: {formatDate(user.emp_end_date)}
							</div>
						</div>
						<div class="mt-2 flex gap-2">
							<button
								on:click={() => openEditModal(user)}
								class="inline-flex items-center rounded bg-yellow-500 px-3 py-1 text-white hover:bg-yellow-700"
							>
								<Icon icon="mdi:pencil" class="h-4 w-4" />
							</button>
							<button
								on:click={() => confirmDelete(user.id)}
								class="inline-flex items-center rounded bg-red-500 px-3 py-1 text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
								disabled={currentUserId !== null && user.id === currentUserId}
							>
								<Icon icon="mdi:delete" class="h-4 w-4" />
							</button>
						</div>
					</div>
				{/each}
			</div>

			<!-- Desktop/tablet table -->
			<div class="hidden overflow-x-auto rounded bg-white p-2 shadow-md sm:block dark:bg-gray-800">
				<table class="w-full table-auto">
					<thead>
						<tr class="text-left text-sm text-gray-600 dark:text-gray-300">
							<th class="px-4 py-3">ID</th>
							<th class="px-4 py-3">User</th>
							<th class="px-4 py-3">Email</th>
							<th class="px-4 py-3">Username</th>
							<th class="px-4 py-3">Role</th>
							<th class="px-4 py-3">Start Date</th>
							<th class="px-4 py-3">End Date</th>
							<th class="px-4 py-3">Status</th>
							<th class="px-4 py-3">
								<span class="inline-flex items-center gap-2">
									<span>Actions</span>
									<button
										class="inline-flex items-center rounded bg-gray-100 px-2 py-1 text-xs text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
										on:click={() => (showActionsInfoModal = true)}
										aria-label="Actions info"
									>
										<Icon icon="mdi:information-outline" class="h-4 w-4" />
									</button>
								</span>
							</th>
						</tr>
					</thead>
					<tbody>
						{#each paginatedUsers as user (user.id)}
							<tr
								class="border-t text-sm text-gray-700 dark:text-gray-200"
								on:mouseenter={(e) => showHover(user, e)}
								on:mousemove={(e) => showHover(user, e)}
								on:mouseleave={hideHover}
							>
								<td class="px-4 py-3">{user.id}</td>
								<td class="px-4 py-3">
									<div class="flex items-center gap-2">
										<Avatar
											firstName={user.first_name}
											lastName={user.last_name}
											username={user.username}
											src={user.profile_picture_url}
											size="sm"
										/>
										<a href={resolve(`/profile/${user.id}`)} class="hover:underline"
											>{(user.first_name || '') + (user.last_name ? ' ' + user.last_name : '') ||
												user.username}</a
										>
									</div>
								</td>
								<td class="px-4 py-3">{user.email || '-'}</td>
								<td class="px-4 py-3"
									><a href={resolve(`/profile/${user.id}`)} class="text-blue-600 hover:underline"
										>{user.username}</a
									></td
								>
								<td class="px-4 py-3">{user.role}</td>
								<td class="px-4 py-3">{formatDate(user.emp_start_date)}</td>
								<td class="px-4 py-3">{formatDate(user.emp_end_date)}</td>
								<td class="px-4 py-3">
									<span
										class={`inline-block rounded-full px-2 py-1 text-xs font-semibold ${
											(user.status || 'Active') === 'Active'
												? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
												: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
										}`}
									>
										{(user.status || 'Active') === 'Active' ? 'Active' : 'Inactive'}
									</span>
									{#if user.blocked}
										<span
											class="ml-2 inline-block rounded-full bg-red-100 px-2 py-1 text-xs font-semibold text-red-800 dark:bg-red-900 dark:text-red-200"
											>Blocked</span
										>
									{/if}
								</td>
								<td class="px-4 py-3">
									<div class="flex gap-2">
										<button
											on:click={() => openEditModal(user)}
											class="inline-flex items-center rounded bg-yellow-500 px-3 py-1 text-white hover:bg-yellow-700"
										>
											<Icon icon="mdi:pencil" class="h-4 w-4" />
										</button>
										{#if admin}
											<button
												on:click={async () => {
													try {
														const next = !user.blocked;
														await userAPI.updateUser(user.id as number, { blocked: next });
														// Optimistic update for immediate icon change
														users = users.map((u) =>
															u.id === user.id ? { ...u, blocked: next } : u
														);
														success = `User '${user.username}' ${next ? 'blocked' : 'unblocked'} successfully`;
														await loadUsers();
														setTimeout(() => (success = null), 3000);
													} catch (e) {
														error =
															e instanceof Error ? e.message : 'Failed to update user block status';
													}
												}}
												class={`inline-flex items-center rounded px-3 py-1 text-white ${user.blocked ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-600 hover:bg-gray-700'}`}
											>
												<Icon icon={user.blocked ? 'mdi:lock-open' : 'mdi:lock'} class="h-4 w-4" />
											</button>
										{/if}
										{#if user.status !== 'Active'}
											<button
												on:click={() => openReactivationModal(user)}
												class="inline-flex items-center rounded bg-blue-500 px-3 py-1 text-white hover:bg-blue-700"
											>
												<Icon icon="mdi:refresh" class="h-4 w-4" />
											</button>
										{/if}
										<button
											on:click={() => confirmDelete(user.id)}
											class="inline-flex items-center rounded bg-red-500 px-3 py-1 text-white hover:bg-red-700"
										>
											<Icon icon="mdi:delete" class="h-4 w-4" />
										</button>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>

				{#if hoveredUser}
					<div
						class="pointer-events-none fixed z-50"
						style={`top: ${hoverY}px; left: ${hoverX}px;`}
					>
						<div
							class="w-64 rounded-lg border border-neutral-200 bg-white p-3 shadow-xl dark:border-gray-700 dark:bg-gray-800"
						>
							<div class="flex flex-col items-center gap-2">
								<Avatar
									firstName={hoveredUser.first_name}
									lastName={hoveredUser.last_name}
									username={hoveredUser.username}
									size="md"
								/>
								<div class="text-sm font-semibold text-neutral-900 dark:text-white">
									{((hoveredUser.first_name || '') + ' ' + (hoveredUser.last_name || '')).trim() ||
										hoveredUser.username}
								</div>
							</div>
							<div class="mt-3 space-y-2 text-sm">
								<div class="flex items-center gap-2">
									<Icon icon="mdi:office-building" class="h-4 w-4 text-neutral-500" />
									<span class="text-neutral-700 dark:text-gray-300"
										>{getBranchName(hoveredUser.branch_id)}</span
									>
								</div>
								<div class="flex items-center gap-2">
									<Icon icon="mdi:email" class="h-4 w-4 text-neutral-500" />
									<span class="text-neutral-700 dark:text-gray-300">{hoveredUser.email || '—'}</span
									>
								</div>
								<div class="flex items-start gap-2">
									<Icon
										icon="mdi:clipboard-text-multiple-outline"
										class="mt-0.5 h-4 w-4 text-neutral-500"
									/>
									<div class="space-y-1 text-sm text-neutral-700 dark:text-gray-300">
										<div>Phone Number: —</div>
										<div>Home Address: —</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				{/if}

				<!-- Pagination controls -->
				<div class="mt-3 flex items-center justify-between px-2">
					<div class="flex items-center gap-2">
						<label class="text-sm" for="rowsPerPage">Rows per page:</label>
						<select
							id="rowsPerPage"
							class="rounded border px-2 py-1"
							bind:value={rowsPerPage}
							on:change={() => (currentPage = 1)}
						>
							<option value={5}>5</option>
							<option value={10}>10</option>
							<option value={25}>25</option>
							<option value={50}>50</option>
						</select>
					</div>
					<div class="flex items-center gap-3">
						<div class="text-sm text-gray-600 dark:text-gray-300">
							{users.length === 0 ? '0' : `${(currentPage - 1) * rowsPerPage + 1}`} - {Math.min(
								currentPage * rowsPerPage,
								users.length
							)} of {users.length}
						</div>
						<button
							class="rounded border px-2 py-1"
							on:click={() => (currentPage = Math.max(1, currentPage - 1))}
							disabled={currentPage <= 1}>Prev</button
						>
						<span class="text-sm">Page {currentPage} / {totalPages}</span>
						<button
							class="rounded border px-2 py-1"
							on:click={() => (currentPage = Math.min(totalPages, currentPage + 1))}
							disabled={currentPage >= totalPages}>Next</button
						>
					</div>
				</div>
			</div>
		{/if}
	</div>

	<!-- Reactivation Modal -->
	{#if showReactivationModal && reactivatingUser}
		<div
			class="fixed inset-0 z-50 flex items-center justify-center p-4"
			style="background: rgba(0, 0, 0, 0.1); backdrop-filter: blur(2px);"
		>
			<div class="w-full max-w-md rounded-lg bg-white p-6 shadow-lg dark:bg-gray-800">
				<h2 class="mb-4 text-xl font-bold dark:text-white">Reactivate User</h2>
				<p class="mb-4 text-gray-600 dark:text-gray-300">
					Reactivate <strong>{reactivatingUser.username}</strong> with new contract dates
				</p>

				{#if reactivationError}
					<div
						class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700 dark:border-red-600 dark:bg-red-900 dark:text-red-200"
					>
						{reactivationError}
					</div>
				{/if}

				<div class="mb-4 space-y-4">
					<div>
						<label
							for="reactivation-start"
							class="block text-sm font-medium text-gray-700 dark:text-gray-300">Start Date</label
						>
						<input
							id="reactivation-start"
							type="date"
							bind:value={reactivationStartDate}
							class="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
						/>
					</div>
					<div>
						<label
							for="reactivation-end"
							class="block text-sm font-medium text-gray-700 dark:text-gray-300">End Date</label
						>
						<input
							id="reactivation-end"
							type="date"
							bind:value={reactivationEndDate}
							class="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
						/>
					</div>
				</div>

				<div class="flex gap-3">
					<button
						on:click={handleReactivation}
						disabled={reactivationLoading}
						class="flex-1 rounded bg-blue-500 px-4 py-2 font-medium text-white hover:bg-blue-600 disabled:opacity-50"
					>
						{#if reactivationLoading}
							Reactivating...
						{:else}
							Reactivate
						{/if}
					</button>
					<button
						on:click={closeReactivationModal}
						disabled={reactivationLoading}
						class="flex-1 rounded bg-gray-500 px-4 py-2 font-medium text-white hover:bg-gray-600 disabled:opacity-50"
					>
						Cancel
					</button>
				</div>
			</div>
		</div>
	{/if}

	{#if showActionsInfoModal}
		<div
			class="fixed inset-0 z-50 flex items-center justify-center p-4"
			style="background: rgba(0, 0, 0, 0.1); backdrop-filter: blur(2px);"
		>
			<div class="w-full max-w-md rounded-lg bg-white p-6 shadow-lg dark:bg-gray-800">
				<h2 class="mb-4 text-xl font-bold dark:text-white">Action Icons</h2>
				<div class="space-y-3 text-sm text-gray-700 dark:text-gray-300">
					<div class="flex items-center gap-2">
						<Icon icon="mdi:pencil" class="h-5 w-5 text-yellow-600" />
						<span>Edit user details</span>
					</div>
					<div class="flex items-center gap-2">
						<Icon icon="mdi:lock" class="h-5 w-5 text-gray-700" />
						<span>Block user (prevent login)</span>
					</div>
					<div class="flex items-center gap-2">
						<Icon icon="mdi:lock-open" class="h-5 w-5 text-green-700" />
						<span>Unblock user (allow login)</span>
					</div>
					<div class="flex items-center gap-2">
						<Icon icon="mdi:refresh" class="h-5 w-5 text-blue-600" />
						<span>Reactivate contract (set new start/end dates)</span>
					</div>
					<div class="flex items-center gap-2">
						<Icon icon="mdi:delete" class="h-5 w-5 text-red-600" />
						<span>Delete user</span>
					</div>
				</div>
				<div class="mt-5 flex gap-3">
					<button
						on:click={() => (showActionsInfoModal = false)}
						class="flex-1 rounded bg-gray-500 px-4 py-2 font-medium text-white hover:bg-gray-600"
					>
						Close
					</button>
				</div>
			</div>
		</div>
	{/if}

	<ConfirmModal
		bind:open={deleteUserOpen}
		title="Delete User"
		message={deleteUserMessage}
		confirmText="Delete"
		cancelText="Cancel"
		on:confirm={() => deleteUser(deletingUserId as number)}
	/>
{/if}
