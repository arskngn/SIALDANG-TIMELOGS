<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { login, isAuthenticated } from '$lib/stores';
	import { healthAPI, authAPI } from '$lib/api';
	import { onMount } from 'svelte';
	import IconEye from '~icons/heroicons-solid/eye';
	import IconEyeSlash from '~icons/heroicons-solid/eye-slash';

	let username = '';
	let password = '';
	let error: string | null = null;
	let isLoading = false;
	let backendLoading = true;
	let backendMessage: string | null = null;
	let backendError: string | null = null;
	let passwordVisible = false;
	let capsLockOn = false;

	function updateCapsLock(e: KeyboardEvent) {
		capsLockOn = typeof e.getModifierState === 'function' ? e.getModifierState('CapsLock') : false;
	}

	function fillDemo(u: string, p: string) {
		username = u;
		password = p;
		error = null;
	}

	async function submit(e: Event) {
		e.preventDefault();
		error = null;

		// Form validation
		if (!username.trim() || !password.trim()) {
			error = 'Please enter both username and password.';
			return;
		}

		if (username.trim().length < 3) {
			error = 'Username must be at least 3 characters long.';
			return;
		}

		if (password.trim().length < 6) {
			error = 'Password must be at least 6 characters long.';
			return;
		}

		isLoading = true;

		// Authenticate using proper JWT authentication
		try {
			const response = await authAPI.login({
				username: username.trim(),
				password: password.trim()
			});

			// Get user details from token verification
			const userInfo = await authAPI.verifyToken(response.access_token);

			// Login with full user information
			login(userInfo.user.username, userInfo.user.role, response.access_token, userInfo.user.id);

			// Redirect to dashboard
			goto(resolve('/main'));
		} catch (err) {
			console.error('Login error', err);
			const msg = err instanceof Error ? err.message : String(err);
			try {
				const jsonPart = msg.split(' - ').slice(1).join(' - ');
				const parsed = JSON.parse(jsonPart);
				const detail = parsed && parsed.detail ? String(parsed.detail) : '';
				if (
					detail.includes('ACCOUNT BLOCKED') ||
					detail.includes('OUT OF CONTRACT') ||
					detail.includes('CONTRACT NOT STARTED')
				) {
					error = 'Not authorized';
				} else {
					error = detail || 'Invalid username or password';
				}
			} catch {
				error =
					msg.includes('ACCOUNT BLOCKED') ||
					msg.includes('OUT OF CONTRACT') ||
					msg.includes('CONTRACT NOT STARTED')
						? 'Not authorized'
						: 'Invalid username or password';
			}
		} finally {
			isLoading = false;
		}
	}

	onMount(() => {
		const unsub = isAuthenticated.subscribe((v) => {
			if (v) goto(resolve('/main'));
		});

		// Check backend health/message
		(async () => {
			backendLoading = true;
			backendError = null;
			backendMessage = null;
			try {
				const res = await healthAPI.checkHealth();
				backendMessage = res?.message ?? 'No message returned from backend';
			} catch (err) {
				backendError = err instanceof Error ? err.message : String(err);
			} finally {
				backendLoading = false;
			}
		})();

		return () => unsub();
	});
</script>

