// API service for connecting frontend to backend
const isDevelopment = import.meta.env.DEV;
const apiUrlEnv = (import.meta.env.VITE_API_URL || '').trim();
const DEFAULT_API_URL = 'http://localhost:8000';
const API_BASE_URL = (() => {
	let base = apiUrlEnv.length > 0 ? apiUrlEnv : isDevelopment ? '/api' : DEFAULT_API_URL;
	if (!isDevelopment && apiUrlEnv.length === 0 && typeof window !== 'undefined') {
		const host = window.location.hostname;
		if (host === 'localhost' || host === '127.0.0.1') {
			base = 'http://localhost:8000';
		}
	}
	return base.replace(/\s+/g, '').replace(/\/$/, '');
})();

export const API_BASE = API_BASE_URL;

if (typeof window !== 'undefined') {
	console.log('[API] Using API_BASE_URL:', API_BASE_URL);
}

// API configuration
const API_CONFIG = {
	baseURL: API_BASE_URL,
	headers: {
		'Content-Type': 'application/json'
	}
};

// Generic API request handler
async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
	const normalizedEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
	const url = `${API_BASE_URL}${normalizedEndpoint.startsWith('/') ? normalizedEndpoint : `/${normalizedEndpoint}`}`;
	// Get auth headers if available
	const authHeaders = typeof window !== 'undefined' ? getAuthHeaders() : {};

	const isForm = options.body instanceof FormData;
	const baseHeaders = isForm ? {} : API_CONFIG.headers;
	const config: RequestInit = {
		...API_CONFIG,
		...options,
		headers: {
			...baseHeaders,
			...authHeaders,
			...options.headers
		}
	};

	try {
		const response = await fetch(url, config);

		if (!response.ok) {
			// Fallback: some production gateways require '/api' prefix
			if (response.status === 404 && !API_BASE_URL.endsWith('/api')) {
				const alt = `${API_BASE_URL}${API_BASE_URL.endsWith('/') ? '' : '/'}api/${normalizedEndpoint}`;
				try {
					const altResp = await fetch(alt, config);
					if (altResp.ok) {
						const altText = await altResp.text();
						return altText ? JSON.parse(altText) : ({} as T);
					}
				} catch {
					/* ignore and proceed to build original error */
				}
			}
			// Try to read and include response body for better debugging (validation errors)
			const errorText = await response.text();
			let errorBody: unknown = errorText;
			try {
				errorBody = JSON.parse(errorText);
			} catch {
				/* not JSON */
			}
			const detail =
				typeof errorBody === 'object' && errorBody !== null && 'detail' in (errorBody as Record<string, unknown>)
					? String((errorBody as Record<string, unknown>).detail as unknown as string)
					: '';
			const invalidCreds =
				response.status === 401 ||
				(response.status === 403 &&
					(detail === 'Could not validate credentials' ||
						detail === 'INVALID TOKEN!' ||
						detail === 'TOKEN NOT PROVIDED!'));
			if (invalidCreds && typeof window !== 'undefined') logout();
			// Nested 404 fallback for legacy '/users/me' endpoint
			if (response.status === 404 && endpoint.includes('/user/me')) {
				const legacyEndpoint = endpoint.replace('/user/me', '/users/me');
				return apiRequest<T>(legacyEndpoint, options);
			}
			const bodyMsg = typeof errorBody === 'string' ? errorBody : JSON.stringify(errorBody);
			const errorMsg = `HTTP error! status: ${response.status} - ${bodyMsg}`;
			console.error(`[API] Request to ${url} failed: ${errorMsg}`);
			throw new Error(errorMsg);
		}

		// Handle empty response
		const text = await response.text();
		return text ? JSON.parse(text) : ({} as T);
	} catch (error) {
		const msg = error instanceof Error ? error.message : String(error);
		const name = (error as { name?: string })?.name ?? '';
		const aborted = name.includes('Abort') || msg.includes('Abort') || msg.includes('ERR_ABORTED');
		if (!aborted) {
			console.error('API request failed:', error);
		}
		throw error;
	}
}

// Import auth functions
import { getAuthHeaders, logout } from './stores';

// User interfaces (matching backend schemas)
export type CivilStatus = 'Single' | 'Married' | 'Widowed' | 'Separated' | 'Divorced' | 'Annulled';

