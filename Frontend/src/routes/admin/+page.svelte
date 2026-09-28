<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { isAdmin, isAuthenticated } from '$lib/stores';
	import api from '$lib/api';
	import type {
		CreateProject,
		UpdateProject,
		CreateBranch,
		UpdateBranch,
		ProjectResponse,
		BranchResponse,
		UserResponse
	} from '$lib/api';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	let admin = false;
	let authed = false;
	const unsub = isAdmin.subscribe((v) => (admin = v));
	const unsubAuth = isAuthenticated.subscribe((v) => (authed = v));

	onDestroy(() => {
		unsub();
		unsubAuth();
	});

	onMount(async () => {
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}
		if (!admin) {
			return;
		}
		await loadData();
	});

	async function loadData() {
		projects = await api.projectAPI.getAllProjects();
		branches = await api.branchAPI.getAllBranches();
		users = await api.userAPI.getAllUsers();
	}

	let projects: ProjectResponse[] = [];
	let branches: BranchResponse[] = [];
	let users: UserResponse[] = [];
	let eligibleUsers: UserResponse[] = [];
	$: eligibleUsers = users;

	let newProject: CreateProject = {
		project_name: '',
		description: '',
		manager_id: undefined,
		branch_id: undefined,
		status: 'Pending'
	};

	let editingProject: UpdateProject = {};
	let selectedProjectId: number | null = null;

	let newBranch: CreateBranch = {
		branch_name: '',
		branch_address: ''
	};

	let editingBranch: UpdateBranch = {};
	let selectedBranchId: number | null = null;

	function getBranchName(id?: number) {
		if (!id) return 'Unassigned';
		const b = branches.find((x) => x.id === id);
		return b ? b.branch_name : String(id);
	}

	function getUserName(id?: number) {
		if (!id) return 'Unassigned';
		const u = users.find((x) => x.id === id);
		return u ? u.username : String(id);
	}

	async function createProject() {
		const p = await api.projectAPI.createProject(newProject);
		projects = [p, ...projects];
		newProject = { project_name: '', description: '', status: 'Pending' };
	}

	async function updateProject() {
		if (selectedProjectId == null) return;
		const p = await api.projectAPI.updateProject(selectedProjectId, editingProject);
		projects = projects.map((x) => (x.id === p.id ? p : x));
		selectedProjectId = null;
		editingProject = {};
	}

	async function deleteProject(id: number) {
		await api.projectAPI.deleteProject(id);
		projects = projects.filter((x) => x.id !== id);
	}

	async function createBranch() {
		const b = await api.branchAPI.createBranch(newBranch);
		branches = [b, ...branches];
		newBranch = { branch_name: '', branch_address: '' };
	}

	async function updateBranch() {
		if (selectedBranchId == null) return;
		const b = await api.branchAPI.updateBranch(selectedBranchId, editingBranch);
		branches = branches.map((x) => (x.id === b.id ? b : x));
		selectedBranchId = null;
		editingBranch = {};
	}

	async function deleteBranch(id: number) {
		await api.branchAPI.deleteBranch(id);
		branches = branches.filter((x) => x.id !== id);
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
		<h1 class="mb-6 text-2xl font-semibold dark:text-white">Admin: Projects and Branches</h1>

		<div class="grid grid-cols-1 gap-8 md:grid-cols-2">
			<div class="rounded bg-white p-6 shadow dark:bg-gray-800">
				<h2 class="mb-4 text-xl font-semibold dark:text-white">Projects</h2>
				<div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
					<input
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
						placeholder="Name"
						bind:value={newProject.project_name}
					/>
					<input
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
						placeholder="Description"
						bind:value={newProject.description}
					/>
					<select
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
						on:change={(e) => {
							const v = (e.target as HTMLSelectElement).value;
							newProject.manager_id = v ? Number(v) : undefined;
						}}
					>
						<option value="">Select Manager</option>
						{#each eligibleUsers as u (u.id)}
							<option value={u.id}>{u.username}</option>
						{/each}
					</select>
					<select
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
						on:change={(e) => {
							const v = (e.target as HTMLSelectElement).value;
							newProject.branch_id = v ? Number(v) : undefined;
						}}
					>
						<option value="">Select Branch</option>
						{#each branches as b (b.id)}
							<option value={b.id}>{b.branch_name}</option>
						{/each}
					</select>
					<select
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
						bind:value={newProject.status}
					>
						<option value="Pending">Pending</option>
						<option value="Ongoing">Ongoing</option>
						<option value="Completed">Completed</option>
					</select>
				</div>
				<button
					class="rounded bg-blue-600 px-3 py-2 text-white hover:bg-blue-700"
					on:click={createProject}>Create Project</button
				>

				<div class="mt-6 space-y-3">
					{#each projects as p (p.id)}
						<div class="rounded border p-3 dark:border-gray-700">
							<div class="flex items-center justify-between">
								<div class="dark:text-white">
									<div class="font-medium">{p.project_name}</div>
									<div class="text-sm text-gray-600 dark:text-gray-300">Status: {p.status}</div>
									<div class="text-sm text-gray-600 dark:text-gray-300">
										Branch: {getBranchName(p.branch_id)}
									</div>
									<div class="text-sm text-gray-600 dark:text-gray-300">
										Manager: {getUserName(p.manager_id)}
									</div>
								</div>
								<div class="flex gap-2">
									<button
										class="rounded bg-gray-600 px-3 py-2 text-white hover:bg-gray-700"
										on:click={() => {
											selectedProjectId = p.id;
											editingProject = {
												project_name: p.project_name,
												description: p.description,
												manager_id: p.manager_id,
												branch_id: p.branch_id,
												status: p.status
											};
										}}>Edit</button
									>
									<button
										class="rounded bg-red-600 px-3 py-2 text-white hover:bg-red-700"
										on:click={() => deleteProject(p.id)}>Delete</button
									>
								</div>
							</div>
						</div>
					{/each}
				</div>

				{#if selectedProjectId !== null}
					<div class="mt-6 rounded bg-gray-50 p-4 dark:bg-gray-700">
						<h3 class="mb-3 font-semibold dark:text-white">Update Project</h3>
						<div class="mb-3 grid grid-cols-1 gap-3 md:grid-cols-2">
							<input
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								placeholder="Name"
								bind:value={editingProject.project_name}
							/>
							<input
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								placeholder="Description"
								bind:value={editingProject.description}
							/>
							<select
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								on:change={(e) => {
									const v = (e.target as HTMLSelectElement).value;
									editingProject.manager_id = v ? Number(v) : undefined;
								}}
							>
								<option value="">Select Manager</option>
								{#each eligibleUsers as u (u.id)}
									<option value={u.id} selected={editingProject.manager_id === u.id}
										>{u.username}</option
									>
								{/each}
							</select>
							<select
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								on:change={(e) => {
									const v = (e.target as HTMLSelectElement).value;
									editingProject.branch_id = v ? Number(v) : undefined;
								}}
							>
								<option value="">Select Branch</option>
								{#each branches as b (b.id)}
									<option value={b.id} selected={editingProject.branch_id === b.id}
										>{b.branch_name}</option
									>
								{/each}
							</select>
							<select
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								bind:value={editingProject.status}
							>
								<option value="Pending">Pending</option>
								<option value="Ongoing">Ongoing</option>
								<option value="Completed">Completed</option>
							</select>
						</div>
						<button
							class="rounded bg-blue-600 px-3 py-2 text-white hover:bg-blue-700"
							on:click={updateProject}>Save</button
						>
					</div>
				{/if}
			</div>

			<div class="rounded bg-white p-6 shadow dark:bg-gray-800">
				<h2 class="mb-4 text-xl font-semibold dark:text-white">Branches</h2>
				<div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
					<input
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
						placeholder="Name"
						bind:value={newBranch.branch_name}
					/>
					<input
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
						placeholder="Address"
						bind:value={newBranch.branch_address}
					/>
				</div>
				<button
					class="rounded bg-blue-600 px-3 py-2 text-white hover:bg-blue-700"
					on:click={createBranch}>Create Branch</button
				>

				<div class="mt-6 space-y-3">
					{#each branches as b (b.id)}
						<div class="rounded border p-3 dark:border-gray-700">
							<div class="flex items-center justify-between">
								<div class="dark:text-white">
									<div class="font-medium">{b.branch_name}</div>
									<div class="text-sm text-gray-600 dark:text-gray-300">{b.branch_address}</div>
								</div>
								<div class="flex gap-2">
									<button
										class="rounded bg-gray-600 px-3 py-2 text-white hover:bg-gray-700"
										on:click={() => {
											selectedBranchId = b.id;
											editingBranch = {
												branch_name: b.branch_name,
												branch_address: b.branch_address
											};
										}}>Edit</button
									>
									<button
										class="rounded bg-red-600 px-3 py-2 text-white hover:bg-red-700"
										on:click={() => deleteBranch(b.id)}>Delete</button
									>
								</div>
							</div>
						</div>
					{/each}
				</div>

				{#if selectedBranchId !== null}
					<div class="mt-6 rounded bg-gray-50 p-4 dark:bg-gray-700">
						<h3 class="mb-3 font-semibold dark:text-white">Update Branch</h3>
						<div class="mb-3 grid grid-cols-1 gap-3 md:grid-cols-2">
							<input
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								placeholder="Name"
								bind:value={editingBranch.branch_name}
							/>
							<input
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								placeholder="Address"
								bind:value={editingBranch.branch_address}
							/>
						</div>
						<button
							class="rounded bg-blue-600 px-3 py-2 text-white hover:bg-blue-700"
							on:click={updateBranch}>Save</button
						>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
