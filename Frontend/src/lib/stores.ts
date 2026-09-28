import { writable, derived } from 'svelte/store';

// Enhanced auth store with JWT token support
const KEY = 'project_auth_v2';

interface AuthState {
	isAuthenticated: boolean;
	role: string;
	username: string;
	token: string | null;
	userId: number | null;
}

function load(): AuthState {
	try {
		const raw = localStorage.getItem(KEY);
		if (!raw) return getDefaultState();
		const parsed = JSON.parse(raw);
		// Validate token expiration (basic check)
		if (parsed.token && isTokenExpired(parsed.token)) {
			return getDefaultState();
		}
		return parsed;
	} catch {
		return getDefaultState();
	}
}

function getDefaultState(): AuthState {
	return {
		isAuthenticated: false,
		role: '',
		username: '',
		token: null,
		userId: null
	};
}

function save(value: AuthState) {
	try {
		localStorage.setItem(KEY, JSON.stringify(value));
	} catch {
		// ignore
	}
}

function isTokenExpired(token: string): boolean {
	try {
		const payload = JSON.parse(atob(token.split('.')[1]));
		const exp = payload.exp;
		if (!exp) return false;
		return Date.now() >= exp * 1000;
	} catch {
		return true;
	}
}

const initial = typeof window !== 'undefined' ? load() : getDefaultState();

const authStore = writable(initial);
authStore.subscribe((v) => {
	if (typeof window !== 'undefined') save(v);
});

export const isAuthenticated = derived(authStore, ($a) => $a.isAuthenticated);
export const userRole = derived(authStore, ($a) => $a.role);
export const username = derived(authStore, ($a) => $a.username);
export const authToken = derived(authStore, ($a) => $a.token);
export const userId = derived(authStore, ($a) => $a.userId);

// ============================================================================
// ROLE-BASED ACCESS CONTROL STORES
// ============================================================================
//
// Role System:
// - Admin: Full access to all features, users, projects, and timelogs
// - Manager: Access to manage assigned projects, approve timelogs
// - Project Manager: Special role - assigned to projects, can approve/reject timelogs
// - User: Regular user - can view/edit own profile, timelogs, and approvals
//

// Derived stores for access control based on role
export const isAdmin = derived(userRole, ($role) => {
	const lower = ($role || '').toLowerCase();
	return lower === 'admin';
});

export const isManager = derived(userRole, ($role) => {
	const lower = ($role || '').toLowerCase();
	return lower === 'manager' || lower === 'admin';
});

export const isProjectManager = derived(userRole, ($role) => {
	const lower = ($role || '').toLowerCase();
	// Project managers are identified by having a special project assignment
	// This will be checked by the backend
	return lower === 'project manager' || lower === 'manager' || lower === 'admin';
});

export const isUser = derived(userRole, ($role) => {
	const lower = ($role || '').toLowerCase();
	return lower === 'user' || lower === 'manager' || lower === 'admin';
});

// Role descriptions for UI
export const roleDescription = derived(userRole, ($role) => {
	const lower = ($role || '').toLowerCase();
	const descriptions: Record<string, string> = {
		admin: 'Administrator - Full access to all features and users',
		manager: 'Manager - Can manage projects and approve timelogs',
		user: 'User - Can view own profile, timelogs, and approvals',
		'project manager': 'Project Manager - Can approve timelogs for assigned projects'
	};
	return descriptions[lower] || 'User';
});

export function login(user: string, role: string, token: string, userId: number) {
	authStore.set({
		isAuthenticated: true,
		username: user,
		role,
		token,
		userId
	});
}

export function logout() {
	authStore.set(getDefaultState());
}

export function getAuthHeaders(): Record<string, string> {
	const state = getStoreValue<AuthState>(authStore);
	return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

function getStoreValue<T>(store: { subscribe: (callback: (value: T) => void) => () => void }): T {
	let value: T | undefined;
	const unsubscribe = store.subscribe((v: T) => {
		value = v;
	});
	unsubscribe(); // Clean up the subscription
	if (value === undefined) {
		throw new Error('Store value is undefined');
	}
	return value;
}

export default {
	isAuthenticated,
	userRole,
	username,
	isAdmin,
	isManager,
	isProjectManager,
	login,
	logout
};