export interface CreateUser {
	username: string;
	password: string;
	role: string;
	role_id?: number;
	branch_id?: number;
	first_name?: string;
	last_name?: string;
	email?: string;
	phone_number: string;
	civil_status: CivilStatus;
	birthdate: string;
	permanent_address_line: string;
	current_address_line: string;
	permanent_address_psgc: string;
	current_address_psgc: string;
	profile_picture_url?: string;
	salutation?: string;
	department?: string;
	job_level?: string;
	emergency_contact_name?: string;
	emergency_contact_number?: string;
	gotyme_account_name?: string;
	gotyme_account_number?: string;
	tin_number?: string;
	sss_number?: string;
	philhealth_number?: string;
	pagibig_number?: string;
	emp_start_date?: string;
	emp_end_date?: string;
	blocked?: boolean;
	date_created: string;
	date_updated: string;
}

export interface UpdateUser {
	username?: string;
	password?: string;
	role?: string;
	role_id?: number;
	branch_id?: number;
	first_name?: string;
	last_name?: string;
	email?: string;
	phone_number?: string;
	civil_status?: CivilStatus;
	birthdate?: string;
	permanent_address_line?: string;
	current_address_line?: string;
	permanent_address_psgc?: string;
	current_address_psgc?: string;
	profile_picture_url?: string;
	salutation?: string;
	department?: string;
	job_level?: string;
	emergency_contact_name?: string;
	emergency_contact_number?: string;
	gotyme_account_name?: string;
	gotyme_account_number?: string;
	tin_number?: string;
	sss_number?: string;
	philhealth_number?: string;
	pagibig_number?: string;
	emp_start_date?: string;
	emp_end_date?: string;
	blocked?: boolean;
	date_updated?: string;
}

export interface UserResponse {
	id: number;
	username: string;
	role: string;
	role_id?: number;
	branch_id?: number;
	first_name?: string;
	last_name?: string;
	email?: string;
	phone_number?: string;
	civil_status?: CivilStatus;
	birthdate?: string;
	permanent_address_line?: string;
	current_address_line?: string;
	permanent_address_psgc?: string;
	current_address_psgc?: string;
	profile_picture_url?: string;
	salutation?: string;
	department?: string;
	job_level?: string;
	emergency_contact_name?: string;
	emergency_contact_number?: string;
	gotyme_account_name?: string;
	gotyme_account_number?: string;
	tin_number?: string;
	sss_number?: string;
	philhealth_number?: string;
	pagibig_number?: string;
	emp_start_date?: string;
	emp_end_date?: string;
	blocked?: boolean;
	status?: 'Active' | 'Inactive (Contract Ended)' | 'Inactive (Contract Not Started)';
	date_created?: string;
	date_updated?: string;
}

export interface CreateBranch {
	branch_name: string;
	branch_address?: string;
}

export interface UpdateBranch {
	branch_name?: string;
	branch_address?: string;
}

export interface BranchResponse {
	id: number;
	branch_name: string;
	branch_address?: string;
	created_at: string;
}

// Customer interfaces
export interface CreateCustomer {
	customer_name: string;
	description?: string;
	customer_location?: string;
	status?: string;
}

export interface UpdateCustomer {
	customer_name?: string;
	description?: string;
	customer_location?: string;
	status?: string;
}

export interface CustomerResponse {
	id: number;
	customer_name: string;
	description?: string;
	customer_location?: string;
	status: string;
	created_at: string;
	updated_at: string;
}

export interface CreateProject {
	project_name: string;
	description?: string;
	manager_id?: number;
	manager_role_id?: number;
	branch_id?: number;
	customer_id?: number;
	start_date?: string;
	end_date?: string;
	status?: string;
}

export interface UpdateProject {
	project_name?: string;
	description?: string;
	manager_id?: number;
	manager_role_id?: number;
	branch_id?: number;
	customer_id?: number;
	start_date?: string;
	end_date?: string;
	status?: string;
}

export interface ProjectResponse {
	id: number;
	project_name: string;
	description?: string;
	manager_id?: number;
	manager_username?: string;
	manager_role_id?: number;
	branch_id?: number;
	customer_id?: number;
	customer_name?: string;
	start_date?: string;
	end_date?: string;
	status: string;
	created_at: string;
	updated_at: string;
}

export enum FTE {
	FULL_TIME = 100,
	HALF_TIME = 50,
	QUARTER_TIME = 25
}

export interface CreateProjectResource {
	user_id: number;
	project_id: number;
	role_in_project: string;
	fte: FTE;
}

