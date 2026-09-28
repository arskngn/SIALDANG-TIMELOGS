<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import type {
		CreateUser,
		UserResponse,
		BranchResponse,
		SystemOptionResponse,
		CivilStatus
	} from '$lib/api';
	import api from '$lib/api';
	import { listProvinces, listMuncities, listBarangays } from '@jobuntux/psgc';
	import UserCircle from 'virtual:icons/heroicons-solid/user-circle';
	import XMark from 'virtual:icons/heroicons-solid/x-mark';
	import Check from 'virtual:icons/heroicons-solid/check';
	import Icon from '@iconify/svelte';

	const isDev = import.meta.env.DEV;

	export let showModal = false;
	// Allow fields from both CreateUser and UserResponse
	export let user: Partial<CreateUser> & Partial<UserResponse> = {};
	export let isEditing = false;

	let branches: BranchResponse[] = [];
	let systemOptions: SystemOptionResponse[] = [];
	let selectedBranchId: number | undefined = undefined;
	let loadingBranches = true;
	let branchError = '';

	let roles: string[] = [];

	const civilStatusOptions: CivilStatus[] = [
		'Single',
		'Married',
		'Widowed',
		'Separated',
		'Divorced',
		'Annulled'
	];

	// --- PSGC address state ---
	// listProvinces() with no arg returns every province/HUC in the country
	const provinces = listProvinces();

	// Permanent address selections — *BarangayCode below stores the full
	// 10-digit `psgcCode`, not the library's 8-digit `brgyCode`, because
	// that's what the backend's permanent_address_psgc / current_address_psgc
	// fields validate against.
	let permProvinceCode = '';
	let permMunCityCode = '';
	let permBarangayCode = '';

	// Current address selections
	let currProvinceCode = '';
	let currMunCityCode = '';
	let currBarangayCode = '';

	let sameAsPermanent = false;

	// Tracks which user's saved address we've already loaded into the dropdowns,
	// so editing the dropdowns doesn't get overwritten by the derive-on-load
	// logic below (that was the "reverts while editing" bug).
	let initializedForUserId: number | null = null;

	$: permProvince = provinces.find((p) => p.provCode === permProvinceCode);
	$: permIsHUC = permProvince?.cityClass === 'HUC';
	$: permMuncities = permProvinceCode ? listMuncities(permProvinceCode) : [];
	$: permEffectiveMunCityCode = permIsHUC ? permMuncities[0]?.munCityCode : permMunCityCode;
	$: permBarangays = permEffectiveMunCityCode ? listBarangays(permEffectiveMunCityCode) : [];

	$: currProvince = provinces.find((p) => p.provCode === currProvinceCode);
	$: currIsHUC = currProvince?.cityClass === 'HUC';
	$: currMuncities = currProvinceCode ? listMuncities(currProvinceCode) : [];
	$: currEffectiveMunCityCode = currIsHUC ? currMuncities[0]?.munCityCode : currMunCityCode;
	$: currBarangays = currEffectiveMunCityCode ? listBarangays(currEffectiveMunCityCode) : [];

	// Mirror permanent -> current whenever the checkbox is on
	$: if (sameAsPermanent) {
		user.current_address_line = user.permanent_address_line;
		currProvinceCode = permProvinceCode;
		currMunCityCode = permMunCityCode;
		currBarangayCode = permBarangayCode;
	}

	function onPermProvinceChange() {
		permMunCityCode = '';
		permBarangayCode = '';
	}
	function onPermMunCityChange() {
		permBarangayCode = '';
	}
	function onCurrProvinceChange() {
		currMunCityCode = '';
		currBarangayCode = '';
	}
	function onCurrMunCityChange() {
		currBarangayCode = '';
	}

	// Full PSGC codes are 10 digits: RR (region) + PPP (province) + MM (city/mun)
	// + BBB (barangay). Slice a saved psgcCode to reconstruct the province and
	// municipality dropdown selections without a reverse-lookup call.
	function deriveFromPsgcCode(code?: string) {
		if (!code || code.length < 10) return { provinceCode: '', munCityCode: '' };
		return {
			provinceCode: code.slice(2, 5),
			munCityCode: code.slice(2, 7)
		};
	}

	onMount(async () => {
		// Load branches and options
		try {
			loadingBranches = true;
			branchError = '';
			const [bRes, sRes] = await Promise.all([
				api.branchAPI.getAllBranches(),
				api.systemOptionsAPI.getAll()
			]);
			branches = bRes;
			systemOptions = sRes;

			if (!branches || branches.length === 0) {
				branchError = 'No branches available';
			}
		} catch (e) {
			branchError = `Failed to load data: ${e}`;
			console.error('Error loading data:', e);
		} finally {
			loadingBranches = false;
		}

		// Load roles
		try {
			roles = await api.rolesAPI.getAll();
			if (!roles || roles.length === 0) roles = ['admin', 'manager', 'user'];
		} catch (e) {
			roles = ['admin', 'manager', 'user'];
		}
	});

	$: departments = systemOptions.filter((o) => o.category === 'Department');
	$: salutations = systemOptions.filter((o) => o.category === 'Salutation');
	$: jobLevels = systemOptions.filter((o) => o.category === 'Job Level');

	// Load branch + address into the form exactly once per user, when the edit
	// modal opens for them. Guarded by initializedForUserId so that clearing
	// permBarangayCode/currBarangayCode while the user picks a new dropdown
	// value does NOT re-trigger this and stomp their in-progress edit.
	$: if (showModal && isEditing && user.id && initializedForUserId !== user.id) {
		initializedForUserId = user.id as number;

		if (user.branch_id) {
			selectedBranchId = user.branch_id as number;
		}
		if (user.permanent_address_psgc) {
			const d = deriveFromPsgcCode(user.permanent_address_psgc);
			permProvinceCode = d.provinceCode;
			permMunCityCode = d.munCityCode;
			permBarangayCode = user.permanent_address_psgc;
		}
		if (user.current_address_psgc) {
			const d = deriveFromPsgcCode(user.current_address_psgc);
			currProvinceCode = d.provinceCode;
			currMunCityCode = d.munCityCode;
			currBarangayCode = user.current_address_psgc;
		}
	}

	// Reset form when opening for new user
	$: if (showModal && !isEditing) {
		selectedBranchId = undefined;
		initializedForUserId = null;
		permProvinceCode = '';
		permMunCityCode = '';
		permBarangayCode = '';
		currProvinceCode = '';
		currMunCityCode = '';
		currBarangayCode = '';
		sameAsPermanent = false;
	}

	const dispatch = createEventDispatcher();
	let error = '';

	function closeModal() {
		// Force a fresh re-derive next time this (or another) user is opened for
		// editing, so unsaved dropdown edits never leak into the next open.
		initializedForUserId = null;
		dispatch('close');
	}

	function handleSubmit() {
		error = '';
		const finalCurrentBarangayCode = sameAsPermanent ? permBarangayCode : currBarangayCode;
		const finalCurrentAddressLine = sameAsPermanent
			? user.permanent_address_line
			: user.current_address_line;

		if (!isEditing) {
			const required = [
				user.username,
				user.password,
				user.email,
				user.first_name,
				user.last_name,
				user.role,
				user.salutation,
				user.department,
				user.job_level,
				selectedBranchId,
				user.phone_number,
				user.civil_status,
				user.birthdate,
				user.permanent_address_line,
				permBarangayCode,
				finalCurrentAddressLine,
				finalCurrentBarangayCode
			];
			const allFilled = required.every((v) =>
				typeof v === 'number' ? v !== undefined && v !== null : !!String(v || '').trim()
			);
			if (!allFilled) {
				error = 'Please fill out all fields';
				return;
			}
		}
		const payload = {
			...user,
			branch_id: selectedBranchId,
			permanent_address_psgc: permBarangayCode,
			current_address_psgc: finalCurrentBarangayCode,
			current_address_line: finalCurrentAddressLine
		};
		if (isDev) console.debug('UserModal submit payload:', payload);
		dispatch('submit', payload);
	}
