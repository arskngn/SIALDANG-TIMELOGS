<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import api, {
		type ProjectResponse,
		type CreateProject,
		type UpdateProject,
		type UserResponse,
		type CustomerResponse,
		type CreateCustomer,
		type UpdateCustomer,
		type ProjectUser,
		type CreateProjectResource,
		type UpdateProjectResource,
		FTE
	} from '$lib/api';
	import { isAuthenticated, isAdmin } from '$lib/stores';
	import Icon from '@iconify/svelte';
	import ConfirmModal from '$lib/ConfirmModal.svelte';

	// Countries list
	const countries = [
		'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 'Argentina', 'Armenia', 'Australia', 'Austria', 'Azerbaijan',
		'Bahamas', 'Bahrain', 'Bangladesh', 'Barbados', 'Belarus', 'Belgium', 'Belize', 'Benin', 'Bhutan', 'Bolivia', 'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Brunei', 'Bulgaria', 'Burkina Faso', 'Burundi',
		'Cambodia', 'Cameroon', 'Canada', 'Cape Verde', 'Central African Republic', 'Chad', 'Chile', 'China', 'Colombia', 'Comoros', 'Congo', 'Costa Rica', 'Croatia', 'Cuba', 'Cyprus', 'Czech Republic',
		'Democratic Republic of Congo', 'Denmark', 'Djibouti', 'Dominica', 'Dominican Republic',
		'East Timor', 'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea', 'Eritrea', 'Estonia', 'Ethiopia',
		'Fiji', 'Finland', 'France',
		'Gabon', 'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Grenada', 'Guatemala', 'Guinea', 'Guinea-Bissau', 'Guyana',
		'Haiti', 'Honduras', 'Hungary',
		'Iceland', 'India', 'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Israel', 'Italy', 'Ivory Coast',
		'Jamaica', 'Japan', 'Jordan',
		'Kazakhstan', 'Kenya', 'Kiribati', 'Kuwait', 'Kyrgyzstan',
		'Laos', 'Latvia', 'Lebanon', 'Lesotho', 'Liberia', 'Libya', 'Liechtenstein', 'Lithuania', 'Luxembourg',
		'Madagascar', 'Malawi', 'Malaysia', 'Maldives', 'Mali', 'Malta', 'Marshall Islands', 'Mauritania', 'Mauritius', 'Mexico', 'Micronesia', 'Moldova', 'Monaco', 'Mongolia', 'Montenegro', 'Morocco', 'Mozambique', 'Myanmar',
		'Namibia', 'Nauru', 'Nepal', 'Netherlands', 'New Zealand', 'Nicaragua', 'Niger', 'Nigeria', 'North Korea', 'North Macedonia', 'Norway',
		'Oman',
		'Pakistan', 'Palau', 'Palestine', 'Panama', 'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines', 'Poland', 'Portugal',
		'Qatar',
		'Romania', 'Russia', 'Rwanda',
		'Saint Kitts and Nevis', 'Saint Lucia', 'Saint Vincent and the Grenadines', 'Samoa', 'San Marino', 'Sao Tome and Principe', 'Saudi Arabia', 'Senegal', 'Serbia', 'Seychelles', 'Sierra Leone', 'Singapore', 'Slovakia', 'Slovenia', 'Solomon Islands', 'Somalia', 'South Africa', 'South Korea', 'South Sudan', 'Spain', 'Sri Lanka', 'Sudan', 'Suriname', 'Sweden', 'Switzerland', 'Syria',
		'Taiwan', 'Tajikistan', 'Tanzania', 'Thailand', 'The Bahamas', 'Togo', 'Tonga', 'Trinidad and Tobago', 'Tunisia', 'Turkey', 'Turkmenistan', 'Tuvalu',
		'Uganda', 'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States', 'Uruguay', 'Uzbekistan',
		'Vanuatu', 'Vatican City', 'Venezuela', 'Vietnam',
		'Yemen',
		'Zambia', 'Zimbabwe'
	].sort();

	let authed = false;
	let admin = false;
	let loading = false;
	
	// Data
	let customers: CustomerResponse[] = [];
	let projects: ProjectResponse[] = [];
	let projectResources: ProjectUser[] = [];
	let allUsers: UserResponse[] = [];

	// Selection State
	let selectedCustomerId: number | null = null;
	let selectedProjectIds: number[] = [];

	// Filter & Sort State
	let searchTermCustomer = '';
	let sortFieldCustomer: 'customer_name' | 'status' = 'customer_name';
	let sortDirectionCustomer: 'asc' | 'desc' = 'asc';

	let searchTermProject = '';
	let sortFieldProject: 'project_name' | 'status' | 'start_date' = 'project_name';
	let sortDirectionProject: 'asc' | 'desc' = 'asc';

	// Pagination State
	let customerPage = 1;
	let projectPage = 1;
	let resourcePage = 1;

	// Per-section page sizes
	const customerPageSize = 2;
	const projectPageSize = 2;
	const resourcePageSize = 10;

	// Modals State
	let showCustomerModal = false;
	let showProjectModal = false;
	let showResourceModal = false;
	
	// Edit/Delete State
	let editingCustomer: CustomerResponse | null = null;
	let editingProject: ProjectResponse | null = null;
	
	// Delete Confirmation
	let deleteType: 'customer' | 'project' | 'resource' | null = null;
	let deleteId: number | null = null;
	let deleteSecondaryId: number | null = null; // For resource removal (user_id)
	let deleteModalOpen = false;
	let deleteMessage = '';

	// Forms
	let customerForm: CreateCustomer = { 
		customer_name: '', 
		description: '',
		customer_location: '', 
		status: 'Active'
	};
	let projectForm: CreateProject = {
		project_name: '',
		description: '',
		customer_id: undefined,
		status: 'Pending',
		manager_id: undefined
	};
	let resourceFormIds: number[] = []; // Selected user IDs for adding resources
	let resourceFTEs: Record<number, FTE> = {}; // Chosen FTE per selected user ID (Add Resource modal)

	// Derived
	$: selectedCustomer = customers.find(c => c.id === selectedCustomerId);
	$: singleSelectedProjectId = selectedProjectIds.length === 1 ? selectedProjectIds[0] : null;
	$: singleSelectedProject = singleSelectedProjectId ? projects.find(p => p.id === singleSelectedProjectId) : undefined;

	// Planned hours: (days between start/end ÷ 7) weeks × 40 hrs/week × FTE%
	const WORK_HOURS_PER_WEEK = 40;
	function calculatePlannedHours(project: ProjectResponse | undefined, fte: number | undefined | null): number | null {
		if (!project?.start_date || !project?.end_date || fte == null) return null;
		const start = new Date(project.start_date);
		const end = new Date(project.end_date);
		const days = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);
		if (!isFinite(days) || days < 0) return null;
		const weeks = days / 7;
		return weeks * WORK_HOURS_PER_WEEK * (fte / 100);
	}

	// Pagination Logic
	function paginate<T>(items: T[], page: number, size: number): T[] {
		const start = (page - 1) * size;
		return items.slice(start, start + size);
	}

	// Svelte action to reflect the "some but not all selected" state on a checkbox
	function setIndeterminate(node: HTMLInputElement, value: boolean) {
		node.indeterminate = value;
		return {
			update(value: boolean) {
				node.indeterminate = value;
			}
		};
	}

	// Filter & Sort Logic
	function filterAndSort<T>(items: T[], term: string, sortField: string, sortDirection: 'asc' | 'desc', searchFields: string[]): T[] {
		let result = [...items]; // Copy to avoid mutating original
		
		// Filter
		if (term) {
			const lowerTerm = term.toLowerCase();
			result = result.filter(item => 
				searchFields.some(field => {
					const val = (item as any)[field];
					return val && String(val).toLowerCase().includes(lowerTerm);
				})
			);
		}
		
		// Sort
		result.sort((a, b) => {
			const valA = (a as any)[sortField] || '';
			const valB = (b as any)[sortField] || '';
			
			if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
			if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
			return 0;
		});
		
		return result;
	}

	$: filteredCustomers = filterAndSort(customers, searchTermCustomer, sortFieldCustomer, sortDirectionCustomer, ['customer_name', 'status', 'description']);
	$: filteredProjects = filterAndSort(projects, searchTermProject, sortFieldProject, sortDirectionProject, ['project_name', 'status', 'description']);

	$: allProjectsSelected = filteredProjects.length > 0 && filteredProjects.every(p => selectedProjectIds.includes(p.id));
	$: someProjectsSelected = selectedProjectIds.length > 0 && !allProjectsSelected;

	$: pagedCustomers = paginate(filteredCustomers, customerPage, customerPageSize);
	$: pagedProjects = paginate(filteredProjects, projectPage, projectPageSize);
	$: pagedResources = paginate(projectResources, resourcePage, resourcePageSize);

	$: customerPageCount = Math.ceil(filteredCustomers.length / customerPageSize) || 1;
	$: projectPageCount = Math.ceil(filteredProjects.length / projectPageSize) || 1;
	$: resourcePageCount = Math.ceil(projectResources.length / resourcePageSize) || 1;

	// Auth & Init
	const unsub = isAuthenticated.subscribe((v) => (authed = v));
	const unsubAdmin = isAdmin.subscribe((v) => (admin = v));
	import { isProjectManager } from '$lib/stores';
	let manager = false;
	const unsubManager = isProjectManager.subscribe((v) => (manager = v));

	onMount(async () => {
		if (!authed) {
			await goto(resolve('/login'));
			return;
		}
		// Always load customers - backend handles permissions and filtering
		await loadCustomers();
		await loadAllUsers(); // For resource assignment
	});

	// Loaders
	async function loadCustomers() {
		try {
			customers = await api.customerAPI.getAllCustomers();
		} catch (e) {
			console.error('Failed to load customers', e);
		}
	}

	async function loadProjects(customerId: number) {
		try {
			projects = await api.projectAPI.getAllProjects(customerId);
			// Drop any selected project IDs that no longer exist in the loaded list
			const validIds = new Set(projects.map(p => p.id));
			const stillValid = selectedProjectIds.filter(id => validIds.has(id));
			if (stillValid.length !== selectedProjectIds.length) {
				selectedProjectIds = stillValid;
				await loadResourcesForSelectedProjects();
			}
		} catch (e) {
			console.error('Failed to load projects', e);
			projects = [];
		}
	}

	// Loads resources for every selected project and merges them, de-duplicated by user id
	async function loadResourcesForSelectedProjects() {
		if (selectedProjectIds.length === 0) {
			projectResources = [];
			return;
		}
		try {
			const results = await Promise.all(
				selectedProjectIds.map(id => api.projectAPI.getProjectUsers(id))
			);
			const merged: ProjectUser[] = [];
			const seen = new Set<number>();
			for (const list of results) {
				for (const r of list) {
					if (!seen.has(r.id)) {
						seen.add(r.id);
						merged.push(r);
					}
				}
			}
			projectResources = merged;
		} catch (e) {
			console.error('Failed to load resources', e);
			projectResources = [];
		}
	}

	async function loadAllUsers() {
		try {
			allUsers = await api.userAPI.getAllUsers();
		} catch (e) {
			console.error('Failed to load users', e);
		}
	}

	// Customer Actions
	function selectCustomer(id: number) {
		selectedCustomerId = id;
		selectedProjectIds = [];
		projectResources = [];
		projectPage = 1;
		resourcePage = 1;
		loadProjects(id);
	}

	function openAddCustomer() {
		editingCustomer = null;
		customerForm = { customer_name: '', description: '', customer_location: '', status: 'Active' };
		showCustomerModal = true;
	}

	function openEditCustomer(c: CustomerResponse) {
		editingCustomer = c;
		customerForm = {
			customer_name: c.customer_name,
			description: c.description || '',
			customer_location: c.customer_location || '',
			status: c.status || 'Active'
		};
		showCustomerModal = true;
	}

	async function saveCustomer() {
		try {
			const payload = { ...customerForm };
			if (editingCustomer) {
				await api.customerAPI.updateCustomer(editingCustomer.id, payload);
			} else {
				await api.customerAPI.createCustomer(payload);
			}
			showCustomerModal = false;
			await loadCustomers();
		} catch (e) {
			alert('Failed to save customer');
		}
	}

	function confirmDeleteCustomer(c: CustomerResponse) {
		deleteType = 'customer';
		deleteId = c.id;
		deleteMessage = `Delete customer '${c.customer_name}'? Projects associated with this customer might be affected.`;
		deleteModalOpen = true;
	}

	// Project Actions
	async function toggleProjectSelection(id: number) {
		if (selectedProjectIds.includes(id)) {
			selectedProjectIds = selectedProjectIds.filter(pid => pid !== id);
		} else {
			selectedProjectIds = [...selectedProjectIds, id];
		}
		resourcePage = 1;
		await loadResourcesForSelectedProjects();
	}

	async function toggleSelectAllProjects() {
		const filteredIds = filteredProjects.map(p => p.id);
		if (allProjectsSelected) {
			const idsToRemove = new Set(filteredIds);
			selectedProjectIds = selectedProjectIds.filter(id => !idsToRemove.has(id));
		} else {
			selectedProjectIds = Array.from(new Set([...selectedProjectIds, ...filteredIds]));
		}
		resourcePage = 1;
		await loadResourcesForSelectedProjects();
	}

	function openAddProject() {
		if (!selectedCustomerId) return;
		editingProject = null;
		projectForm = {
			project_name: '',
			description: '',
			customer_id: selectedCustomerId,
			status: 'Pending',
			start_date: new Date().toISOString().split('T')[0],
			end_date: new Date().toISOString().split('T')[0]
		};
		showProjectModal = true;
	}

	function openEditProject(p: ProjectResponse) {
		editingProject = p;
		projectForm = {
			project_name: p.project_name,
			description: p.description,
			customer_id: p.customer_id,
			status: p.status,
			start_date: p.start_date ? p.start_date.split('T')[0] : undefined,
			end_date: p.end_date ? p.end_date.split('T')[0] : undefined
		};
		showProjectModal = true;
	}

	async function saveProject() {
		try {
			if (editingProject) {
				await api.projectAPI.updateProject(editingProject.id, projectForm);
			} else {
				await api.projectAPI.createProject(projectForm);
			}
			showProjectModal = false;
			if (selectedCustomerId) await loadProjects(selectedCustomerId);
		} catch (e) {
			alert('Failed to save project');
		}
	}

	function confirmDeleteProject(p: ProjectResponse) {
		deleteType = 'project';
		deleteId = p.id;
		deleteMessage = `Delete project '${p.project_name}'?`;
		deleteModalOpen = true;
	}

	// Resource Actions
	function openAddResource() {
		resourceFormIds = [];
		resourceFTEs = {};
		showResourceModal = true;
	}

	function toggleResourceSelection(userId: number) {
		if (resourceFormIds.includes(userId)) {
			resourceFormIds = resourceFormIds.filter(id => id !== userId);
			const updated = { ...resourceFTEs };
			delete updated[userId];
			resourceFTEs = updated;
		} else {
			resourceFormIds = [...resourceFormIds, userId];
			resourceFTEs = { ...resourceFTEs, [userId]: FTE.FULL_TIME };
		}
	}

	async function saveResources() {
		if (!singleSelectedProjectId) return;
		try {
			for (const uid of resourceFormIds) {
				await api.projectAPI.addResource({
					user_id: uid,
					project_id: singleSelectedProjectId,
					role_in_project: 'Member',
					fte: resourceFTEs[uid] ?? FTE.FULL_TIME
				});
			}
			showResourceModal = false;
			resourceFormIds = [];
			resourceFTEs = {};
			await loadResourcesForSelectedProjects();
		} catch (e) {
			alert('Failed to add resources');
		}
	}

	async function updateResourceFte(r: ProjectUser, fte: FTE) {
		if (!singleSelectedProjectId) return;
		try {
			await api.projectAPI.updateResource(singleSelectedProjectId, r.id, { fte });
			await loadResourcesForSelectedProjects();
		} catch (e) {
			alert('Failed to update FTE');
		}
	}

	function confirmRemoveResource(r: ProjectUser) {
		if (!singleSelectedProjectId) return;
		deleteType = 'resource';
		deleteId = singleSelectedProjectId; // Project ID
		deleteSecondaryId = r.id; // User ID
		deleteMessage = `Remove '${r.username}' from project?`;
		deleteModalOpen = true;
	}

	// Generic Delete Execution
	async function performDelete() {
		if (!deleteId) return;
		try {
			if (deleteType === 'customer') {
				await api.customerAPI.deleteCustomer(deleteId);
				if (selectedCustomerId === deleteId) {
					selectedCustomerId = null;
					projects = [];
					selectedProjectIds = [];
					projectResources = [];
				}
				await loadCustomers();
			} else if (deleteType === 'project') {
				await api.projectAPI.deleteProject(deleteId);
				if (selectedProjectIds.includes(deleteId)) {
					selectedProjectIds = selectedProjectIds.filter(id => id !== deleteId);
				}
				if (selectedCustomerId) await loadProjects(selectedCustomerId);
				await loadResourcesForSelectedProjects();
			} else if (deleteType === 'resource' && deleteSecondaryId) {
				await api.projectAPI.removeResource(deleteId, deleteSecondaryId);
				await loadResourcesForSelectedProjects();
			}
		} catch (e: any) {
			console.error(e);
			let msg = 'Failed to delete item';
			// Extract detail from api.ts error format: "HTTP error! status: 400 - {"detail":"..."}"
			const match = e.message?.match(/HTTP error! status: \d+ - (.*)/);
			if (match && match[1]) {
				try {
					const body = JSON.parse(match[1]);
					if (body.detail) msg = body.detail;
				} catch {
					// If parsing fails, use the raw text if it's not too long
					if (match[1].length < 100) msg = match[1];
				}
			}
			alert(msg);
		} finally {
			deleteModalOpen = false;
			deleteType = null;
			deleteId = null;
			deleteSecondaryId = null;
		}
	}

