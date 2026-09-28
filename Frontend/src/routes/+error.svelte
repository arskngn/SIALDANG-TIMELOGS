<script lang="ts">
	export let error: Error & { message?: string };
	export let status: number;

	const imagePath = '/404.jpg';
	const ariaLabel =
		status === 404 ? 'Page not found' : `Error ${status || ''}`.trim() || 'Error';
</script>

<div
	style="position: fixed; inset: 0; z-index: 99999; background: #000; display: flex; align-items: center; justify-content: center;"
	title={error?.message || ''}
>
	<img
		src={imagePath}
		alt={ariaLabel}
		style="width: 100vw; height: 100vh; object-fit: cover; display: block;"
	/>
</div>

<style>
	/* Keep styles scoped to the error overlay only */
	div {
		margin: 0;
		padding: 0;
	}
</style>