</script>

{#if showModal}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-4"
		style="background: rgba(0, 0, 0, 0.1); backdrop-filter: blur(2px);"
	>
		<div
			class="flex flex-col h-auto max-h-[90vh] w-full max-w-3xl rounded-lg border bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800"
		>
			<div class="flex-none px-6 py-4 border-b dark:border-gray-700">
				<div class="flex items-center gap-3">
					<UserCircle class="h-8 w-8 text-blue-500" />
					<h2 class="text-2xl font-bold dark:text-white">
						{isEditing ? 'Edit User' : 'Create New User'}
					</h2>
				</div>
			</div>
			<div class="flex-1 overflow-y-auto p-6">
				<form id="userForm" on:submit|preventDefault={handleSubmit}>
				{#if error}
					<div
						class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700 dark:border-red-600 dark:bg-red-900 dark:text-red-200"
					>
						{error}
					</div>
				{/if}
				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="username"
								>Username</label
							>
							<input
								id="username"
								type="text"
								bind:value={user.username}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							/>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="password"
								>Password</label
							>
							<input
								id="password"
								type="password"
								bind:value={user.password}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								placeholder={isEditing ? 'Leave blank to keep current password' : ''}
								required={!isEditing}
							/>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="email">Email</label>
							<input
								id="email"
								type="email"
								bind:value={user.email}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							/>
						</div>

						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="first_name"
								>First Name</label
							>
							<input
								id="first_name"
								type="text"
								bind:value={user.first_name}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							/>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="last_name"
								>Last Name</label
							>
							<input
								id="last_name"
								type="text"
								bind:value={user.last_name}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							/>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="phone_number"
								>Phone Number</label
							>
							<input
								id="phone_number"
								type="tel"
								bind:value={user.phone_number}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							/>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="role">Role</label>
							<select
								id="role"
								bind:value={user.role}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							>
								{#each roles as r}
									<option value={r}>{r}</option>
								{/each}
							</select>
						</div>
					</div>
					<div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="branch">Branch</label>
							{#if loadingBranches}
								<div class="text-sm text-gray-500">Loading branches...</div>
							{:else if branchError}
								<div class="text-sm text-red-600">{branchError}</div>
							{:else}
								<select
									id="branch"
									bind:value={selectedBranchId}
									on:change={(e) =>
										(selectedBranchId = Number((e.target as HTMLSelectElement).value))}
									class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
									required
								>
									<option value="">Select Branch</option>
									{#each branches as b (b.id)}
										<option value={b.id}>{b.branch_name}</option>
									{/each}
								</select>
							{/if}
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="salutation"
								>Salutation</label
							>
							<select
								id="salutation"
								bind:value={user.salutation}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							>
								<option value="">Select Salutation</option>
								{#each salutations as s}
									<option value={s.value}>{s.value}</option>
								{/each}
							</select>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="department"
								>Department</label
							>
							<select
								id="department"
								bind:value={user.department}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							>
								<option value="">Select Department</option>
								{#each departments as d}
									<option value={d.value}>{d.value}</option>
								{/each}
							</select>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="job_level"
								>Job Level</label
							>
							<select
								id="job_level"
								bind:value={user.job_level}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							>
								<option value="">Select Job Level</option>
								{#each jobLevels as j}
									<option value={j.value}>{j.value}</option>
								{/each}
							</select>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="civil_status"
								>Civil Status</label
							>
							<select
								id="civil_status"
								bind:value={user.civil_status}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							>
								<option value="">Select Civil Status</option>
								{#each civilStatusOptions as c}
									<option value={c}>{c}</option>
								{/each}
							</select>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="birthdate"
								>Birthdate</label
							>
							<input
								id="birthdate"
								type="date"
								bind:value={user.birthdate}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							/>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="emp_start_date"
								>Employment Start Date</label
							>
							<input
								id="emp_start_date"
								type="date"
								bind:value={user.emp_start_date}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
							/>
						</div>
						<div class="mb-3">
							<label class="mb-2 block text-sm font-bold text-gray-700" for="emp_end_date"
								>Employment End Date</label
							>
							<input
								id="emp_end_date"
								type="date"
								bind:value={user.emp_end_date}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
							/>
						</div>
					</div>
				</div>

				<!-- Permanent Address -->
				<div class="mt-6 border-t pt-6 dark:border-gray-700">
					<h3 class="mb-4 text-lg font-bold text-gray-800 dark:text-white">Permanent Address</h3>
					<div class="mb-3">
						<label
							class="mb-2 block text-sm font-bold text-gray-700"
							for="permanent_address_line">House No./Street</label
						>
						<input
							id="permanent_address_line"
							type="text"
							bind:value={user.permanent_address_line}
							class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
							required
						/>
					</div>
					<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
						<div>
							<label class="mb-2 block text-sm font-bold text-gray-700" for="perm_province"
								>Province</label
							>
							<select
								id="perm_province"
								bind:value={permProvinceCode}
								on:change={onPermProvinceChange}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								required
							>
								<option value="">Select Province</option>
								{#each provinces as p (p.provCode)}
									<option value={p.provCode}
										>{p.provName}{p.cityClass === 'HUC' ? ' (HUC)' : ''}</option
									>
								{/each}
							</select>
						</div>
						<div>
							<label class="mb-2 block text-sm font-bold text-gray-700" for="perm_muncity"
								>City/Municipality</label
							>
							<select
								id="perm_muncity"
								bind:value={permMunCityCode}
								on:change={onPermMunCityChange}
								disabled={!permProvinceCode || permMuncities.length <= 1}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none disabled:bg-gray-100 disabled:text-gray-400"
								required
							>
								<option value="">Select City/Municipality</option>
								{#each permMuncities as m (m.munCityCode)}
									<option value={m.munCityCode}>{m.munCityName}</option>
								{/each}
							</select>
						</div>
						<div>
							<label class="mb-2 block text-sm font-bold text-gray-700" for="perm_barangay"
								>Barangay</label
							>
							<select
								id="perm_barangay"
								bind:value={permBarangayCode}
								disabled={!permEffectiveMunCityCode}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none disabled:bg-gray-100 disabled:text-gray-400"
								required
							>
								<option value="">Select Barangay</option>
								{#each permBarangays as b (b.psgcCode)}
									<option value={b.psgcCode}
										>{b.brgyOldName ? `${b.brgyName} (${b.brgyOldName})` : b.brgyName}</option
									>
								{/each}
							</select>
						</div>
					</div>
				</div>

				<div class="mt-4">
					<label
						class="inline-flex items-center gap-2 text-sm font-bold text-gray-700 dark:text-gray-300"
					>
						<input type="checkbox" bind:checked={sameAsPermanent} />
						Current address is the same as permanent address
					</label>
				</div>

				<!-- Current Address -->
				<div class="mt-4 border-t pt-6 dark:border-gray-700">
					<h3 class="mb-4 text-lg font-bold text-gray-800 dark:text-white">Current Address</h3>
					<div class="mb-3">
						<label class="mb-2 block text-sm font-bold text-gray-700" for="current_address_line"
							>House No./Street</label
						>
						<input
							id="current_address_line"
							type="text"
							bind:value={user.current_address_line}
							disabled={sameAsPermanent}
							class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none disabled:bg-gray-100 disabled:text-gray-400"
							required={!sameAsPermanent}
						/>
					</div>
					<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
						<div>
							<label class="mb-2 block text-sm font-bold text-gray-700" for="curr_province"
								>Province</label
							>
							<select
								id="curr_province"
								bind:value={currProvinceCode}
								on:change={onCurrProvinceChange}
								disabled={sameAsPermanent}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none disabled:bg-gray-100 disabled:text-gray-400"
								required={!sameAsPermanent}
							>
								<option value="">Select Province</option>
								{#each provinces as p (p.provCode)}
									<option value={p.provCode}
										>{p.provName}{p.cityClass === 'HUC' ? ' (HUC)' : ''}</option
									>
								{/each}
							</select>
						</div>
						<div>
							<label class="mb-2 block text-sm font-bold text-gray-700" for="curr_muncity"
								>City/Municipality</label
							>
							<select
								id="curr_muncity"
								bind:value={currMunCityCode}
								on:change={onCurrMunCityChange}
								disabled={sameAsPermanent || !currProvinceCode || currMuncities.length <= 1}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none disabled:bg-gray-100 disabled:text-gray-400"
								required={!sameAsPermanent}
							>
								<option value="">Select City/Municipality</option>
								{#each currMuncities as m (m.munCityCode)}
									<option value={m.munCityCode}>{m.munCityName}</option>
								{/each}
							</select>
						</div>
						<div>
							<label class="mb-2 block text-sm font-bold text-gray-700" for="curr_barangay"
								>Barangay</label
							>
							<select
								id="curr_barangay"
								bind:value={currBarangayCode}
								disabled={sameAsPermanent || !currEffectiveMunCityCode}
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none disabled:bg-gray-100 disabled:text-gray-400"
								required={!sameAsPermanent}
							>
								<option value="">Select Barangay</option>
								{#each currBarangays as b (b.psgcCode)}
									<option value={b.psgcCode}
										>{b.brgyOldName ? `${b.brgyName} (${b.brgyOldName})` : b.brgyName}</option
									>
								{/each}
							</select>
						</div>
					</div>
				</div>
			</form>
			</div>

			<div class="flex-none px-6 py-4 border-t bg-gray-50 dark:bg-gray-800/50 dark:border-gray-700 flex justify-end">
				<button
					type="button"
					on:click={closeModal}
					class="mr-2 inline-flex items-center rounded bg-gray-300 px-4 py-2 font-bold text-gray-800 hover:bg-gray-400"
				>
					<XMark class="mr-2 h-5 w-5" />
					Cancel
				</button>
				<button
					type="submit"
					form="userForm"
					class="inline-flex items-center rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
				>
					<Check class="mr-2 h-5 w-5" />
					{isEditing ? 'Save Changes' : 'Create User'}
				</button>
			</div>
		</div>
	</div>
{/if}