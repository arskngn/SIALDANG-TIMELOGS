<script lang="ts">
	import { onMount } from 'svelte';
	import api, {
		user201API,
		document_typeAPI,
		type UserResponse,
		type UpdateUser,
		type ProjectResponse,
		type BranchResponse,
		type User201FileResponse,
		type DocumentTypeResponse,
		type LeaveCreditResponse,
		type SystemOptionResponse,
		leaveCreditsAPI,
		systemOptionsAPI
	} from '$lib/api';
	import { isAdmin, isAuthenticated } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Icon from '@iconify/svelte';
	import Avatar from '$lib/Avatar.svelte';
	import { page } from '$app/stores';
	import { listProvinces, listMuncities, listBarangays } from '@jobuntux/psgc';

	let authed = false;
	let admin = false;
	const unsubAuth = isAuthenticated.subscribe((v) => (authed = v));
	const unsubAdmin = isAdmin.subscribe((v) => (admin = v));

	let user: UserResponse | null = null;
	let loading = true;
	let error: string | null = null;
	let success: string | null = null;

	let userId: number | null = null;
	let userProjects: ProjectResponse[] = [];
	let branches: BranchResponse[] = [];
	let systemOptions: SystemOptionResponse[] = [];
	$: departments = systemOptions.filter((o) => o.category === 'Department');
	$: salutations = systemOptions.filter((o) => o.category === 'Salutation');
	$: jobLevels = systemOptions.filter((o) => o.category === 'Job Level');
	let documentTypes: DocumentTypeResponse[] = [];
	let userFiles: User201FileResponse[] = [];
	let leaveCredits: LeaveCreditResponse | null = null;
	let leaveCreditsError: string | null = null;
	$: getDocTypeById = (id: number) => documentTypes.find((d) => d.id === id);
	$: preDocs = userFiles.filter(
		(f) =>
			f.status === 'Approved' && getDocTypeById(f.document_type_id)?.category === 'pre-employment'
	);
	$: payrollDocs = userFiles.filter(
		(f) => f.status === 'Approved' && getDocTypeById(f.document_type_id)?.category === 'payroll'
	);
	let govReveal: Record<string, boolean> = {};
	$: govItems = user
		? [
				{ key: 'tin_number', label: 'TIN', value: user.tin_number || '—' },
				{ key: 'sss_number', label: 'SSS', value: user.sss_number || '—' },
				{ key: 'philhealth_number', label: 'PhilHealth', value: user.philhealth_number || '—' },
				{ key: 'pagibig_number', label: 'Pag-IBIG', value: user.pagibig_number || '—' }
			]
		: [];
	let modalOpen = false;
	let modalTitle = '';
	let modalItems: { name: string; url: string; file: User201FileResponse }[] = [];
	let modalLoading = false;
	async function openModalFor(kind: 'Pre-employment Requirements' | 'Payroll Requirements') {
		modalTitle = kind;
		modalLoading = true;
		const source = kind === 'Pre-employment Requirements' ? preDocs : payrollDocs;

		const promises = source.map(async (f) => {
			const dt = getDocTypeById(f.document_type_id);
			let url = f.file_url || '';
			if (f.s3_path) {
				try {
					const pr = await user201API.presignDownload(f.s3_path);
					url = pr.download_url;
				} catch {
					url = f.file_url || '';
				}
			}
			return { name: dt?.name || f.file_name, url, file: f };
		});

		modalItems = await Promise.all(promises);
		modalOpen = true;
		modalLoading = false;
	}

	function getPermanentAddress(): string {
		if (!user) return '—';

		const addressLine = user.permanent_address_line?.trim() || '';
		const psgc = user.permanent_address_psgc?.trim();

		if (!psgc || psgc.length !== 10) {
			return addressLine || '—';
		}

		const regionCode = psgc.substring(0, 2);
		const provinceCode = psgc.substring(2, 5);
		const muncityCode = psgc.substring(5, 7);
		const barangayCode = psgc.substring(7, 10);

		const province = listProvinces(regionCode).find((p) => p.provCode === provinceCode);

		const muncity = listMuncities(provinceCode).find(
			(m) => m.munCityCode === `${provinceCode}${muncityCode}`
		);

		const barangay = listBarangays(`${provinceCode}${muncityCode}`).find(
			(b) => b.brgyCode === `${provinceCode}${muncityCode}${barangayCode}`
		);

		const parts = [
			addressLine,
			barangay?.brgyName,
			muncity?.munCityName,
			province?.provName
		].filter(Boolean);

		return parts.length > 0 ? parts.join(', ') : '—';
	}

	function closeModal() {
		modalOpen = false;
		modalItems = [];
		modalTitle = '';
	}
	function downloadUrl(url: string) {
		if (!url) return;

		const link = document.createElement('a');
		link.href = url;
		link.target = '_blank';
		link.rel = 'noopener noreferrer';

		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}

	// Helper function to extract file type from filename
	function getFileType(fileName?: string): string {
		if (!fileName) return '';
		const match = fileName.match(/\.([a-zA-Z0-9]+)$/);
		return match ? match[1].toUpperCase() : '';
	}

	// Editable fields
	let form: Partial<UpdateUser & { password?: string }> = {};
	let original: Partial<UserResponse> = {};

	function toISODate(value?: string): string | undefined {
		if (!value) return undefined;
		const d = new Date(value);
		if (isNaN(d.getTime())) return undefined;
		const yyyy = d.getFullYear();
		const mm = String(d.getMonth() + 1).padStart(2, '0');
		const dd = String(d.getDate()).padStart(2, '0');
		return `${yyyy}-${mm}-${dd}`;
	}

	function formatLeaveCredits(value?: number | null): string {
		if (value === null || value === undefined) return '—';
		const rounded = Math.round(value * 2) / 2;
		const formatted = rounded.toFixed(1).replace(/\.0$/, '');
		if (rounded < 0) {
			return `${formatted} (Borrowed)`;
		}
		return formatted;
	}
	function leaveCreditColorClass(value?: number | null): string {
		if (value === null || value === undefined) return '';
		if (value <= 0) return 'text-red-600 dark:text-red-400';
		return 'text-green-600 dark:text-green-400';
	}

	onMount(async () => {
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}
		if (!admin) {
			return;
		}
		userId = Number($page.params.id);
		if (!userId || Number.isNaN(userId)) {
			error = 'Invalid user id';
			loading = false;
			return;
		}
		try {
			const [u, up, b, dt, uf, so] = await Promise.all([
				api.userAPI.getUser(userId),
				api.userAPI.getUserProjects(userId).catch(() => []),
				api.branchAPI.getAllBranchesPublic().catch(() => []),
				document_typeAPI.getAllPublic().catch(() => []),
				user201API.listByUserActive(userId).catch(() => []),
				systemOptionsAPI.getAll().catch(() => [])
			]);
			user = u;
			userProjects = up;
			branches = b;
			documentTypes = dt;
			userFiles = uf;
			systemOptions = so;
			try {
				leaveCredits = await leaveCreditsAPI.getUserCredits(userId);
			} catch (e: unknown) {
				leaveCreditsError = e instanceof Error ? e.message : 'Failed to load leave credits';
			}
			// Initialize form
			form.username = user.username;
			form.email = user.email;
			form.salutation = user.salutation;
			form.department = user.department;
			form.job_level = user.job_level;
			form.emergency_contact_name = user.emergency_contact_name;
			form.emergency_contact_number = user.emergency_contact_number;
			form.first_name = user.first_name;
			form.last_name = user.last_name;
			form.role = user.role;
			form.branch_id = user.branch_id;
			original = { ...user };
		} catch (e: any) {
			error = e?.message || 'Failed to load user';
		} finally {
			loading = false;
		}
	});

	function computeChanges(): Partial<UpdateUser & { password?: string }> {
		const changes: any = {};
		const keys: (keyof (UpdateUser & { password?: string }))[] = [
			'username',
			'email',
			'salutation',
			'department',
			'job_level',
			'emergency_contact_name',
			'emergency_contact_number',
			'first_name',
			'last_name',
			'role',
			'branch_id',
			'password'
		];
		for (const k of keys) {
			const newVal = (form as any)[k];
			const oldVal = (original as any)[k];
			if (newVal !== undefined && newVal !== oldVal && newVal !== '') {
				(changes as any)[k] = newVal;
			}
		}
		return changes;
	}

	async function save() {
		error = null;
		success = null;
		if (!userId) return;
		const changes = computeChanges();
		if (Object.keys(changes).length === 0) {
			success = 'No changes to save';
			return;
		}
		try {
			const updated = await api.userAPI.updateUser(userId, changes);
			user = updated;
			original = { ...updated };
			success = 'User updated successfully';
		} catch (e: any) {
			error = e?.message || 'Failed to update user';
		}
	}

	function resetForm() {
		if (!user) return;
		form.username = user.username;
		form.email = user.email;
		form.salutation = user.salutation;
		form.department = user.department;
		form.job_level = user.job_level;
		form.emergency_contact_name = user.emergency_contact_name;
		form.emergency_contact_number = user.emergency_contact_number;
		form.first_name = user.first_name;
		form.last_name = user.last_name;
		form.role = user.role;
		form.branch_id = user.branch_id;
		form.password = '';
		success = null;
		error = null;
	}
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
	<div class="container mx-auto px-4 py-6">
		<div class="mb-4 flex items-center justify-between">
			<h1 class="text-3xl font-semibold">User Profile</h1>
			<a
				href={resolve('/users')}
				class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
				aria-label="Return to User Management"
			>
				<Icon icon="mdi:arrow-left" class="h-4 w-4" />
				<span>Return</span>
			</a>
		</div>

		{#if loading}
			<p>Loading...</p>
		{:else if error}
			<div
				class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700 dark:border-red-600 dark:bg-red-900 dark:text-red-200"
			>
				{error}
			</div>
		{:else if user}
			<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
				<div class="md:col-span-1">
					<div class="flex items-center gap-4">
						<Avatar
							firstName={user.first_name}
							lastName={user.last_name}
							username={user.username}
							src={user.profile_picture_url}
							size="2xl"
						/>
						<div>
							<p class="text-2xl font-semibold">
								{(() => {
									const fullName = `${user?.first_name || ''} ${user?.last_name || ''}`.trim();
									return fullName || user.username;
								})()}
							</p>
							<p class="text-sm text-gray-500 dark:text-gray-400">{user.role}</p>
						</div>
					</div>
					<div class="mt-4 text-sm text-gray-600 dark:text-gray-300">
						<p>
							<span class="font-medium">Branch:</span>
							{(() => {
								const bid = user?.branch_id ?? null;
								const branch = branches.find((b) => b.id === bid);
								return branch ? branch.branch_name : (bid ?? '—');
							})()}
						</p>
						{#if userProjects.length > 0}
							<div class="mt-2">
								<p class="mb-1 font-medium">
									Project: {userProjects.map((p) => p.project_name).join(', ')}
								</p>
							</div>
						{:else}
							<p class="mt-2"><span class="font-medium">Project:</span> None</p>
						{/if}
						<p class="mt-2">
							<span class="font-medium">Phone Number:</span>
							{user.phone_number || '—'}
						</p>

						<p class="mt-2">
							<span class="font-medium">Permanent Address:</span>
							{getPermanentAddress()}
						</p>
						<p class="mt-2">
							<span class="font-medium">Joined:</span>
							{user.date_created ? new Date(user.date_created).toLocaleDateString() : '—'}
						</p>
						<p class="mt-2">
							<span class="font-medium">Last Updated:</span>
							{user.date_updated ? new Date(user.date_updated).toLocaleDateString() : '—'}
						</p>
						<div class="mt-6">
							<div class="mb-2 text-base font-semibold">Government Mandated Requirements</div>
							<div class="space-y-2">
								{#each govItems as it (it.key)}
									<div
										class="flex items-center justify-between rounded border px-3 py-2 dark:border-gray-700"
									>
										<div class="text-sm text-neutral-800 dark:text-gray-200">{it.label}</div>
										<div class="flex items-center gap-3">
											<div class="text-lg tracking-widest select-none">
												{govReveal[it.key] ? it.value : '••••••••••'}
											</div>
											<button
												class="rounded bg-gray-100 p-1 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600"
												on:click={() =>
													(govReveal = { ...govReveal, [it.key]: !govReveal[it.key] })}
											>
												<Icon icon="mdi:eye" class="h-4 w-4" />
											</button>
										</div>
									</div>
								{/each}
							</div>
						</div>
						<div class="mt-6">
							<div class="mb-2 flex items-center justify-between">
								<div class="text-base font-semibold">Pre-employment Requirements</div>
								<button
									class="inline-flex items-center gap-2 rounded bg-blue-600 px-2 py-1 text-sm text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
									on:click={() => openModalFor('Pre-employment Requirements')}
								>
									<Icon icon="mdi:eye" class="h-4 w-4" />
									View
								</button>
							</div>
							<div class="text-xs text-neutral-600 dark:text-gray-400">
								Compilation of submitted items
							</div>
						</div>
						<div class="mt-6">
							<div class="mb-2 flex items-center justify-between">
								<div class="text-base font-semibold">Payroll Requirements</div>
								<button
									class="inline-flex items-center gap-2 rounded bg-blue-600 px-2 py-1 text-sm text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
									on:click={() => openModalFor('Payroll Requirements')}
								>
									<Icon icon="mdi:eye" class="h-4 w-4" />
									View
								</button>
							</div>
							<div class="text-xs text-neutral-600 dark:text-gray-400">
								Compilation of submitted items
							</div>
						</div>
					</div>
				</div>

				<div class="md:col-span-1">
					{#if success}
						<div
							class="mb-4 rounded border border-green-400 bg-green-100 px-4 py-3 text-green-700 dark:border-green-600 dark:bg-green-900 dark:text-green-200"
						>
							{success}
						</div>
					{/if}

					<div class="grid grid-cols-1 gap-2 md:grid-cols-2">
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Username</div>
							<input
								id="admin-username"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.username}
							/>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Email</div>
							<input
								id="admin-email"
								type="email"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.email}
							/>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Emergency Contact Name</div>
							<input
								id="admin-emergency-name"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.emergency_contact_name}
							/>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">
								Emergency Contact Number
							</div>
							<input
								id="admin-emergency-number"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								type="tel"
								inputmode="numeric"
								pattern="\\d*"
								bind:value={form.emergency_contact_number}
								on:input={(e) =>
									(form.emergency_contact_number = (e.target as HTMLInputElement).value.replace(
										/\\D/g,
										''
									))}
							/>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">First Name</div>
							<input
								id="admin-first-name"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.first_name}
							/>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Last Name</div>
							<input
								id="admin-last-name"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.last_name}
							/>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Salutation</div>
							<select
								id="admin-salutation"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.salutation}
							>
								<option value="">Select Salutation</option>
								{#each salutations as s}
									<option value={s.value}>{s.value}</option>
								{/each}
							</select>
						</div>

						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Department</div>
							<select
								id="admin-department"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.department}
							>
								<option value="">Select Department</option>
								{#each departments as d}
									<option value={d.value}>{d.value}</option>
								{/each}
							</select>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Job Level</div>
							<select
								id="admin-job-level"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.job_level}
							>
								<option value="">Select Job Level</option>
								{#each jobLevels as j}
									<option value={j.value}>{j.value}</option>
								{/each}
							</select>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Role</div>
							<input
								id="admin-role"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.role}
							/>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Branch</div>
							<select
								id="admin-branch"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								on:change={(e) => {
									const v = (e.target as HTMLSelectElement).value;
									form.branch_id = v ? Number(v) : undefined;
								}}
							>
								<option value="">Select Branch</option>
								{#each branches as b (b.id)}
									<option value={b.id} selected={form.branch_id === b.id}>{b.branch_name}</option>
								{/each}
							</select>
						</div>
						<div
							class="rounded border-b border-neutral-200 px-3 py-2 transition-colors hover:bg-gray-50 md:col-span-2 dark:border-gray-700 dark:hover:bg-gray-700"
						>
							<div class="text-xs text-neutral-500 dark:text-gray-400">Password (optional)</div>
							<input
								id="admin-password"
								type="password"
								class="w-full bg-transparent px-0 py-1 text-sm text-neutral-900 outline-none focus:ring-0 dark:text-white"
								bind:value={form.password}
								placeholder="Leave blank to keep current"
							/>
						</div>
					</div>

					<div class="mt-6 flex gap-3">
						<button
							on:click={save}
							class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
							>Save Changes</button
						>
						<button
							on:click={resetForm}
							class="rounded bg-gray-200 px-4 py-2 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
							>Reset</button
						>
					</div>
				</div>
			</div>
			{#if modalOpen}
				<div
					class="fixed inset-0 z-50 flex items-center justify-center p-4"
					style="background: rgba(0,0,0,0.2); backdrop-filter: blur(2px);"
				>
					<div
						class="h-auto max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-lg border bg-white p-4 shadow-2xl dark:border-gray-700 dark:bg-gray-800"
					>
						<div class="mb-4 flex items-center justify-between">
							<div class="text-xl font-semibold dark:text-white">{modalTitle}</div>
							<button
								class="rounded bg-gray-100 p-2 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600"
								on:click={closeModal}
								aria-label="Close"
							>
								<Icon icon="mdi:close" class="h-5 w-5" />
							</button>
						</div>
						{#if modalLoading}
							<div class="p-6 text-center text-neutral-600 dark:text-gray-300">Loading...</div>
						{:else if modalItems.length === 0}
							<div class="p-6 text-center text-neutral-600 dark:text-gray-300">No items</div>
						{:else}
							<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
								{#each modalItems as it (it.file.id)}
									<div class="rounded border p-3 dark:border-gray-700">
										{#if it.url}
											{#if (it.file.file_name || it.name || '').toLowerCase().endsWith('.pdf')}
												<iframe
													src={it.url}
													title={it.name}
													class="h-56 w-full rounded border bg-gray-50"
												></iframe>
											{:else}
												<img
													src={it.url}
													alt={it.name}
													class="h-56 w-full rounded bg-gray-100 object-contain dark:bg-gray-700"
												/>
											{/if}
										{:else}
											<div
												class="flex h-56 w-full items-center justify-center rounded bg-gray-100 dark:bg-gray-700"
											>
												<span class="text-gray-400">No Preview</span>
											</div>
										{/if}
										<div class="mt-2 flex items-center justify-between">
											<div class="text-sm font-medium text-neutral-900 dark:text-white">
												{it.name}
											</div>
											<div class="flex items-center gap-2">
												<button
													class="inline-flex items-center rounded bg-gray-100 px-2 py-1 text-xs hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
													on:click={() => downloadUrl(it.url)}
												>
													<Icon icon="mdi:download" class="h-4 w-4" />
													<span class="ml-1">Download</span>
													{#if it.file.file_name}
														<span class="ml-1 text-gray-600 dark:text-gray-400">
															({getFileType(it.file.file_name)})
														</span>
													{/if}
												</button>
											</div>
										</div>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			{/if}
		{/if}
	</div>
{/if}
