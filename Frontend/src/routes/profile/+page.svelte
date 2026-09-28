<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import api, {
		API_BASE,
		user201API,
		document_typeAPI,
		type UserResponse,
		type UpdateUser,
		type BranchResponse,
		type User201FileResponse,
		type DocumentTypeResponse,
		type LeaveCreditResponse,
		type SystemOptionResponse
	} from '$lib/api';
	import { isAuthenticated } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Avatar from '$lib/Avatar.svelte';
	import Icon from '@iconify/svelte';
	import { addNotification, currentToast } from '$lib/notifications';
	import { page } from '$app/stores';
	import { listProvinces, listMuncities, listBarangays } from '@jobuntux/psgc';

	let authed = false;
	isAuthenticated.subscribe((v) => (authed = v));

	let user: UserResponse | null = null;
	let loading = true;
	let error: string | null = null;
	let success: string | null = null;
	let tab: 'personal' | 'employment' = 'personal';
	onMount(() => {
		const params = $page.url.searchParams;
		const t = params.get('tab');
		if (t === 'employment') {
			tab = 'employment';
		}
	});
	let branches: BranchResponse[] = [];
	let systemOptions: SystemOptionResponse[] = [];
	$: departments = systemOptions.filter((o) => o.category === 'Department');
	$: salutations = systemOptions.filter((o) => o.category === 'Salutation');
	$: jobLevels = systemOptions.filter((o) => o.category === 'Job Level');

	// Only Admins can edit First/Last Name, Salutation, Job Level, Username,
	// Branch, and Department below. Regular users and Managers see them read-only.
	// NOTE: `role` is cast to `any` because it isn't on the `UserResponse` type shown
	// here — swap in whatever field/values your UserResponse actually uses for role.
	$: isAdmin = ((user as any)?.role ?? '').toString().toLowerCase() === 'admin';

	// --- PSGC address helpers ---
	// listProvinces() with no arg returns every province/HUC in the country
	const provinces = listProvinces();

	// Full PSGC codes are 10 digits: RR (region) + PPP (province) + MM (city/mun)
	// + BBB (barangay). Slice a saved psgcCode to reconstruct province/municipality
	// dropdown selections without a reverse-lookup call.
	function deriveFromPsgcCode(code?: string): { provinceCode: string; munCityCode: string } {
		if (!code || code.length < 10) return { provinceCode: '', munCityCode: '' };
		return {
			provinceCode: code.slice(2, 5),
			munCityCode: code.slice(2, 7)
		};
	}

	// Turns a saved psgcCode + address line into a readable "House No, Barangay,
	// City, Province" string for read-only display.
	function resolveAddressDisplay(psgcCode?: string, addressLine?: string): string {
		if (!psgcCode) return addressLine || '—';
		const { provinceCode, munCityCode } = deriveFromPsgcCode(psgcCode);
		const province = provinces.find((p) => p.provCode === provinceCode);
		const muncity = munCityCode
			? listMuncities(provinceCode).find((m) => m.munCityCode === munCityCode)
			: undefined;
		const barangay = munCityCode
			? listBarangays(munCityCode).find((b) => b.psgcCode === psgcCode)
			: undefined;
		const parts = [
			addressLine,
			barangay?.brgyName,
			muncity?.munCityName,
			province?.provName
		].filter((v): v is string => !!v && v.trim().length > 0);
		return parts.length ? parts.join(', ') : '—';
	}

	function toDateOnly(d?: string): string {
		if (!d) return '—';
		// Slice rather than parse with `new Date()` — birthdate is a date-only
		// value, and going through Date/toISOString risks a timezone off-by-one.
		return d.slice(0, 10);
	}

	$: permanentAddressDisplay = user
		? resolveAddressDisplay(user.permanent_address_psgc, user.permanent_address_line)
		: '—';

	// Current address dropdown state (the one address block editable here).
	// currBarangayCode holds the full 10-digit `psgcCode`, matching what the
	// backend's current_address_psgc field validates against.
	let currProvinceCode = '';
	let currMunCityCode = '';
	let currBarangayCode = '';

	$: currProvince = provinces.find((p) => p.provCode === currProvinceCode);
	$: currIsHUC = currProvince?.cityClass === 'HUC';
	$: currMuncities = currProvinceCode ? listMuncities(currProvinceCode) : [];
	$: currEffectiveMunCityCode = currIsHUC ? currMuncities[0]?.munCityCode : currMunCityCode;
	$: currBarangays = currEffectiveMunCityCode ? listBarangays(currEffectiveMunCityCode) : [];

	function onCurrProvinceChange() {
		currMunCityCode = '';
		currBarangayCode = '';
	}
	function onCurrMunCityChange() {
		currBarangayCode = '';
	}

	let my201: User201FileResponse[] = [];
	let documentTypes: DocumentTypeResponse[] = [];
	let leaveCredits: LeaveCreditResponse | null = null;
	let leaveCreditsError: string | null = null;
	let bulkUploading = false;
	let selectedDocs: Record<string, File | null> = {};
	let uploading: Record<string, boolean> = {};
	const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
	const MAX_SIZE_BYTES = 10 * 1024 * 1024;
	const preEmploymentItems: { key: string; label: string }[] = [
		{ key: 'psa_birth_certificate', label: 'PSA Birth Certificate' },
		{ key: 'nbi_clearance', label: 'NBI Clearance for Local Employment' },
		{ key: 'police_clearance', label: 'Police Clearance' },
		{ key: 'medical_certificate', label: 'Medical Certificate (Fit to Work)' },
		{ key: 'transcript_of_records', label: 'Transcript of Records with SO number' },
		{ key: 'marriage_certificate', label: 'Marriage Certificate (if legally married)' }
	];
	const payrollFileItems: { key: string; label: string }[] = [
		{ key: 'gotyme_bank_certificate', label: 'GoTyme Bank Certificate' },
		{ key: 'gotyme_atm_card', label: 'GoTyme ATM Card' }
	];
	const governmentFileItems: { key: string; label: string }[] = [
		{ key: 'tin', label: 'TIN' },
		{ key: 'sss', label: 'SSS' },
		{ key: 'philhealth', label: 'PhilHealth' },
		{ key: 'pagibig', label: 'Pag-IBIG' }
	];
	const labelToCategory: Record<string, 'pre' | 'payroll' | 'gov' | 'misc'> = {};
	for (const it of preEmploymentItems) labelToCategory[it.label] = 'pre';
	for (const it of payrollFileItems) labelToCategory[it.label] = 'payroll';
	for (const it of governmentFileItems) labelToCategory[it.label] = 'gov';
	function getCategoryForLabel(label: string): 'pre' | 'payroll' | 'gov' | 'misc' {
		return labelToCategory[label] || 'misc';
	}
	const allDocLabels: string[] = [
		...preEmploymentItems.map((i) => i.label),
		...payrollFileItems.map((i) => i.label)
	];

	// Category key sets
	const preKeys = new Set(preEmploymentItems.map((i) => i.key));
	const payrollKeys = new Set(payrollFileItems.map((i) => i.key));
	const govKeys = new Set(governmentFileItems.map((i) => i.key));

	// Editable fields
	let form: Partial<UpdateUser & { password?: string }> = {};
	let original: Partial<UserResponse> = {};

	// Approved types (by document type label) used to disable uploads per item
	function getDocTypeNameById(id: number): string {
		const found = documentTypes.find((d) => d.id === id);
		return found ? found.name : '';
	}
	function slugifyName(name: string): string {
		return (name || '')
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '_')
			.replace(/^_+|_+$/g, '');
	}
	function getDocTypeIdForKey(key: string): number {
		const found = documentTypes.find((d) => slugifyName(d.name) === key);
		return found ? found.id : 0;
	}
	function getActiveDoc(label: string): User201FileResponse | undefined {
		const same = (my201 || []).filter((x) => getDocTypeNameById(x.document_type_id) === label);
		const active = same.find((x) => x.is_active);
		if (active) return active;
		return same.sort((a, b) => (b.version || 0) - (a.version || 0))[0];
	}
	function isDocApprovedLabel(label: string): boolean {
		const id = getDocTypeId(label);
		return (my201 || []).some((f) => f.document_type_id === id && f.status === 'Approved');
	}
	function isDocPendingLabel(label: string): boolean {
		return getActiveDoc(label)?.status === 'Pending';
	}
	$: approvedTypes = new Set(
		(my201 || [])
			.filter((f) => f.status === 'Approved')
			.map((f) => getDocTypeNameById(f.document_type_id))
			.filter((n) => !!n)
	);
	function isDocApprovedKey(key: string): boolean {
		const id = getDocTypeIdForKey(key);
		return (my201 || []).some((f) => f.document_type_id === id && f.status === 'Approved');
	}
	function isDocPendingKey(key: string): boolean {
		return getActiveDocByKey(key)?.status === 'Pending';
	}
	function getActiveDocByKey(key: string): User201FileResponse | undefined {
		const same = (my201 || []).filter(
			(x) => slugifyName(getDocTypeNameById(x.document_type_id)) === key
		);
		const active = same.find((x) => x.is_active);
		if (active) return active;
		return same.sort((a, b) => (b.version || 0) - (a.version || 0))[0];
	}

	// Reactive map of active documents for UI consistency
	$: activeDocs =
		my201 && documentTypes
			? allDocLabels.reduce(
					(acc, label) => {
						acc[label] = getActiveDoc(label);
						return acc;
					},
					{} as Record<string, User201FileResponse | undefined>
				)
			: {};

	// Required keys per category (exclude already approved items)
	function computeRequiredPreKeys(approvedTypesArg: Set<string>): string[] {
		return preEmploymentItems
			.filter((i) => i.key !== 'marriage_certificate' && !approvedTypesArg.has(i.label))
			.map((i) => i.key);
	}
	function computeRequiredPayrollKeys(approvedTypesArg: Set<string>): string[] {
		return payrollFileItems.filter((i) => !approvedTypesArg.has(i.label)).map((i) => i.key);
	}
	$: requiredPreKeys = computeRequiredPreKeys(approvedTypes);
	$: requiredPayrollKeys = computeRequiredPayrollKeys(approvedTypes);
	// Completeness checks
	$: preAllSelected = requiredPreKeys.every((k) => !!selectedDocs[k]);
	$: payrollAllSelected = requiredPayrollKeys.every((k) => !!selectedDocs[k]);
	$: hasRejectedPre = requiredPreKeys.some((k) => {
		const label = preEmploymentItems.find((i) => i.key === k)?.label || k;
		return getActiveDoc(label)?.status === 'Declined';
	});
	$: hasRejectedPayroll = requiredPayrollKeys.some((k) => {
		const label = payrollFileItems.find((i) => i.key === k)?.label || k;
		return getActiveDoc(label)?.status === 'Declined';
	});
	$: allRequiredKeys = [...requiredPreKeys, ...requiredPayrollKeys];
	$: allRequiredSelected = allRequiredKeys.every((k) => !!selectedDocs[k]);

	// Pattern validators for government IDs
	function isValidTin(v?: string): boolean {
		const d = (v || '').replace(/\D/g, '');
		return d.length === 9;
	}
	function isValidSSS(v?: string): boolean {
		const d = (v || '').replace(/\D/g, '');
		return d.length === 12;
	}
	function isValidPagibig(v?: string): boolean {
		const d = (v || '').replace(/\D/g, '');
		return d.length === 12;
	}
	function isValidPhilhealth(v?: string): boolean {
		const d = (v || '').replace(/\D/g, '');
		return d.length === 12;
	}
	$: govAllFilledValid =
		isValidTin(form.tin_number) &&
		isValidSSS(form.sss_number) &&
		isValidPagibig(form.pagibig_number) &&
		isValidPhilhealth(form.philhealth_number);

	function limitNumeric(value: string, maxLen: number): string {
		return (value || '').replace(/\D/g, '').slice(0, maxLen);
	}

	// Formatters for government IDs
	function formatTin(value: string): string {
		const d = (value || '').replace(/\D/g, '').slice(0, 9);
		const a = d.slice(0, 3);
		const b = d.slice(3, 6);
		const c = d.slice(6, 9);
		return [a, b, c].filter(Boolean).join('-');
	}
	function formatSSS(value: string): string {
		const d = (value || '').replace(/\D/g, '').slice(0, 12);
		const a = d.slice(0, 2);
		const b = d.slice(2, 11);
		const c = d.slice(11, 12);
		return [a, b, c].filter(Boolean).join('-');
	}
	function formatPagibig(value: string): string {
		const d = (value || '').replace(/\D/g, '').slice(0, 12);
		const a = d.slice(0, 2);
		const b = d.slice(2, 11);
		const c = d.slice(11, 12);
		return [a, b, c].filter(Boolean).join('-');
	}
	function formatPhilhealth(value: string): string {
		const d = (value || '').replace(/\D/g, '').slice(0, 12);
		const a = d.slice(0, 4);
		const b = d.slice(4, 8);
		const c = d.slice(8, 12);
		return [a, b, c].filter(Boolean).join('-');
	}

	function formatLeaveCredits(value?: number | null): string {
		if (value === null || value === undefined) return '—';
		// Round to nearest whole number or 0.5
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

	// Helper function to extract file type from filename
	function getFileType(fileName?: string): string {
		if (!fileName) return '';
		const match = fileName.match(/\.([a-zA-Z0-9]+)$/);
		return match ? match[1].toUpperCase() : '';
	}

	// Removed unused toISODate

	onMount(async () => {
		if (!authed) {
			goto(resolve('/login'));
			return;
		}
		try {
			user = await api.userAPI.getMe();
			branches = await api.branchAPI.getAllBranchesPublic().catch(() => []);
			systemOptions = await api.systemOptionsAPI.getAll().catch(() => []);
			my201 = await user201API.listMineActive().catch(() => []);
			documentTypes = await document_typeAPI.getAllPublic().catch(() => []);
			try {
				leaveCredits = await api.leaveCreditsAPI.getMyCredits();
			} catch (e) {
				leaveCreditsError = e instanceof Error ? e.message : 'Failed to load leave credits';
			}
			// Initialize form with current user values
			form.username = user.username;
			form.branch_id = user.branch_id;
			form.salutation = user.salutation;
			form.department = user.department;
			form.job_level = user.job_level;
			form.emergency_contact_name = user.emergency_contact_name;
			form.emergency_contact_number = user.emergency_contact_number;
			form.gotyme_account_name = user.gotyme_account_name;
			form.gotyme_account_number = user.gotyme_account_number;
			form.tin_number = user.tin_number;
			form.sss_number = user.sss_number;
			form.philhealth_number = user.philhealth_number;
			form.pagibig_number = user.pagibig_number;
			form.first_name = user.first_name;
			form.last_name = user.last_name;
			form.current_address_line = user.current_address_line;
			if (user.current_address_psgc) {
				const d = deriveFromPsgcCode(user.current_address_psgc);
				currProvinceCode = d.provinceCode;
				currMunCityCode = d.munCityCode;
				currBarangayCode = user.current_address_psgc;
			}
			original = { ...user };
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load profile';
		} finally {
			loading = false;
		}
	});

	// Reactive refresh helpers (no full page reload)
	let pollTimer: number | null = null;
	let toastUnsub: (() => void) | null = null;
	async function refreshMy201Active() {
		try {
			const latest = await user201API.listMineActive().catch(() => my201);
			if (JSON.stringify(latest) !== JSON.stringify(my201)) {
				my201 = latest;
			}
		} catch {
			/* ignore */
		}
	}
	$: {
		if (tab === 'employment' && pollTimer === null && typeof window !== 'undefined') {
			pollTimer = window.setInterval(refreshMy201Active, 30000);
			window.addEventListener('focus', refreshMy201Active);
			toastUnsub = currentToast.subscribe((n) => {
				if (n && n.type === 'user201') refreshMy201Active();
			});
		}
		if (tab !== 'employment' && pollTimer !== null && typeof window !== 'undefined') {
			window.clearInterval(pollTimer);
			pollTimer = null;
			window.removeEventListener('focus', refreshMy201Active);
			if (toastUnsub) {
				toastUnsub();
				toastUnsub = null;
			}
		}
	}
	onDestroy(() => {
		if (pollTimer !== null && typeof window !== 'undefined') {
			window.clearInterval(pollTimer);
			pollTimer = null;
			window.removeEventListener('focus', refreshMy201Active);
		}
		if (toastUnsub) {
			toastUnsub();
			toastUnsub = null;
		}
	});

	function computeChanges(): Partial<UpdateUser & { password?: string }> {
		const changes: Partial<UpdateUser & { password?: string }> = {};
		const keys: (keyof (UpdateUser & { password?: string }))[] = [
			'username',
			'branch_id',
			'salutation',
			'department',
			'job_level',
			'emergency_contact_name',
			'emergency_contact_number',
			'gotyme_account_name',
			'gotyme_account_number',
			'tin_number',
			'sss_number',
			'philhealth_number',
			'pagibig_number',
			'first_name',
			'last_name',
			'password',
			'current_address_line',
			'current_address_psgc'
		];
		for (const k of keys) {
			const newVal = (form as Record<string, unknown>)[k as string];
			const oldVal = (original as Record<string, unknown>)[k as string];
			if (newVal !== undefined && newVal !== oldVal && newVal !== '') {
				(changes as Record<string, unknown>)[k as string] = newVal;
			}
		}
		return changes;
	}

	let avatarLoading = false;

	async function handleAvatarChange(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files || input.files.length === 0) return;
		const file = input.files[0];

		if (file.size > 2 * 1024 * 1024) {
			error = 'Image size must be less than 2MB';
			return;
		}
		if (!file.type.startsWith('image/')) {
			error = 'Only image files are allowed';
			return;
		}

		try {
			avatarLoading = true;
			const updatedUser = await api.userAPI.uploadAvatar(file);

			user = updatedUser;
			original = { ...updatedUser };
			success = 'Profile picture updated successfully';
			if (typeof window !== 'undefined') {
				window.dispatchEvent(new CustomEvent('profile-updated'));
			}
		} catch (err: any) {
			console.error(err);
			error = err.message || 'Failed to update profile picture';
		} finally {
			avatarLoading = false;
			input.value = '';
		}
	}

	async function save() {
		error = null;
		success = null;
		if (!user) return;
		form.current_address_psgc = currBarangayCode;
		const changes = computeChanges();
		if (Object.keys(changes).length === 0) {
			success = 'No changes to save';
			return;
		}
		try {
			const updated = await api.userAPI.updateMe(changes);
			user = updated;
			original = { ...updated };
			success = 'Profile updated successfully';
			form.password = '';
			// Re-sync current-address dropdowns from what actually got saved
			if (updated.current_address_psgc) {
				const d = deriveFromPsgcCode(updated.current_address_psgc);
				currProvinceCode = d.provinceCode;
				currMunCityCode = d.munCityCode;
				currBarangayCode = updated.current_address_psgc;
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to update profile';
		}
	}

	// Removed unused single-upload handlers

	function isAllowedFile(file: File): boolean {
		const t = (file.type || '').toLowerCase();
		if (ALLOWED_TYPES.includes(t)) return true;
		const ext = (file.name.split('.').pop() || '').toLowerCase();
		return ['pdf', 'png', 'jpg', 'jpeg', 'img'].includes(ext);
	}
	function detectContentType(file: File): string {
		const t = (file.type || '').toLowerCase();
		if (ALLOWED_TYPES.includes(t)) return t;
		const ext = (file.name.split('.').pop() || '').toLowerCase();
		if (ext === 'pdf') return 'application/pdf';
		if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg';
		if (ext === 'png') return 'image/png';
		if (ext === 'webp') return 'image/webp';
		return 'application/octet-stream';
	}
	function onDocSelected(key: string, e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files && input.files[0] ? input.files[0] : null;
		if (file) {
			if (!isAllowedFile(file)) {
				error = 'Only PDF, JPG, PNG, or WebP files are allowed';
				selectedDocs[key] = null;
				return;
			}
			if (file.size > MAX_SIZE_BYTES) {
				error = 'File size exceeds 10 MB limit';
				selectedDocs[key] = null;
				return;
			}
		}
		selectedDocs[key] = file;
		selectedDocs = { ...selectedDocs };
		// Auto-upload this single file immediately (no page refresh needed)
		if (file) {
			void autoUploadSingle(key);
		}
	}

	let galleryModalOpen = false;
	let reuploadLabel: string | null = null;
	let galleryModalTitle = '';
	let galleryItems: { name: string; url: string; file: User201FileResponse }[] = [];
	let galleryLoading = false;
	let remarksModalOpen = false;
	let remarksModalTitle = '';
	let remarksModalText = '';
	let confirmOpen = false;
	let confirmMessage = '';
	let confirmLoading = false;
	let confirmAction: (() => Promise<void> | void) | null = null;
	function openConfirm(msg: string, action: () => Promise<void> | void) {
		confirmMessage = msg;
		confirmAction = action;
		confirmOpen = true;
		confirmLoading = false;
	}
	function closeConfirm() {
		confirmOpen = false;
		confirmMessage = '';
		confirmAction = null;
		confirmLoading = false;
	}
	async function proceedConfirm() {
		if (!confirmAction) return;
		confirmLoading = true;
		try {
			await Promise.resolve(confirmAction());
		} finally {
			confirmLoading = false;
			closeConfirm();
		}
	}
	let cancelingLabels = new Set<string>();

	async function openGalleryFor(kind: 'Pre-employment Requirements' | 'Payroll Requirements') {
		galleryModalTitle = kind;
		galleryLoading = true;
		const targetCategory = kind === 'Pre-employment Requirements' ? 'pre-employment' : 'payroll';

		const source = my201.filter((f) => {
			const dt = documentTypes.find((d) => d.id === f.document_type_id);
			return dt?.category === targetCategory;
		});

		const items: { name: string; url: string; file: User201FileResponse }[] = [];
		for (const f of source) {
			const dt = documentTypes.find((d) => d.id === f.document_type_id);
			let url = f.file_url || '';
			if (f.s3_path) {
				try {
					const pr = await user201API.presignDownload(f.s3_path);
					url = pr.download_url;
				} catch {
					url = f.file_url || '';
				}
			}
			url = normalizeFileUrl(url);
			items.push({ name: dt?.name || f.file_name, url, file: f });
		}
		galleryItems = items;
		galleryModalOpen = true;
		galleryLoading = false;
	}

	function closeGallery() {
		galleryModalOpen = false;
		galleryItems = [];
		galleryModalTitle = '';
	}

	function openRemarksByKey(key: string) {
		const d = getActiveDocByKey(key);
		remarksModalTitle = key;
		remarksModalText = d && d.remarks ? d.remarks : 'No remarks provided';
		remarksModalOpen = true;
	}
	function openRemarksByLabel(label: string) {
		const d = getActiveDoc(label);
		remarksModalTitle = label;
		remarksModalText = d && d.remarks ? d.remarks : 'No remarks provided';
		remarksModalOpen = true;
	}
	function closeRemarks() {
		remarksModalOpen = false;
		remarksModalTitle = '';
		remarksModalText = '';
	}

	function isPdfItem(it: { name: string; file: User201FileResponse }): boolean {
		const name = (it.file.file_name || it.name || '').toLowerCase();
		return name.endsWith('.pdf');
	}

	function normalizeFileUrl(raw: string): string {
		if (!raw) return '';
		if (raw.startsWith('/static/')) {
			return `${API_BASE}${raw}`;
		}
		return raw;
	}

	async function deleteFile(file: User201FileResponse) {
		if (!confirm('Are you sure you want to delete this file?')) return;
		try {
			await user201API.remove(file.id);
			my201 = await user201API.listMineActive();
			// If we are in gallery view, we should refresh the gallery items too
			if (galleryModalOpen) {
				galleryItems = galleryItems.filter((it) => it.file.id !== file.id);
			}
			success = 'File deleted successfully';
		} catch (e: unknown) {
			console.error(e);
			error = 'Failed to delete file';
		}
	}

	async function openPreview(doc: User201FileResponse) {
		galleryModalTitle = getDocTypeNameById(doc.document_type_id) || doc.file_name;
		galleryLoading = true;
		galleryModalOpen = true;
		galleryItems = [];
		try {
			let url = doc.file_url || '';
			if (doc.s3_path) {
				const pr = await user201API.presignDownload(doc.s3_path);
				url = pr.download_url;
			}
			url = normalizeFileUrl(url);
			galleryItems = [{ name: galleryModalTitle, url, file: doc }];
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load preview';
		} finally {
			galleryLoading = false;
		}
	}

	function openPreviewByLabel(label: string) {
		const d = getActiveDoc(label);
		if (d) openPreview(d);
	}

	function closePreview() {
		// Deprecated, use closeGallery
		closeGallery();
	}

	async function downloadFile(doc: User201FileResponse) {
		try {
			let url = doc.file_url || '';
			if (doc.s3_path) {
				const pr = await user201API.presignDownload(doc.s3_path);
				url = pr.download_url;
			}
			url = normalizeFileUrl(url);
			if (!url) {
				throw new Error('No download URL available');
			}
			const res = await fetch(url);
			if (!res.ok) {
				throw new Error('Download failed');
			}
			const blob = await res.blob();
			const objectUrl = URL.createObjectURL(blob);
			const link = document.createElement('a');
			const name = doc.file_name || getDocTypeNameById(doc.document_type_id) || 'document';
			link.href = objectUrl;
			link.download = name;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			URL.revokeObjectURL(objectUrl);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Download failed';
		}
	}
	function downloadByLabel(label: string) {
		const d = getActiveDoc(label);
		if (d) downloadFile(d);
	}
	function reuploadFile(label: string) {
		reuploadLabel = label;
		document.getElementById('reupload_input')?.click();
	}
	function updateFile(label: string) {
		openConfirm('Updating will remove the previous/current file', () => {
			reuploadLabel = label;
			document.getElementById('reupload_input')?.click();
		});
	}
	function cancelFile(label: string) {
		const doc = getActiveDoc(label);
		if (!doc || doc.status !== 'Pending') return;
		openConfirm('Cancelling will remove the previous file and cancel request', async () => {
			cancelingLabels.add(label);
			cancelingLabels = new Set(cancelingLabels);
			try {
				await user201API.remove(doc.id);
				my201 = await user201API.listMineActive();
				if (galleryModalOpen) {
					galleryItems = galleryItems.filter((it) => it.file.id !== doc.id);
				}
				success = 'Request cancelled';
				addNotification({
					title: '201 File Request Cancelled',
					message: `${label} cancellation successful`,
					type: 'user201',
					action: 'declined',
					target_route: '/profile?tab=employment'
				});
			} catch (e: unknown) {
				error = e instanceof Error ? e.message : 'Cancel failed';
			} finally {
				cancelingLabels.delete(label);
				cancelingLabels = new Set(cancelingLabels);
			}
		});
	}
	function getDocTypeId(label: string): number {
		const found = documentTypes.find((d) => d.name === label);
		return found ? found.id : 0;
	}

	async function autoUploadSingle(key: string) {
		if (!user) return;
		const file = selectedDocs[key];
		if (!file) return;
		uploading[key] = true;
		uploading = { ...uploading };
		try {
			const isPre = preKeys.has(key);
			const isPayroll = payrollKeys.has(key);
			const category = isPre ? 'pre' : isPayroll ? 'payroll' : 'misc';
			if (!isPre && !isPayroll) {
				error = 'Unsupported item for auto-upload';
				return;
			}
			const label = isPre
				? preEmploymentItems.find((i) => i.key === key)?.label || key
				: payrollFileItems.find((i) => i.key === key)?.label || key;
			const current = getActiveDoc(label);
			if (current) {
				my201 = my201.map((f) => (f.id === current.id ? { ...f, is_active: false } : f));
			}

			// New flow: Upload temp -> Create
			const uploaded = await user201API.uploadTemp(file);

			const created = await user201API.create({
				user_id: user.id,
				file_name: file.name,
				document_type_id: getDocTypeId(label),
				file_url: uploaded.file_url,
				s3_path: '', // Empty initially
				status: 'Pending'
			});
			my201 = [created, ...my201];
			delete selectedDocs[key];
			selectedDocs = { ...selectedDocs };
			success = 'File uploaded for approval';
			error = null;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			await refreshMy201Active();
			delete uploading[key];
			uploading = { ...uploading };
		}
	}

	async function onReuploadSelected(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files && input.files[0] ? input.files[0] : null;
		input.value = '';
		if (!file || !reuploadLabel || !user) return;
		if (!isAllowedFile(file)) {
			error = 'Only PDF, PNG, JPG, JPEG, or IMG files are allowed';
			return;
		}
		if (file.size > MAX_SIZE_BYTES) {
			error = 'File size exceeds 10 MB limit';
			return;
		}
		try {
			const current = getActiveDoc(reuploadLabel);
			if (current) {
				my201 = my201.map((f) => (f.id === current.id ? { ...f, is_active: false } : f));
			}

			// New flow: Upload temp -> Create
			const uploaded = await user201API.uploadTemp(file);

			const created = await user201API.create({
				user_id: user.id,
				file_name: file.name,
				document_type_id: getDocTypeId(reuploadLabel),
				file_url: uploaded.file_url,
				s3_path: '', // Empty initially
				status: 'Pending'
			});
			my201 = [created, ...my201];
			success = 'File re-uploaded for approval';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Re-upload failed';
		} finally {
			reuploadLabel = null;
			await refreshMy201Active();
		}
	}

	async function updatePreDocs() {
		error = null;
		success = null;
		if (!user) return;
		if (!Array.from(preKeys).some((k) => !!selectedDocs[k])) {
			error = 'Choose at least one file';
			return;
		}
		bulkUploading = true;
		try {
			const created: User201FileResponse[] = [];
			for (const k of Array.from(preKeys)) {
				const file = selectedDocs[k];
				if (!file) continue;
				if (!isAllowedFile(file)) continue;
				if (file.size > MAX_SIZE_BYTES) continue;
				const label = preEmploymentItems.find((i) => i.key === k)?.label || k;
				const current = getActiveDoc(label);
				if (current) {
					my201 = my201.map((f) => (f.id === current.id ? { ...f, is_active: false } : f));
				}
				const presigned = await user201API.presign(file.name, detectContentType(file), 'pre');
				await fetch(presigned.upload_url, {
					method: 'PUT',
					headers: { 'Content-Type': detectContentType(file) },
					body: file
				});
				const res = await user201API.create({
					user_id: user.id,
					file_name: file.name,
					document_type_id: getDocTypeId(label),
					file_url: presigned.file_url,
					s3_path: presigned.key,
					status: 'Pending'
				});
				created.push(res);
				delete selectedDocs[k];
			}
			if (created.length > 0) {
				my201 = [...created, ...my201];
				selectedDocs = { ...selectedDocs };
				success = 'Selected Pre-employment files updated';
			} else {
				error = 'Choose at least one file';
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Update failed';
		} finally {
			await refreshMy201Active();
			bulkUploading = false;
		}
	}

	async function updatePayrollDocs() {
		error = null;
		success = null;
		if (!user) return;
		if (!Array.from(payrollKeys).some((k) => !!selectedDocs[k])) {
			error = 'Choose at least one file';
			return;
		}
		bulkUploading = true;
		try {
			const created: User201FileResponse[] = [];
			for (const k of Array.from(payrollKeys)) {
				const file = selectedDocs[k];
				if (!file) continue;
				if (!isAllowedFile(file)) continue;
				if (file.size > MAX_SIZE_BYTES) continue;
				const label = payrollFileItems.find((i) => i.key === k)?.label || k;
				const current = getActiveDoc(label);
				if (current) {
					my201 = my201.map((f) => (f.id === current.id ? { ...f, is_active: false } : f));
				}
				const presigned = await user201API.presign(file.name, detectContentType(file), 'payroll');
				await fetch(presigned.upload_url, {
					method: 'PUT',
					headers: { 'Content-Type': detectContentType(file) },
					body: file
				});
				const res = await user201API.create({
					user_id: user.id,
					file_name: file.name,
					document_type_id: getDocTypeId(label),
					file_url: presigned.file_url,
					s3_path: presigned.key,
					status: 'Pending'
				});
				created.push(res);
				delete selectedDocs[k];
			}
			if (created.length > 0) {
				my201 = [...created, ...my201];
				selectedDocs = { ...selectedDocs };
				success = 'Selected Payroll files updated';
			} else {
				error = 'Choose at least one file';
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Update failed';
		} finally {
			await refreshMy201Active();
			bulkUploading = false;
		}
	}

	async function uploadAllDocs() {
		error = null;
		success = null;
		if (!user) return;
		const labelsByKey: Record<string, string> = Object.fromEntries(
			[...preEmploymentItems, ...payrollFileItems].map((i) => [i.key, i.label])
		);
		const entries = Object.entries(selectedDocs).filter(([, f]) => !!f) as [string, File][];
		if (entries.length === 0) {
			error = 'Choose at least one file';
			return;
		}
		bulkUploading = true;
		try {
			const created: User201FileResponse[] = [];
			for (const [key, file] of entries) {
				const category = preKeys.has(key)
					? 'pre'
					: payrollKeys.has(key)
						? 'payroll'
						: govKeys.has(key)
							? 'gov'
							: 'misc';
				if (!isAllowedFile(file)) {
					error = 'Only PDF, JPG, PNG, or WebP files are allowed';
					break;
				}
				if (file.size > MAX_SIZE_BYTES) {
					error = 'One or more files exceed the 10 MB limit';
					break;
				}
				const presigned = await user201API.presign(file.name, detectContentType(file), category);
				await fetch(presigned.upload_url, {
					method: 'PUT',
					headers: { 'Content-Type': detectContentType(file) },
					body: file
				});
				const res = await user201API.create({
					user_id: user.id,
					file_name: file.name,
					document_type_id: getDocTypeId(labelsByKey[key] || key),
					file_url: presigned.file_url,
					s3_path: presigned.key,
					status: 'Pending'
				});
				created.push(res);
			}
			my201 = [...created, ...my201];
			selectedDocs = {};
			success = 'Files uploaded for approval';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			await refreshMy201Active();
			bulkUploading = false;
		}
	}

	async function uploadPreDocs() {
		error = null;
		success = null;
		if (!user) return;
		const onlyMarriageSelected =
			!!selectedDocs['marriage_certificate'] && requiredPreKeys.every((k) => !selectedDocs[k]);
		if (!preAllSelected && !onlyMarriageSelected) {
			error = 'Select all Pre-employment files';
			return;
		}
		bulkUploading = true;
		try {
			const created: User201FileResponse[] = [];
			const keysToUpload = onlyMarriageSelected ? ['marriage_certificate'] : requiredPreKeys;
			for (const k of keysToUpload) {
				const file = selectedDocs[k]!;
				const label = preEmploymentItems.find((i) => i.key === k)?.label || k;
				const presigned = await user201API.presign(file.name, detectContentType(file), 'pre');
				await fetch(presigned.upload_url, {
					method: 'PUT',
					headers: { 'Content-Type': detectContentType(file) },
					body: file
				});
				const res = await user201API.create({
					user_id: user.id,
					file_name: file.name,
					document_type_id: getDocTypeId(label),
					file_url: presigned.file_url,
					s3_path: presigned.key,
					status: 'Pending'
				});
				created.push(res);
			}
			my201 = [...created, ...my201];
			for (const k of keysToUpload) delete selectedDocs[k];
			selectedDocs = { ...selectedDocs };
			success = onlyMarriageSelected
				? 'Marriage Certificate uploaded for approval'
				: 'Pre-employment files uploaded for approval';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			await refreshMy201Active();
			bulkUploading = false;
		}
	}

	async function uploadPayrollDocs() {
		error = null;
		success = null;
		if (!user) return;
		if (!payrollAllSelected) {
			error = 'Select all Payroll files';
			return;
		}
		bulkUploading = true;
		try {
			const created: User201FileResponse[] = [];
			for (const k of requiredPayrollKeys) {
				const file = selectedDocs[k]!;
				const label = payrollFileItems.find((i) => i.key === k)?.label || k;
				const presigned = await user201API.presign(file.name, detectContentType(file), 'payroll');
				await fetch(presigned.upload_url, {
					method: 'PUT',
					headers: { 'Content-Type': detectContentType(file) },
					body: file
				});
				const res = await user201API.create({
					user_id: user.id,
					file_name: file.name,
					document_type_id: getDocTypeId(label),
					file_url: presigned.file_url,
					s3_path: presigned.key,
					status: 'Pending'
				});
				created.push(res);
			}
			my201 = [...created, ...my201];
			for (const k of requiredPayrollKeys) delete selectedDocs[k];
			selectedDocs = { ...selectedDocs };
			success = 'Payroll files uploaded for approval';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			await refreshMy201Active();
			bulkUploading = false;
		}
	}

	async function saveGovernment() {
		error = null;
		success = null;
		if (!govAllFilledValid) {
			error = 'Fill all Government IDs in the correct format';
			addNotification({ title: 'Error', message: error });
			return;
		}
		await save();
		if (success) {
			addNotification({ title: 'Success', message: 'Government IDs saved' });
		} else if (error) {
			addNotification({ title: 'Error', message: error });
		} else {
			addNotification({ title: 'Info', message: 'No changes to save' });
		}
	}

	function resetForm() {
		if (!user) return;
		form.username = user.username;
		form.branch_id = user.branch_id;
		form.salutation = user.salutation;
		form.department = user.department;
		form.job_level = user.job_level;
		form.emergency_contact_name = user.emergency_contact_name;
		form.emergency_contact_number = user.emergency_contact_number;
		form.gotyme_account_name = user.gotyme_account_name;
		form.gotyme_account_number = user.gotyme_account_number;
		form.tin_number = user.tin_number;
		form.sss_number = user.sss_number;
		form.philhealth_number = user.philhealth_number;
		form.pagibig_number = user.pagibig_number;
		form.first_name = user.first_name;
		form.last_name = user.last_name;
		form.current_address_line = user.current_address_line;
		if (user.current_address_psgc) {
			const d = deriveFromPsgcCode(user.current_address_psgc);
			currProvinceCode = d.provinceCode;
			currMunCityCode = d.munCityCode;
			currBarangayCode = user.current_address_psgc;
		} else {
			currProvinceCode = '';
			currMunCityCode = '';
			currBarangayCode = '';
		}
		form.password = '';
		success = null;
		error = null;
	}
</script>

<div class="container mx-auto px-4 py-6">
	<div class="mb-4">
		<h1 class="text-2xl font-semibold">My Profile</h1>
	</div>

	{#if loading}
		<p>Loading profile...</p>
	{:else if error}
		<div
			class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700 dark:border-red-600 dark:bg-red-900 dark:text-red-200"
		>
			{error}
		</div>
	{:else if user}
		<!-- Image & Summary Section -->
		<div
			class="mb-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800"
		>
			<div class="flex items-center gap-4">
				<Avatar
					firstName={user.first_name}
					lastName={user.last_name}
					username={user.username}
					src={user.profile_picture_url}
					size="2xl"
				/>
				<div class="flex-1">
					<div class="text-2xl font-semibold text-neutral-900 dark:text-white">
						{(() => {
							const fullName = `${user?.first_name || ''} ${user?.last_name || ''}`.trim();
							return fullName || user.username;
						})()}
					</div>
					<div class="text-sm text-neutral-600 dark:text-gray-300">{user?.job_level ?? '—'}</div>

					<div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
						<div class="flex items-center gap-2 text-sm sm:col-span-2">
							<Icon icon="mdi:gmail" class="h-4 w-4 text-red-500" />
							<span class="text-neutral-800 dark:text-gray-200"> Email: {user?.email ?? '—'}</span>
						</div>

						<div class="flex items-center gap-2 text-sm">
							<Icon icon="mdi:phone" class="h-4 w-4 text-green-600" />
							<span class="text-neutral-800 dark:text-gray-200">
								Phone Number: {user?.phone_number ?? '—'}
							</span>
						</div>

						<div class="flex items-center gap-2 text-sm">
							<Icon icon="mdi:calendar" class="h-4 w-4 text-blue-600" />
							<span class="text-neutral-800 dark:text-gray-200">
								Birthdate: {user?.birthdate ?? '—'}
							</span>
						</div>

						<div class="flex items-center gap-2 text-sm">
							<Icon icon="mdi:map-marker" class="h-4 w-4 text-blue-600" />
							<span class="text-neutral-800 dark:text-gray-200">
								Permanent Address: {permanentAddressDisplay}
							</span>
						</div>

						<div class="flex items-center gap-2 text-sm">
							<Icon icon="mdi:account-heart" class="h-4 w-4 text-purple-600" />
							<span class="text-neutral-800 dark:text-gray-200">
								Civil Status: {user?.civil_status ?? '—'}
							</span>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Tabs -->
		<div class="mb-4 flex gap-2">
			<button
				class="rounded border px-4 py-2 text-sm font-medium"
				class:!bg-blue-600={tab === 'personal'}
				class:!text-white={tab === 'personal'}
				on:click={() => (tab = 'personal')}>Personal Details</button
			>
			<button
				class="rounded border px-4 py-2 text-sm font-medium"
				class:!bg-blue-600={tab === 'employment'}
				class:!text-white={tab === 'employment'}
				on:click={() => (tab = 'employment')}>Employment Details</button
			>
		</div>

		{#if tab === 'personal'}
			<div
				class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800"
			>
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

				<form on:submit|preventDefault={save} class="space-y-4">
					<div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
						<!-- Personal fields: two explicit stacked columns so we can pin
						     Civil Status directly below Birthdate, rather than relying
						     on grid auto-flow row order. -->
						<div class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:col-span-2">
							<div class="space-y-4">
								<div>
									<label
										for="first_name"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">First Name</label
									>
									<input
										id="first_name"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none read-only:cursor-not-allowed read-only:opacity-60 dark:border-gray-700 dark:bg-transparent"
										type="text"
										bind:value={form.first_name}
										readonly={!isAdmin}
										placeholder="First name"
									/>
								</div>
								<div>
									<label
										for="salutation"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Salutation</label
									>
									<select
										id="salutation"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-transparent"
										bind:value={form.salutation}
										disabled={!isAdmin}
									>
										<option value="">Select Salutation</option>
										{#each salutations as s}
											<option value={s.value}>{s.value}</option>
										{/each}
									</select>
								</div>
								<div>
									<label
										for="job_level"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Job Level</label
									>
									<select
										id="job_level"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-transparent"
										bind:value={form.job_level}
										disabled={!isAdmin}
									>
										<option value="">Select Job Level</option>
										{#each jobLevels as j}
											<option value={j.value}>{j.value}</option>
										{/each}
									</select>
								</div>
								<div>
									<label
										for="username"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Username</label
									>
									<input
										id="username"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none read-only:cursor-not-allowed read-only:opacity-60 dark:border-gray-700 dark:bg-transparent"
										type="text"
										bind:value={form.username}
										readonly={!isAdmin}
										placeholder="Username"
									/>
								</div>
								<div>
									<label
										for="emergency_contact_name"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400"
										>Emergency Contact Name</label
									>
									<input
										id="emergency_contact_name"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
										type="text"
										bind:value={form.emergency_contact_name}
										placeholder="Contact name"
									/>
								</div>
							</div>
							<div class="space-y-4">
	<div>
		<label
			for="last_name"
			class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Last Name</label
		>
		<input
			id="last_name"
			class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none read-only:cursor-not-allowed read-only:opacity-60 dark:border-gray-700 dark:bg-transparent"
			type="text"
			bind:value={form.last_name}
			readonly={!isAdmin}
			placeholder="Last name"
		/>
	</div>
	<div>
		<label
			for="branch"
			class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Branch</label
		>
		<select
			id="branch"
			class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-transparent"
			bind:value={form.branch_id}
			disabled={!isAdmin}
		>
			<option value="">Select Branch</option>
			{#each branches as b (b.id)}
				<option value={b.id}>{b.branch_name}</option>
			{/each}
		</select>
	</div>
	<div>
		<label
			for="department"
			class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Department</label
		>
		<select
			id="department"
			class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-transparent"
			bind:value={form.department}
			disabled={!isAdmin}
		>
			<option value="">Select Department</option>
			{#each departments as d}
				<option value={d.value}>{d.value}</option>
			{/each}
		</select>
	</div>
	<div>
		<label
			for="emergency_contact_number"
			class="mb-1 block text-xs text-neutral-500 dark:text-gray-400"
			>Emergency Contact Number</label
		>
		<input
			id="emergency_contact_number"
			class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
			type="tel"
			inputmode="numeric"
			pattern="[0-9]*"
			bind:value={form.emergency_contact_number}
			on:input={(e) =>
				(form.emergency_contact_number = (e.target as HTMLInputElement).value.replace(
					/\D/g,
					''
				))}
			placeholder="Contact number"
		/>
	</div>
</div>
							<div class="sm:col-span-2">
								<label for="password" class="mb-1 block text-xs text-neutral-500 dark:text-gray-400"
									>New Password</label
								>
								<input
									id="password"
									class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
									type="password"
									bind:value={form.password}
									placeholder="Leave blank to keep current"
								/>
							</div>
						</div>

						<!-- Current Address: the one address block editable from here. -->
						<div class="lg:col-span-1">
							<div class="space-y-4">
								<div>
									<label
										for="curr_province"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Province</label
									>
									<select
										id="curr_province"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
										bind:value={currProvinceCode}
										on:change={onCurrProvinceChange}
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
									<label
										for="curr_muncity"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400"
										>City/Municipality</label
									>
									<select
										id="curr_muncity"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:text-gray-400 dark:border-gray-700 dark:bg-transparent"
										bind:value={currMunCityCode}
										on:change={onCurrMunCityChange}
										disabled={!currProvinceCode || currMuncities.length <= 1}
									>
										<option value="">Select City/Municipality</option>
										{#each currMuncities as m (m.munCityCode)}
											<option value={m.munCityCode}>{m.munCityName}</option>
										{/each}
									</select>
								</div>
								<div>
									<label
										for="curr_barangay"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">Barangay</label
									>
									<select
										id="curr_barangay"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:text-gray-400 dark:border-gray-700 dark:bg-transparent"
										bind:value={currBarangayCode}
										disabled={!currEffectiveMunCityCode}
									>
										<option value="">Select Barangay</option>
										{#each currBarangays as b (b.psgcCode)}
											<option value={b.psgcCode}
												>{b.brgyOldName ? `${b.brgyName} (${b.brgyOldName})` : b.brgyName}</option
											>
										{/each}
									</select>
								</div>
								<div>
									<label
										for="current_address_line"
										class="mb-1 block text-xs text-neutral-500 dark:text-gray-400"
										>House No./Street</label
									>
									<input
										id="current_address_line"
										class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
										type="text"
										bind:value={form.current_address_line}
										placeholder="House No./Street"
									/>
								</div>
							</div>
						</div>
					</div>

					<div class="flex items-center gap-2">
						<button
							type="submit"
							class="inline-flex items-center rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
							>Save Changes</button
						>
						<button
							type="button"
							on:click={resetForm}
							class="inline-flex items-center rounded bg-gray-200 px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
							>Reset</button
						>
					</div>
				</form>
			</div>
		{:else if tab === 'employment'}
			<div
				class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800"
			>
				<div class="mt-6 mb-3 text-lg font-semibold">Government Mandated Requirements</div>
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
					<div>
						<label
							for="tin_number_emp"
							class="mb-1 block text-xs text-neutral-500 dark:text-gray-400"
							>Tax Identification Number (TIN)</label
						>
						<input
							id="tin_number_emp"
							inputmode="numeric"
							maxlength={11}
							pattern="^\d{3}-\d{3}-\d{3}$"
							class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
							type="text"
							bind:value={form.tin_number}
							on:input={(e) => (form.tin_number = formatTin((e.target as HTMLInputElement).value))}
							placeholder="000-000-000"
						/>
					</div>
					<div>
						<label
							for="sss_number_emp"
							class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">SSS Number</label
						>
						<input
							id="sss_number_emp"
							inputmode="numeric"
							maxlength={14}
							pattern="^\d{2}-\d{9}-\d$"
							class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
							type="text"
							bind:value={form.sss_number}
							on:input={(e) => (form.sss_number = formatSSS((e.target as HTMLInputElement).value))}
							placeholder="00-000000000-0"
						/>
					</div>
					<div>
						<label
							for="philhealth_number_emp"
							class="mb-1 block text-xs text-neutral-500 dark:text-gray-400"
							>PhilHealth Number</label
						>
						<input
							id="philhealth_number_emp"
							inputmode="numeric"
							maxlength={14}
							pattern="^\d{4}-\d{4}-\d{4}$"
							class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
							type="text"
							bind:value={form.philhealth_number}
							on:input={(e) =>
								(form.philhealth_number = formatPhilhealth((e.target as HTMLInputElement).value))}
							placeholder="0000-0000-0000"
						/>
					</div>
					<div>
						<label
							for="pagibig_number_emp"
							class="mb-1 block text-xs text-neutral-500 dark:text-gray-400">PAG-IBIG Number</label
						>
						<input
							id="pagibig_number_emp"
							inputmode="numeric"
							maxlength={14}
							pattern="^\d{2}-\d{9}-\d$"
							class="w-full border-0 border-b border-neutral-300 bg-transparent px-0 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-transparent"
							type="text"
							bind:value={form.pagibig_number}
							on:input={(e) =>
								(form.pagibig_number = formatPagibig((e.target as HTMLInputElement).value))}
							placeholder="00-000000000-0"
						/>
					</div>
				</div>

				<div class="mt-3">
					<button
						class="inline-flex items-center rounded bg-blue-600 px-3 py-1.5 text-white disabled:opacity-50"
						disabled={false}
						on:click={saveGovernment}
					>
						Save Government IDs
					</button>
				</div>

				<div class="mt-6 mb-3 text-lg font-semibold">Document Status & Actions</div>
				<div class="overflow-x-auto">
					<table class="w-full border-collapse">
						<thead>
							<tr class="border-b dark:border-gray-700">
								<th class="py-2 text-left">Document</th>
								<th class="py-2 text-left">Status</th>
								<th class="py-2 text-left">Action</th>
							</tr>
						</thead>
						<tbody>
							{#each allDocLabels as label (label)}
								<tr class="border-b dark:border-gray-700">
									<td class="py-2">{label}</td>
									<td class="py-2">
										{#if activeDocs[label]}
											{#if activeDocs[label]?.status === 'Approved'}
												<span class="inline-flex items-center text-green-700 dark:text-green-400">
													<Icon icon="mdi:check-circle" class="mr-1 h-4 w-4" /> Approved
												</span>
											{:else if activeDocs[label]?.status === 'Declined'}
												<span class="inline-flex items-center text-red-700 dark:text-red-400">
													<Icon icon="mdi:close-circle" class="mr-1 h-4 w-4" /> Declined
												</span>
											{:else}
												<span class="inline-flex items-center text-yellow-700 dark:text-yellow-400">
													<Icon icon="mdi:hourglass-half" class="mr-1 h-4 w-4" /> Pending
												</span>
											{/if}
										{:else}
											<span class="inline-flex items-center text-gray-500 dark:text-gray-400">
												<Icon icon="mdi:file-remove-outline" class="mr-1 h-4 w-4" /> No File
											</span>
										{/if}
									</td>
									<td class="py-2">
										{#if activeDocs[label]}
											<button
												class="mr-2 inline-flex items-center text-blue-600 disabled:opacity-50 dark:text-blue-400"
												disabled={!activeDocs[label]?.file_url || cancelingLabels.has(label)}
												on:click={() => openPreviewByLabel(label)}
											>
												<Icon icon="mdi:eye" class="mr-1 h-4 w-4" /> View
											</button>
											{#if activeDocs[label]?.status === 'Approved'}
												<button
													class="mr-2 inline-flex items-center text-green-600 dark:text-green-400"
													on:click={() => downloadByLabel(label)}
												>
													<Icon icon="mdi:download" class="mr-1 h-4 w-4" /> Download
													{#if activeDocs[label]?.file_name}
														<span class="ml-1 text-xs text-gray-600 dark:text-gray-400">
															({getFileType(activeDocs[label]?.file_name)})
														</span>
													{/if}
												</button>
												<button
													class="inline-flex items-center text-gray-700 dark:text-gray-300"
													on:click={() => updateFile(label)}
												>
													<Icon icon="mdi:update" class="mr-1 h-4 w-4" /> Update
												</button>
											{:else if activeDocs[label]?.status === 'Declined'}
												<button
													class="inline-flex items-center text-red-600 dark:text-red-400"
													on:click={() => reuploadFile(label)}
												>
													<Icon icon="mdi:refresh" class="mr-1 h-4 w-4" /> Re-upload
												</button>
											{:else if activeDocs[label]?.status === 'Pending'}
												<button
													class="inline-flex items-center text-orange-600 dark:text-orange-400"
													on:click={() => cancelFile(label)}
												>
													<Icon icon="mdi:cancel" class="mr-1 h-4 w-4" /> Cancel
												</button>
											{/if}
										{:else}
											<button
												class="inline-flex items-center text-blue-600 dark:text-blue-400"
												on:click={() => reuploadFile(label)}
											>
												<Icon icon="mdi:upload" class="mr-1 h-4 w-4" /> Upload
											</button>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<input
					id="reupload_input"
					type="file"
					accept="image/*,.pdf"
					class="hidden"
					on:change={onReuploadSelected}
				/>
			</div>
		{/if}
	{/if}
</div>

<!-- Gallery Modal -->
{#if galleryModalOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-4"
		style="background: rgba(0,0,0,0.2); backdrop-filter: blur(2px);"
	>
		<div
			class="h-auto max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-lg border bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-800"
		>
			<div class="mb-4 flex items-center justify-between border-b pb-3 dark:border-gray-700">
				<div class="text-xl font-semibold dark:text-white">{galleryModalTitle}</div>
				<button
					class="rounded bg-gray-100 p-2 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600"
					on:click={closeGallery}
				>
					<Icon icon="mdi:close" class="h-5 w-5" />
				</button>
			</div>

			{#if galleryLoading}
				<div class="flex justify-center p-8">
					<div
						class="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"
					></div>
				</div>
			{:else if galleryItems.length === 0}
				<div class="p-8 text-center text-gray-500">No documents found.</div>
			{:else}
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{#each galleryItems as it (it.file.id)}
						<div class="rounded border p-3 dark:border-gray-700">
							<div class="mb-2 flex items-center justify-between">
								<span class="truncate text-sm font-medium" title={it.name}>{it.name}</span>
								{#if it.file.status === 'Approved'}
									<span
										class="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900 dark:text-green-300"
										>Approved</span
									>
								{:else if it.file.status === 'Declined'}
									<span
										class="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900 dark:text-red-300"
										>Declined</span
									>
								{:else}
									<span
										class="rounded bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
										>Pending</span
									>
								{/if}
							</div>

							{#if it.url}
								{#if isPdfItem(it)}
									<iframe src={it.url} title={it.name} class="h-56 w-full rounded border bg-gray-50"
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

							<div class="mt-2 flex items-center justify-between gap-2">
								<button
									class="rounded p-1 text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-700"
									title={`Download - ${getFileType(it.file.file_name)}`}
									on:click={() => downloadFile(it.file)}
								>
									<Icon icon="mdi:download" class="h-5 w-5" />
									{#if it.file.file_name}
										<span class="ml-1 text-xs text-gray-600 dark:text-gray-400">
											{getFileType(it.file.file_name)}
										</span>
									{/if}
								</button>
								{#if it.file.status === 'Approved'}
									<button
										class="rounded p-1 text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-700"
										title="Re-upload"
										on:click={() =>
											updateFile(getDocTypeNameById(it.file.document_type_id) || it.name)}
									>
										<Icon icon="mdi:update" class="h-5 w-5" />
									</button>
								{:else}
									<button
										class="rounded p-1 text-red-600 hover:bg-gray-100 dark:hover:bg-gray-700"
										title="Delete"
										on:click={() => deleteFile(it.file)}
									>
										<Icon icon="mdi:trash-can" class="h-5 w-5" />
									</button>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
			<div class="mt-4 flex justify-end border-t pt-3 dark:border-gray-700">
				<button
					class="rounded bg-gray-200 px-4 py-2 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
					on:click={closeGallery}
				>
					Close
				</button>
			</div>
		</div>
	</div>
{/if}

{#if remarksModalOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-4"
		style="background: rgba(0,0,0,0.2); backdrop-filter: blur(2px);"
	>
		<div
			class="w-full max-w-md rounded-lg border bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-800"
		>
			<div class="mb-4 flex items-center justify-between border-b pb-3 dark:border-gray-700">
				<div class="text-lg font-semibold dark:text-white">{remarksModalTitle}</div>
				<button
					class="rounded bg-gray-100 p-2 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600"
					on:click={closeRemarks}
				>
					<Icon icon="mdi:close" class="h-5 w-5" />
				</button>
			</div>
			<div class="text-sm whitespace-pre-wrap text-neutral-700 dark:text-gray-300">
				{remarksModalText}
			</div>
			<div class="mt-4 flex justify-end border-t pt-3 dark:border-gray-700">
				<button
					class="rounded bg-gray-200 px-4 py-2 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
					on:click={closeRemarks}
				>
					Close
				</button>
			</div>
		</div>
	</div>
{/if}

{#if confirmOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-4"
		style="background: rgba(0,0,0,0.2); backdrop-filter: blur(2px);"
	>
		<div
			class="w-full max-w-md rounded-lg border bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-800"
		>
			<div class="mb-4 text-lg font-semibold dark:text-white">Confirm Action</div>
			<div class="mb-6 text-sm text-neutral-700 dark:text-gray-300">{confirmMessage}</div>
			<div class="flex justify-end gap-2">
				<button
					class="rounded bg-gray-200 px-4 py-2 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
					on:click={closeConfirm}
					disabled={confirmLoading}
				>
					Close
				</button>
				<button
					class="inline-flex items-center rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
					on:click={proceedConfirm}
					disabled={confirmLoading}
				>
					{#if confirmLoading}
						<span
							class="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
						></span>
					{/if}
					Proceed
				</button>
			</div>
		</div>
	</div>
{/if}