export interface UpdateProjectResource {
	fte?: FTE;
	role_in_project?: string;
}

export interface ProjectUser {
	id: number;
	username: string;
	email?: string;
	full_name?: string;
	role_in_project?: string;
	fte?: number;
}

export interface TimelogCreate {
	type: 'project' | 'other' | 'leave';
	project_id?: number;
	task_type_id?: number;
	description?: string;
	location?: string;
	start_time: string; // ISO
	end_time: string; // ISO
}

export interface TimelogResponse {
	id: number;
	user_id: number;
	username?: string;
	first_name?: string;
	last_name?: string;
	type: 'project' | 'other' | 'leave';
	project_id?: number;
	task_type_id?: number;
	description?: string;
	location?: string;
	start_time: string;
	end_time: string;
	duration_minutes: number;
	status: 'Pending' | 'Approved' | 'Rejected';
	approver_id?: number;
	approver_name?: string;
	approved_at?: string;
	created_at: string;
	updated_at: string;
}

export interface LeaveCreditResponse {
	id: number;
	user_id: number;
	sick_leave_balance: number;
	vacation_leave_balance: number;
	last_allocation_month?: string | null;
	updated_at: string;
}

export interface WeeklySummaryItem {
	week_start: string;
	week_end: string;
	total_logged_hours: number;
	deficient_hours: number;
	approved_hours: number;
	for_approval_hours: number;
	rejected_hours: number;
}

export interface User201FileCreate {
	user_id: number;
	file_name: string;
	document_type_id: number;
	file_url?: string;
	s3_path?: string;
	notes?: string;
	remarks?: string;
	status?: 'Pending' | 'Approved' | 'Declined';
	version?: number;
	is_active?: boolean;
	created_at?: string;
	updated_at?: string;
}

export interface User201FileUpdate {
	file_name?: string;
	document_type?: string;
	file_url?: string;
	s3_path?: string;
	notes?: string;
	remarks?: string;
	status?: 'Pending' | 'Approved' | 'Declined';
	approver_id?: number;
	approved_at?: string;
	reviewed_at?: string;
	reviewed_by?: number;
	version?: number;
	is_active?: boolean;
	updated_at?: string;
}

export interface User201FileResponse {
	id: number;
	user_id: number;
	file_name: string;
	document_type_id: number;
	file_url?: string;
	s3_path?: string;
	notes?: string;
	remarks?: string;
	status: 'Pending' | 'Approved' | 'Declined';
	approver_id?: number;
	approved_at?: string;
	reviewed_at?: string;
	reviewed_by?: number;
	uploaded_at?: string;
	version: number;
	is_active: boolean;
	created_at: string;
	updated_at: string;
}

export interface NotificationBackendItem {
	id: number;
	item_type?: string;
	item_id?: number;
	action?: 'approved' | 'rejected' | 'created' | 'declined';
	approver_id?: number;
	approver_name?: string;
	approver_avatar?: string;
	target_route?: string;
	is_read?: number;
	created_at?: string;
}

export interface StatusUpdateBackendItem {
	id: number;
	type?: string;
	item_id?: number;
	message?: string;
	created_at?: string;
	timelog_id?: number;
	status?: 'Approved' | 'Rejected';
	approved_at?: string;
	approver_id?: number;
	approver_name?: string;
	approver_avatar?: string;
	description?: string;
	action?: 'approved' | 'rejected';
	target_route?: string;
}

