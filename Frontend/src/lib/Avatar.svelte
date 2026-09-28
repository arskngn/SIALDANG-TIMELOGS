<script lang="ts">
	export let firstName = '';
	export let lastName = '';
	export let username = '';
	export let src: string | null | undefined = null;
	export let size: 'sm' | 'md' | 'lg' | 'xl' | '2xl' = 'md';

	let showImage = false;
	$: cacheBustedSrc = src ? `${src}${src.includes('?') ? '&' : '?'}t=${Date.now()}` : null;

	$: initials = (() => {
		const first = firstName?.trim();
		const last = lastName?.trim();
		if (first && last) {
			return `${first[0]}${last[0]}`.toUpperCase();
		} else if (first) {
			return first[0].toUpperCase();
		} else if (last) {
			return last[0].toUpperCase();
		} else if (username) {
			return username.substring(0, 2).toUpperCase();
		}
		return '?';
	})();

	$: sizeClasses = {
		sm: 'w-6 h-6 text-xs',
		md: 'w-8 h-8 text-sm',
		lg: 'w-10 h-10 text-base',
		xl: 'w-16 h-16 text-xl',
		'2xl': 'w-32 h-32 text-3xl'
	}[size];

	// Consistent color based on initials
	$: bgColor = (() => {
		const colors = [
			'bg-red-500',
			'bg-blue-500',
			'bg-green-500',
			'bg-purple-500',
			'bg-pink-500',
			'bg-indigo-500',
			'bg-yellow-500',
			'bg-teal-500'
		];
		const charCode = initials.charCodeAt(0);
		return colors[charCode % colors.length];
	})();

	$: displayName = `${firstName} ${lastName}`.trim() || username;
</script>

<div
	class="{sizeClasses} flex shrink-0 items-center justify-center rounded-full"
	title={displayName}
>
	{#if cacheBustedSrc}
		<img
			src={cacheBustedSrc}
			alt={displayName}
			class="h-full w-full rounded-full object-cover"
			on:load={() => (showImage = true)}
			on:error={() => (showImage = false)}
			style="display: {showImage ? 'block' : 'none'}"
		/>
	{/if}
	{#if !showImage}
		<div
			class="{bgColor} flex h-full w-full items-center justify-center rounded-full leading-none font-semibold text-white"
		>
			{initials}
		</div>
	{/if}
</div>