</script>

	<div class="container mx-auto px-4 py-6 space-y-8">
		<!-- CUSTOMERS SECTION -->
		<section class="space-y-4">
			<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<h2 class="text-2xl font-bold dark:text-white">
					Customers
				</h2>
				<div class="flex flex-wrap items-center gap-2">
					<div class="relative">
						<Icon icon="mdi:magnify" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 h-4 w-4" />
						<input 
							type="text" 
							placeholder="Search..." 
							bind:value={searchTermCustomer}
							class="pl-9 pr-4 py-2 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-sm w-40"
						/>
					</div>
					<select bind:value={sortFieldCustomer} class="rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 py-2 pl-3 pr-8 text-sm">
						<option value="customer_name">Name</option>
						<option value="status">Status</option>
					</select>
					<button 
						on:click={() => sortDirectionCustomer = sortDirectionCustomer === 'asc' ? 'desc' : 'asc'}
						class="p-2 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
						title="Toggle Sort Direction"
					>
						<Icon icon={sortDirectionCustomer === 'asc' ? 'mdi:sort-ascending' : 'mdi:sort-descending'} class="h-5 w-5" />
					</button>
					<button
						on:click={openAddCustomer}
						class="inline-flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 shadow-sm transition-colors ml-2"
					>
						<Icon icon="mdi:plus" class="h-5 w-5" />
						<span>Add</span>
					</button>
				</div>
			</div>

			<div class="rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
						<thead class="bg-gray-50 dark:bg-gray-900">
							<tr>
								<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 w-10"></th>
								<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">ID</th>
								<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Name</th>
								<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Description</th>
							<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Country</th>
								<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
								<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Date Started</th>
								<th class="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
							{#each pagedCustomers as c (c.id)}
								<tr 
									class="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 {selectedCustomerId === c.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}"
									on:click={() => selectCustomer(c.id)}
								>
									<td class="px-6 py-4 whitespace-nowrap text-sm" on:click|stopPropagation>
										<input
											type="radio"
											name="customer-select"
											checked={selectedCustomerId === c.id}
											on:change={() => selectCustomer(c.id)}
											class="h-4 w-4 text-blue-600 focus:ring-blue-500"
										/>
									</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{c.id}</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{c.customer_name}</td>
									<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 max-w-xs truncate" title={c.description || ''}>{c.description || '-'}</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{c.customer_location || '-'}</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
										<span class="px-2 inline-flex items-center text-xs leading-5 font-semibold rounded-full {c.status === 'Active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
											<Icon icon={c.status === 'Active' ? 'mdi:check-circle-outline' : 'mdi:close-circle-outline'} class="mr-1 h-3 w-3" />
											{c.status}
										</span>
									</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
										{c.created_at?.split('T')[0] || '-'}
									</td>
									<td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
										<button 
											class="text-blue-600 hover:text-blue-900 mr-3 inline-flex items-center gap-1"
											on:click|stopPropagation={() => openEditCustomer(c)}
										>
											<Icon icon="mdi:pencil" class="h-4 w-4" />
											Edit
										</button>
										<button 
											class="text-red-600 hover:text-red-900 inline-flex items-center gap-1"
											on:click|stopPropagation={() => confirmDeleteCustomer(c)}
										>
											<Icon icon="mdi:delete" class="h-4 w-4" />
											Delete
										</button>
									</td>
								</tr>
							{/each}
							{#if pagedCustomers.length === 0}
								<tr>
									<td colspan="8" class="px-6 py-4 text-center text-gray-500">No customers found.</td>
								</tr>
							{/if}
						</tbody>
					</table>
				</div>
				<!-- Pagination -->
				<div class="flex justify-between items-center px-4 py-3 border-t border-gray-200 dark:border-gray-700">
					<span class="text-sm">Page {customerPage} of {customerPageCount}</span>
					<div class="flex items-center gap-2">
						<button 
							disabled={customerPage === 1}
							on:click={() => customerPage--}
							class="px-3 py-1 rounded border disabled:opacity-50 flex items-center gap-1 hover:bg-gray-100 dark:hover:bg-gray-700"
						>
							<Icon icon="mdi:chevron-left" class="h-5 w-5" />
							Prev
						</button>
						<button 
							disabled={customerPage === customerPageCount}
							on:click={() => customerPage++}
							class="px-3 py-1 rounded border disabled:opacity-50 flex items-center gap-1 hover:bg-gray-100 dark:hover:bg-gray-700"
						>
							Next
							<Icon icon="mdi:chevron-right" class="h-5 w-5" />
						</button>
					</div>
				</div>
			</div>
		</section>

		<!-- PROJECTS SECTION -->
		<section class="space-y-4">
			<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<h2 class="text-2xl font-bold dark:text-white">
					Projects
				</h2>
				{#if selectedCustomerId}
					<div class="flex flex-wrap items-center gap-2">
						<div class="relative">
							<Icon icon="mdi:magnify" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 h-4 w-4" />
							<input 
								type="text" 
								placeholder="Search..." 
								bind:value={searchTermProject}
								class="pl-9 pr-4 py-2 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-sm w-40"
							/>
						</div>
						<select bind:value={sortFieldProject} class="rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 py-2 pl-3 pr-8 text-sm">
							<option value="project_name">Name</option>
							<option value="status">Status</option>
							<option value="start_date">Start Date</option>
						</select>
						<button 
							on:click={() => sortDirectionProject = sortDirectionProject === 'asc' ? 'desc' : 'asc'}
							class="p-2 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
							title="Toggle Sort Direction"
						>
							<Icon icon={sortDirectionProject === 'asc' ? 'mdi:sort-ascending' : 'mdi:sort-descending'} class="h-5 w-5" />
						</button>
						<button
							on:click={openAddProject}
							class="inline-flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 shadow-sm transition-colors ml-2"
						>
							<Icon icon="mdi:plus" class="h-5 w-5" />
							<span>Add</span>
						</button>
					</div>
				{/if}
			</div>

			{#if !selectedCustomerId}
				<div class="rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
					Select a customer to view projects.
				</div>
			{:else}
				<div class="rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
					<div class="overflow-x-auto">
						<table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
							<thead class="bg-gray-50 dark:bg-gray-900">
								<tr>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 w-10">
										<input
											type="checkbox"
											checked={allProjectsSelected}
											use:setIndeterminate={someProjectsSelected}
											on:change={toggleSelectAllProjects}
											class="h-4 w-4 text-blue-600 focus:ring-blue-500"
										/>
									</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">ID</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Project Name</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Description</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Dates</th>
									<th class="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
								{#each pagedProjects as p (p.id)}
									<tr 
										class="hover:bg-gray-50 dark:hover:bg-gray-700 {selectedProjectIds.includes(p.id) ? 'bg-blue-50 dark:bg-blue-900/20' : ''}"
									>
										<td class="px-6 py-4 whitespace-nowrap text-sm">
											<input
												type="checkbox"
												checked={selectedProjectIds.includes(p.id)}
												on:change={() => toggleProjectSelection(p.id)}
												class="h-4 w-4 text-blue-600 focus:ring-blue-500"
											/>
										</td>
										<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{p.id}</td>
										<td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{p.project_name}</td>
										<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 max-w-xs truncate" title={p.description || ''}>{p.description || '-'}</td>
										<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
											<span class="px-2 inline-flex items-center text-xs leading-5 font-semibold rounded-full 
												{p.status === 'Completed' ? 'bg-green-100 text-green-800' : 
												 p.status === 'Ongoing' ? 'bg-blue-100 text-blue-800' : 
												 'bg-yellow-100 text-yellow-800'}">
												<Icon icon={
													p.status === 'Completed' ? 'mdi:check-circle-outline' : 
													p.status === 'Ongoing' ? 'mdi:progress-clock' : 
													'mdi:clock-outline'
												} class="mr-1 h-3 w-3" />
												{p.status}
											</span>
										</td>
										<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
											{p.start_date?.split('T')[0] || '-'} to {p.end_date?.split('T')[0] || '-'}
										</td>
										<td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
											<button 
												class="text-blue-600 hover:text-blue-900 mr-3 inline-flex items-center gap-1"
												on:click|stopPropagation={() => openEditProject(p)}
											>
												<Icon icon="mdi:pencil" class="h-4 w-4" />
												Edit
											</button>
											<button 
												class="text-red-600 hover:text-red-900 inline-flex items-center gap-1"
												on:click|stopPropagation={() => confirmDeleteProject(p)}
											>
												<Icon icon="mdi:delete" class="h-4 w-4" />
												Delete
											</button>
										</td>
									</tr>
								{/each}
								{#if pagedProjects.length === 0}
									<tr>
										<td colspan="7" class="px-6 py-4 text-center text-gray-500">No projects found for this customer.</td>
									</tr>
								{/if}
							</tbody>
						</table>
					</div>
					<!-- Pagination -->
					<div class="flex justify-between items-center px-4 py-3 border-t border-gray-200 dark:border-gray-700">
						<span class="text-sm">Page {projectPage} of {projectPageCount}</span>
						<div class="flex items-center gap-2">
							<button 
								disabled={projectPage === 1}
								on:click={() => projectPage--}
								class="px-3 py-1 rounded border disabled:opacity-50 flex items-center gap-1 hover:bg-gray-100 dark:hover:bg-gray-700"
							>
								<Icon icon="mdi:chevron-left" class="h-5 w-5" />
								Prev
							</button>
							<button 
								disabled={projectPage === projectPageCount}
								on:click={() => projectPage++}
								class="px-3 py-1 rounded border disabled:opacity-50 flex items-center gap-1 hover:bg-gray-100 dark:hover:bg-gray-700"
							>
								Next
								<Icon icon="mdi:chevron-right" class="h-5 w-5" />
							</button>
						</div>
					</div>
				</div>
			{/if}
		</section>

		<!-- PROJECT RESOURCES SECTION -->
		<section class="space-y-4 pb-12">
			<div class="flex items-center justify-between">
				<h2 class="text-2xl font-bold dark:text-white">
					Project Resources
				</h2>
				{#if singleSelectedProjectId}
					<button
						on:click={openAddResource}
						class="inline-flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 shadow-sm transition-colors"
					>
						<Icon icon="mdi:account-plus" class="h-5 w-5" />
						<span>Add Resource</span>
					</button>
				{/if}
			</div>

			{#if selectedProjectIds.length === 0}
				<div class="rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
					Select at least one project to view resources.
				</div>
			{:else}
				{#if selectedProjectIds.length > 1}
					<p class="text-sm text-gray-500 dark:text-gray-400">
						Showing combined, de-duplicated resources from {selectedProjectIds.length} selected projects.
					</p>
				{/if}
				<div class="rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
					<div class="overflow-x-auto">
						<table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
							<thead class="bg-gray-50 dark:bg-gray-900">
								<tr>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Name</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Email</th>
									<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Role</th>
									{#if singleSelectedProjectId}
										<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">FTE</th>
										<th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Planned Hours</th>
									{/if}
									<th class="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
								{#each pagedResources as r (r.id)}
									<tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
										<td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{r.full_name || r.username}</td>
										<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{r.email || '-'}</td>
										<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{r.role_in_project || 'Member'}</td>
										{#if singleSelectedProjectId}
											<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
												<select
													value={r.fte}
													on:change={(e) => updateResourceFte(r, Number((e.target as HTMLSelectElement).value) as FTE)}
													class="rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 py-1 pl-2 pr-6 text-sm"
												>
													<option value={FTE.FULL_TIME}>100%</option>
													<option value={FTE.HALF_TIME}>50%</option>
													<option value={FTE.QUARTER_TIME}>25%</option>
												</select>
											</td>
											<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
												{#if calculatePlannedHours(singleSelectedProject, r.fte) !== null}
													{calculatePlannedHours(singleSelectedProject, r.fte)?.toFixed(1)} h
												{:else}
													-
												{/if}
											</td>
										{/if}
										<td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
											{#if singleSelectedProjectId}
												<button 
													class="text-red-600 hover:text-red-900 inline-flex items-center gap-1"
													on:click={() => confirmRemoveResource(r)}
												>
													<Icon icon="mdi:account-remove" class="h-4 w-4" />
													Remove
												</button>
											{:else}
												<span class="text-gray-400 text-xs">Select one project to remove</span>
											{/if}
										</td>
									</tr>
								{/each}
								{#if pagedResources.length === 0}
									<tr>
										<td colspan={singleSelectedProjectId ? 6 : 4} class="px-6 py-4 text-center text-gray-500">No resources assigned to the selected project(s).</td>
									</tr>
								{/if}
							</tbody>
						</table>
					</div>
					<!-- Pagination -->
					<div class="flex justify-between items-center px-4 py-3 border-t border-gray-200 dark:border-gray-700">
						<span class="text-sm">Page {resourcePage} of {resourcePageCount}</span>
						<div class="flex items-center gap-2">
							<button 
								disabled={resourcePage === 1}
								on:click={() => resourcePage--}
								class="px-3 py-1 rounded border disabled:opacity-50 flex items-center gap-1 hover:bg-gray-100 dark:hover:bg-gray-700"
							>
								<Icon icon="mdi:chevron-left" class="h-5 w-5" />
								Prev
							</button>
							<button 
								disabled={resourcePage === resourcePageCount}
								on:click={() => resourcePage++}
								class="px-3 py-1 rounded border disabled:opacity-50 flex items-center gap-1 hover:bg-gray-100 dark:hover:bg-gray-700"
							>
								Next
								<Icon icon="mdi:chevron-right" class="h-5 w-5" />
							</button>
						</div>
					</div>
				</div>
			{/if}
		</section>
	</div>

<!-- Customer Modal -->
{#if showCustomerModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
		<div class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800">
			<h3 class="mb-4 text-xl font-bold dark:text-white">{editingCustomer ? 'Edit Customer' : 'Add Customer'}</h3>
			<div class="space-y-4">
				<div>
					<label for="cust-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Customer Name</label>
					<input id="cust-name" class="mt-1 block w-full rounded border p-2" bind:value={customerForm.customer_name} />
				</div>
				<div>
					<label for="cust-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Description</label>
					<textarea id="cust-desc" class="mt-1 block w-full rounded border p-2" bind:value={customerForm.description}></textarea>
				</div>
				<div>
					<label for="cust-country" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Country</label>
					<select id="cust-country" class="mt-1 block w-full rounded border p-2 dark:bg-gray-700 dark:text-white" bind:value={customerForm.customer_location}>
						<option value="">Select Country</option>
						{#each countries as country}
							<option value={country}>{country}</option>
						{/each}
					</select>
				</div>
				<div>
					<label for="cust-status" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Status</label>
					<select id="cust-status" class="mt-1 block w-full rounded border p-2" bind:value={customerForm.status}>
						<option value="Active">Active</option>
						<option value="Inactive">Inactive</option>
					</select>
				</div>
			</div>
			<div class="mt-6 flex justify-end gap-3">
				<button class="rounded px-4 py-2 text-gray-600 hover:bg-gray-100 flex items-center gap-1" on:click={() => showCustomerModal = false}>
					<Icon icon="mdi:close" class="h-5 w-5" />
					Cancel
				</button>
				<button class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 flex items-center gap-1" on:click={saveCustomer}>
					<Icon icon="mdi:content-save" class="h-5 w-5" />
					Save
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Project Modal -->
{#if showProjectModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
		<div class="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800">
			<h3 class="mb-4 text-xl font-bold dark:text-white">{editingProject ? 'Edit Project' : 'Add Project'}</h3>
			<div class="space-y-4">
				<div>
					<label for="proj-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Project Name</label>
					<input id="proj-name" class="mt-1 block w-full rounded border p-2" bind:value={projectForm.project_name} />
				</div>
				<div>
					<label for="proj-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Description</label>
					<textarea id="proj-desc" class="mt-1 block w-full rounded border p-2" bind:value={projectForm.description}></textarea>
				</div>
				<div>
					<label for="proj-manager" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Project Manager</label>
					<select id="proj-manager" class="mt-1 block w-full rounded border p-2" bind:value={projectForm.manager_id}>
						<option value={undefined}>-- Select Manager --</option>
						{#each allUsers as u}
							<option value={u.id}>{u.first_name} {u.last_name} ({u.username})</option>
						{/each}
					</select>
				</div>
				<div class="grid grid-cols-2 gap-4">
					<div>
						<label for="proj-start" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Start Date</label>
						<input id="proj-start" type="date" class="mt-1 block w-full rounded border p-2" bind:value={projectForm.start_date} />
					</div>
					<div>
						<label for="proj-end" class="block text-sm font-medium text-gray-700 dark:text-gray-300">End Date</label>
						<input id="proj-end" type="date" class="mt-1 block w-full rounded border p-2" bind:value={projectForm.end_date} />
					</div>
				</div>
			</div>
			<div class="mt-6 flex justify-end gap-3">
				<button class="rounded px-4 py-2 text-gray-600 hover:bg-gray-100 flex items-center gap-1" on:click={() => showProjectModal = false}>
					<Icon icon="mdi:close" class="h-5 w-5" />
					Cancel
				</button>
				<button class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 flex items-center gap-1" on:click={saveProject}>
					<Icon icon="mdi:content-save" class="h-5 w-5" />
					Save
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Resource Modal -->
{#if showResourceModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
		<div class="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800">
			<h3 class="mb-4 text-xl font-bold dark:text-white">Add Resources</h3>
			<div class="max-h-96 overflow-y-auto border rounded p-2 space-y-1">
				{#each allUsers as user}
					{#if !projectResources.find(r => r.id === user.id)}
						<div class="flex items-center justify-between gap-2 p-2 hover:bg-gray-50 dark:hover:bg-gray-700 rounded">
							<label class="flex items-center gap-2 cursor-pointer flex-1">
								<input
									type="checkbox"
									checked={resourceFormIds.includes(user.id)}
									on:change={() => toggleResourceSelection(user.id)}
								/>
								<div>
									<div class="font-medium">{user.first_name} {user.last_name}</div>
									<div class="text-xs text-gray-500">{user.username}</div>
								</div>
							</label>
							{#if resourceFormIds.includes(user.id)}
								<select
									bind:value={resourceFTEs[user.id]}
									class="rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 py-1 pl-2 pr-6 text-sm"
								>
									<option value={FTE.FULL_TIME}>100%</option>
									<option value={FTE.HALF_TIME}>50%</option>
									<option value={FTE.QUARTER_TIME}>25%</option>
								</select>
							{/if}
						</div>
					{/if}
				{/each}
			</div>
			<div class="mt-4 text-sm text-gray-500">Selected: {resourceFormIds.length} users</div>
			<div class="mt-6 flex justify-end gap-3">
				<button class="rounded px-4 py-2 text-gray-600 hover:bg-gray-100 flex items-center gap-1" on:click={() => { showResourceModal = false; }}>
					<Icon icon="mdi:close" class="h-5 w-5" />
					Cancel
				</button>
				<button class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 flex items-center gap-1" on:click={saveResources}>
					<Icon icon="mdi:check" class="h-5 w-5" />
					Add Selected
				</button>
			</div>
		</div>
	</div>
{/if}

<ConfirmModal
	bind:open={deleteModalOpen}
	message={deleteMessage}
	on:confirm={performDelete}
/>