// User API functions
export const userAPI = {
	// Get all users
	async getAllUsers(): Promise<UserResponse[]> {
		return apiRequest<UserResponse[]>('/user/');
	},

	async getManagedUsers(): Promise<UserResponse[]> {
		return apiRequest<UserResponse[]>('user/my-managed')
	},

	// Get single user by ID
	async getUser(userId: number): Promise<UserResponse> {
		return apiRequest<UserResponse>(`/user/${userId}`);
	},

	// Create new user
	async createUser(user: CreateUser): Promise<UserResponse> {
		return apiRequest<UserResponse>('/user/', {
			method: 'POST',
			body: JSON.stringify(user)
		});
	},

	// Update user
	async updateUser(userId: number, userUpdate: UpdateUser): Promise<UserResponse> {
		return apiRequest<UserResponse>(`/user/${userId}`, {
			method: 'PATCH',
			body: JSON.stringify(userUpdate)
		});
	},

	// Update current user (non-admin)
	async updateMe(userUpdate: UpdateUser): Promise<UserResponse> {
		return apiRequest<UserResponse>(`/user/me`, {
			method: 'PATCH',
			body: JSON.stringify(userUpdate)
		});
	},

	// Delete user
	async deleteUser(userId: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/user/${userId}`, {
			method: 'DELETE'
		});
	},

	async getUserProjects(userId: number): Promise<ProjectResponse[]> {
		return apiRequest<ProjectResponse[]>(`/user/${userId}/projects`);
	},

	async getMyProjects(): Promise<ProjectResponse[]> {
		return apiRequest<ProjectResponse[]>(`/user/me/projects`);
	},

	async getMe(): Promise<UserResponse> {
		return apiRequest<UserResponse>(`/user/me`);
	},

	async assignUserProjects(userId: number, projectIds: number[]): Promise<ProjectResponse[]> {
		return apiRequest<ProjectResponse[]>(`/user/${userId}/projects`, {
			method: 'PATCH',
			body: JSON.stringify({ project_ids: projectIds })
		});
	},

	async uploadAvatar(file: File): Promise<UserResponse> {
		const formData = new FormData();
		formData.append('file', file);
		return apiRequest<UserResponse>('/user/me/avatar', {
			method: 'POST',
			body: formData
		});
	}
};

export const user201API = {
	async listAll(): Promise<User201FileResponse[]> {
		return apiRequest<User201FileResponse[]>('/user-201/');
	},
	async listByUser(userId: number): Promise<User201FileResponse[]> {
		return apiRequest<User201FileResponse[]>(`/user-201/by-user/${userId}`);
	},
	async listByUserActive(userId: number): Promise<User201FileResponse[]> {
		return apiRequest<User201FileResponse[]>(`/user-201/by-user/${userId}?active_only=true`);
	},
	async listMine(): Promise<User201FileResponse[]> {
		return apiRequest<User201FileResponse[]>('/user-201/me');
	},
	async listMineActive(): Promise<User201FileResponse[]> {
		return apiRequest<User201FileResponse[]>(`/user-201/me?active_only=true`);
	},
	async getOne(id: number): Promise<User201FileResponse> {
		return apiRequest<User201FileResponse>(`/user-201/${id}`);
	},
	async history(documentType: string): Promise<User201FileResponse[]> {
		const params = new URLSearchParams({ document_type: documentType });
		return apiRequest<User201FileResponse[]>(`/user-201/history?${params.toString()}`);
	},
	async create(payload: User201FileCreate): Promise<User201FileResponse> {
		return apiRequest<User201FileResponse>('/user-201/', {
			method: 'POST',
			body: JSON.stringify(payload)
		});
	},
	async update(id: number, payload: User201FileUpdate): Promise<User201FileResponse> {
		return apiRequest<User201FileResponse>(`/user-201/${id}`, {
			method: 'PATCH',
			body: JSON.stringify(payload)
		});
	},
	async remove(id: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/user-201/${id}`, { method: 'DELETE' });
	},
	async presign(
		fileName: string,
		contentType: string,
		category: 'pre' | 'payroll' | 'gov' | 'misc' = 'misc'
	): Promise<{ upload_url: string; file_url: string; key: string }> {
		const params = new URLSearchParams({
			file_name: fileName,
			content_type: contentType,
			category
		});
		return apiRequest<{ upload_url: string; file_url: string; key: string }>(
			`/user-201/presign?${params.toString()}`,
			{ method: 'POST' }
		);
	},
	async uploadTemp(file: File): Promise<{ file_url: string; temp_path: string }> {
		const formData = new FormData();
		formData.append('file', file);
		return apiRequest<{ file_url: string; temp_path: string }>('/user-201/upload-temp', {
			method: 'POST',
			body: formData
		});
	},
	async presignDownload(s3Key: string): Promise<{ download_url: string }> {
		const params = new URLSearchParams({ s3_key: s3Key });
		return apiRequest<{ download_url: string }>(`/user-201/presign-download?${params.toString()}`, {
			method: 'POST'
		});
	},
	async approve(id: number, remarks = ''): Promise<User201FileResponse> {
		const params = new URLSearchParams({ remarks });
		return apiRequest<User201FileResponse>(`/user-201/${id}/approve?${params.toString()}`, {
			method: 'PATCH'
		});
	},
	async decline(id: number, remarks = ''): Promise<User201FileResponse> {
		const params = new URLSearchParams({ remarks });
		return apiRequest<User201FileResponse>(`/user-201/${id}/decline?${params.toString()}`, {
			method: 'PATCH'
		});
	}
};