<div class="flex min-h-screen items-center justify-center px-4">
	<div class="w-full max-w-md p-8">
		<h1 class="mb-6 text-center text-2xl font-semibold">Login</h1>

		{#if error}
			<div class="mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700">
				{error}
			</div>
		{/if}

		<form on:submit|preventDefault={submit} class="mb-4 rounded bg-white px-8 pt-6 pb-8 shadow-md">
			<div class="mb-6 flex justify-center">
				<img
					src="/sialdang-banner.png"
					alt="sialdang.com"
					class="h-14 w-full object-contain"
					loading="eager"
				/>
			</div>
			<div class="mb-4">
				<label for="username-input" class="mb-2 block text-sm font-bold text-gray-700"
					>Username</label
				>
				<input
					id="username-input"
					bind:value={username}
					disabled={isLoading}
					class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none disabled:opacity-50"
					placeholder="Enter your username"
				/>
			</div>
			<div class="mb-6">
				<label for="password-input" class="mb-2 block text-sm font-bold text-gray-700"
					>Password</label
				>
				<div class="relative">
					<input
						id="password-input"
						{...{}}
						type={passwordVisible ? 'text' : 'password'}
						bind:value={password}
						disabled={isLoading}
						class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 pr-10 leading-tight text-gray-700 shadow focus:outline-none disabled:opacity-50"
						placeholder="Enter your password"
						on:keydown={(e) => updateCapsLock(e as KeyboardEvent)}
						on:keyup={(e) => updateCapsLock(e as KeyboardEvent)}
						on:blur={() => (capsLockOn = false)}
					/>
					<button
						type="button"
						class="absolute top-1/2 right-2 -translate-y-1/2 text-gray-600 hover:text-gray-800"
						aria-label={passwordVisible ? 'Hide password' : 'Show password'}
						on:click={() => (passwordVisible = !passwordVisible)}
					>
						{#if passwordVisible}
							<IconEyeSlash class="h-5 w-5" />
						{:else}
							<IconEye class="h-5 w-5" />
						{/if}
					</button>
				</div>
				{#if !passwordVisible && capsLockOn}
					<div class="mt-1 text-xs text-red-600">Caps Lock is on</div>
				{/if}
			</div>
			<div class="flex items-center justify-between">
				<button
					type="submit"
					disabled={isLoading}
					class="focus:shadow-outline w-full rounded bg-blue-500 py-2.5 font-bold text-white transition hover:bg-blue-700 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
				>
					{#if isLoading}
						Logging in...
					{:else}
						Login
					{/if}
				</button>
			</div>

			<div class="mt-6 border-t border-gray-200 pt-4 dark:border-gray-700">
				<div class="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-500">
					<span>Live Demo Quick Fill</span>
					<span class="text-[10px] font-normal text-blue-500 lowercase">Click to fill</span>
				</div>
				<div class="grid grid-cols-3 gap-2">
					<button
						type="button"
						on:click={() => fillDemo('admin', 'DemoAdmin123!')}
						class="flex flex-col items-center rounded border border-gray-200 bg-gray-50 p-2 text-xs font-medium text-gray-700 transition hover:border-blue-500 hover:bg-blue-50 hover:text-blue-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
					>
						<span class="font-bold text-blue-600">👑 Admin</span>
						<span class="text-[10px] text-gray-400">admin</span>
					</button>
					<button
						type="button"
						on:click={() => fillDemo('manager', 'DemoManager123!')}
						class="flex flex-col items-center rounded border border-gray-200 bg-gray-50 p-2 text-xs font-medium text-gray-700 transition hover:border-blue-500 hover:bg-blue-50 hover:text-blue-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
					>
						<span class="font-bold text-amber-600">👔 Manager</span>
						<span class="text-[10px] text-gray-400">manager</span>
					</button>
					<button
						type="button"
						on:click={() => fillDemo('employee', 'DemoUser123!')}
						class="flex flex-col items-center rounded border border-gray-200 bg-gray-50 p-2 text-xs font-medium text-gray-700 transition hover:border-blue-500 hover:bg-blue-50 hover:text-blue-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
					>
						<span class="font-bold text-green-600">👤 Staff</span>
						<span class="text-[10px] text-gray-400">employee</span>
					</button>
				</div>
			</div>
		</form>

		<div class="mt-4">
			{#if backendLoading}
				<p class="text-sm text-gray-600">Checking backend connection...</p>
			{:else if backendError}
				<div class="text-sm text-red-600">Failed to connect to backend: {backendError}</div>
			{:else}
				<div class="text-sm text-green-700">Connected to backend: {backendMessage}</div>
			{/if}
			<p class="mt-2 text-xs text-gray-500">
				Authentication uses the connected FastAPI backend; enter your backend credentials.
			</p>
		</div>
	</div>
</div>

<style>
	input[type='password']::-ms-reveal {
		display: none;
	}
	input[type='password']::-ms-clear {
		display: none;
	}
</style>