// Authentication interfaces
export interface LoginRequest {
	username: string;
	password: string;
}

export interface LoginResponse {
	access_token: string;
	token_type: string;
}

export interface VerifyResponse {
	message: string;
	user: {
		id: number;
		username: string;
		role: string;
	};
}

// Authentication API functions
export const authAPI = {
	// Login and get JWT token
	async login(credentials: LoginRequest): Promise<LoginResponse> {
		console.log('Login attempt with username:', credentials.username); // Debug log
		const formData = new URLSearchParams();
		formData.append('username', credentials.username);
		formData.append('password', credentials.password);
		formData.append('grant_type', 'password');

		const response = await apiRequest<LoginResponse>('/auth/login', {
			method: 'POST',
			body: formData,
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			}
		});
		console.log('Login response:', response); // Debug log
		return response;
	},

	// Verify token and get user info
	async verifyToken(token: string): Promise<VerifyResponse> {
		return apiRequest<VerifyResponse>('/auth/verify', {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});
	}
};

// Health check
export const healthAPI = {
	async checkHealth(): Promise<{ message: string }> {
		return apiRequest<{ message: string }>('/schema/status');
	}
};

// Location interfaces
export interface CreateLocation {
	name: string;
	address?: string;
	date_created: string;
	date_updated: string;
}

export interface UpdateLocation {
	name?: string;
	address?: string;
	date_updated: string;
}

export interface LocationResponse {
	id: number;
	name: string;
	address?: string;
}

// Location API functions (admin only)
export const locationAPI = {
	async getAllLocations(): Promise<LocationResponse[]> {
		return apiRequest<LocationResponse[]>('/location/');
	},
	async getLocation(id: number): Promise<LocationResponse> {
		return apiRequest<LocationResponse>(`/location/${id}`);
	},
	async createLocation(loc: CreateLocation): Promise<LocationResponse> {
		return apiRequest<LocationResponse>('/location/', {
			method: 'POST',
			body: JSON.stringify(loc)
		});
	},
	async updateLocation(id: number, loc: UpdateLocation): Promise<LocationResponse> {
		return apiRequest<LocationResponse>(`/location/${id}`, {
			method: 'PATCH',
			body: JSON.stringify(loc)
		});
	},
	async deleteLocation(id: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/location/${id}`, {
			method: 'DELETE'
		});
	}
};

export interface DocumentTypeResponse {
	id: number;
	code: string;
	name: string;
	category: 'pre-employment' | 'payroll' | 'government';
	required: boolean;
	created_at: string;
}

export const document_typeAPI = {
	async getAll(): Promise<DocumentTypeResponse[]> {
		return apiRequest<DocumentTypeResponse[]>('/document-type/');
	},
	async getAllPublic(): Promise<DocumentTypeResponse[]> {
		return apiRequest<DocumentTypeResponse[]>('/document-type/all');
	}
};

// Task Types API
export interface TaskTypeResponse {
	id: number;
	name: string;
	description?: string;
	category: 'other' | 'leave';
	created_at: string;
}

export const task_typeAPI = {
	async getAll(): Promise<TaskTypeResponse[]> {
		return apiRequest<TaskTypeResponse[]>('/task-type/');
	},
	async getAllPublic(): Promise<TaskTypeResponse[]> {
		return apiRequest<TaskTypeResponse[]>('/task-type/all');
	}
};

export const leaveCreditsAPI = {
	async getMyCredits(): Promise<LeaveCreditResponse> {
		return apiRequest<LeaveCreditResponse>('/leave-credits/my-credits');
	},
	async getUserCredits(userId: number): Promise<LeaveCreditResponse> {
		return apiRequest<LeaveCreditResponse>(`/leave-credits/user/${userId}`);
	}
};

export const branchAPI = {
	async getAllBranches(): Promise<BranchResponse[]> {
		return apiRequest<BranchResponse[]>('/branch/');
	},
	async getAllBranchesPublic(): Promise<BranchResponse[]> {
		return apiRequest<BranchResponse[]>('/branch/all');
	},
	async createBranch(branch: CreateBranch): Promise<BranchResponse> {
		return apiRequest<BranchResponse>('/branch/', {
			method: 'POST',
			body: JSON.stringify(branch)
		});
	},
	async updateBranch(branchId: number, update: UpdateBranch): Promise<BranchResponse> {
		return apiRequest<BranchResponse>(`/branch/${branchId}`, {
			method: 'PATCH',
			body: JSON.stringify(update)
		});
	},
	async deleteBranch(branchId: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/branch/${branchId}`, {
			method: 'DELETE'
		});
	}
};

// Default export moved below timelogAPI declaration
export const timelogAPI = {
	async listMine(): Promise<TimelogResponse[]> {
		return apiRequest<TimelogResponse[]>('/timelog/');
	},
	async listAll(): Promise<TimelogResponse[]> {
		return apiRequest<TimelogResponse[]>('/timelog/all');
	},
	async listManaged(
		status: 'Pending' | 'Approved' | 'Rejected' | 'All' = 'Pending'
	): Promise<TimelogResponse[]> {
		const endpoint = `/timelog/managed?status_filter=${encodeURIComponent(status)}`;
		console.log(`[API] Calling listManaged with endpoint: ${endpoint}`);
		try {
			const result = await apiRequest<TimelogResponse[]>(endpoint);
			console.log(`[API] listManaged returned ${result.length} items`);
			return result;
		} catch (error) {
			console.error(`[API] listManaged failed: ${error}`);
			throw error;
		}
	},
	async create(payload: TimelogCreate): Promise<TimelogResponse> {
		return apiRequest<TimelogResponse>('/timelog/', {
			method: 'POST',
			body: JSON.stringify(payload)
		});
	},
	async update(
		id: number,
		payload: Partial<TimelogCreate & { status: 'Pending' | 'Approved' | 'Rejected' }>
	): Promise<TimelogResponse> {
		return apiRequest<TimelogResponse>(`/timelog/${id}`, {
			method: 'PATCH',
			body: JSON.stringify(payload)
		});
	},
	async remove(id: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/timelog/${id}`, { method: 'DELETE' });
	},
	async weeklySummary(weeks = 4): Promise<WeeklySummaryItem[]> {
		return apiRequest<WeeklySummaryItem[]>(`/timelog/summary?weeks=${weeks}`);
	},
	// Duplicate a timelog across a date range with given frequency
	async duplicate(
		id: number,
		payload: { start_date: string; end_date?: string; frequency: 'daily' | 'weekdays' | 'weekly' }
	): Promise<TimelogResponse[]> {
		return apiRequest<TimelogResponse[]>(`/timelog/${id}/duplicate`, {
			method: 'POST',
			body: JSON.stringify(payload)
		});
	},

	// Duplicate a timelog to specific dates
	async duplicateToDates(id: number, dates: string[]): Promise<TimelogResponse[]> {
		return apiRequest<TimelogResponse[]>(`/timelog/${id}/duplicate-to-dates`, {
			method: 'POST',
			body: JSON.stringify({ dates })
		});
	}
};

export const customerAPI = {
	async getAllCustomers(): Promise<CustomerResponse[]> {
		return apiRequest<CustomerResponse[]>('/customer/');
	},
	async getCustomer(id: number): Promise<CustomerResponse> {
		return apiRequest<CustomerResponse>(`/customer/${id}`);
	},
	async createCustomer(customer: CreateCustomer): Promise<CustomerResponse> {
		return apiRequest<CustomerResponse>('/customer/', {
			method: 'POST',
			body: JSON.stringify(customer)
		});
	},
	async updateCustomer(id: number, customer: UpdateCustomer): Promise<CustomerResponse> {
		return apiRequest<CustomerResponse>(`/customer/${id}`, {
			method: 'PUT',
			body: JSON.stringify(customer)
		});
	},
	async deleteCustomer(id: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/customer/${id}`, {
			method: 'DELETE'
		});
	}
};

export const rolesAPI = {
	async getAll(): Promise<string[]> {
		return apiRequest<string[]>('/role/');
	},
	async getAllPublic(): Promise<string[]> {
		return apiRequest<string[]>('/role/all');
	}
};

export const projectAPI = {
	async getAllProjects(customerId?: number): Promise<ProjectResponse[]> {
		const url = customerId ? `/project/?customer_id=${customerId}` : '/project/';
		return apiRequest<ProjectResponse[]>(url);
	},
	async getMyManaged(): Promise<ProjectResponse[]> {
		return apiRequest<ProjectResponse[]>('/project/my-managed');
	},
	async createProject(project: CreateProject): Promise<ProjectResponse> {
		return apiRequest<ProjectResponse>('/project/', {
			method: 'POST',
			body: JSON.stringify(project)
		});
	},
	async updateProject(projectId: number, update: UpdateProject): Promise<ProjectResponse> {
		return apiRequest<ProjectResponse>(`/project/${projectId}`, {
			method: 'PATCH',
			body: JSON.stringify(update)
		});
	},
	async deleteProject(projectId: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/project/${projectId}`, {
			method: 'DELETE'
		});
	},
	async getProjectUsers(projectId: number): Promise<ProjectUser[]> {
		return apiRequest<ProjectUser[]>(`/project/${projectId}/users`);
	},
	async addResource(resource: CreateProjectResource): Promise<{ message: string }> {
		return apiRequest<{ message: string }>('/project/resources', {
			method: 'POST',
			body: JSON.stringify(resource)
		});
	},

	async updateResource(projectId: number, userId: number, payload: UpdateProjectResource): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/project/${projectId}/resources/${userId}`, {
			method: 'PATCH',
			body: JSON.stringify(payload)
		});
	},
	async removeResource(projectId: number, userId: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/project/${projectId}/resources/${userId}`, {
			method: 'DELETE'
		});
	}
};

export interface SystemOptionResponse {
	id: number;
	category: string;
	value: string;
}

export interface CreateSystemOption {
	category: string;
	value: string;
}

export interface UpdateSystemOption {
	value: string;
}

export const systemOptionsAPI = {
	async getAll(category?: string): Promise<SystemOptionResponse[]> {
		const query = category ? `?category=${encodeURIComponent(category)}` : '';
		return apiRequest<SystemOptionResponse[]>(`/system-options/${query}`);
	},
	async create(option: CreateSystemOption): Promise<SystemOptionResponse> {
		return apiRequest<SystemOptionResponse>('/system-options/', {
			method: 'POST',
			body: JSON.stringify(option)
		});
	},
	async update(id: number, option: UpdateSystemOption): Promise<SystemOptionResponse> {
		return apiRequest<SystemOptionResponse>(`/system-options/${id}`, {
			method: 'PUT',
			body: JSON.stringify(option)
		});
	},
	async delete(id: number): Promise<{ message: string }> {
		return apiRequest<{ message: string }>(`/system-options/${id}`, {
			method: 'DELETE'
		});
	}
};

export default {
	userAPI,
	authAPI,
	healthAPI,
	document_typeAPI,
	task_typeAPI,
	leaveCreditsAPI,
	rolesAPI,
	branchAPI,
	timelogAPI,
	projectAPI,
	customerAPI,
	systemOptionsAPI,
	notificationAPI: {
		async getNotifications(): Promise<{ count: number; notifications: NotificationBackendItem[] }> {
			return apiRequest<{ count: number; notifications: NotificationBackendItem[] }>(
				'/notification/mine'
			);
		},
		async markAsRead(notification_id: number): Promise<{ success?: boolean; message?: string }> {
			return apiRequest<{ success?: boolean; message?: string }>(
				`/notification/${notification_id}/read`,
				{
					method: 'PATCH'
				}
			);
		},
		async deleteNotification(notification_id: number): Promise<{ success?: boolean; message?: string }> {
			return apiRequest<{ success?: boolean; message?: string }>(
				`/notification/${notification_id}`,
				{
					method: 'DELETE'
				}
			);
		},
		async getStatusUpdates(): Promise<{ count: number; updates: StatusUpdateBackendItem[] }> {
			return apiRequest<{ count: number; updates: StatusUpdateBackendItem[] }>(
				'/notification/status-updates'
			);
		},
		async recordTimelogApproval(timelog_id: number, status: string): Promise<{ success?: boolean }> {
			return apiRequest<{ success?: boolean }>(
				`/notification/record-approval?timelog_id=${timelog_id}&status_new=${status}`,
				{
					method: 'POST'
				}
			);
		},
		async record201Approval(file_id: number, status: string): Promise<{ success?: boolean }> {
			return apiRequest<{ success?: boolean }>(
				`/notification/record-201-approval?file_id=${file_id}&status_new=${status}`,
				{
					method: 'PATCH'
				}
			);
		}
	},
	locationAPI
};
