<script lang="ts">
	import Icon from '@iconify/svelte';
</script>

<svelte:head>
	<title>About - Timelogs</title>
</svelte:head>

<div class="min-h-screen bg-gray-50 dark:bg-gray-900">
	<!-- Header -->
	<div class="w-full bg-slate-800 text-white">
		<div class="mx-auto max-w-6xl px-8 py-16">
			<div class="flex items-center gap-4">
				<img src="/favicon.png" alt="Timelogs Logo" class="h-12 w-12" />
				<div>
					<h1 class="text-4xl font-bold tracking-tight">About Timelogs</h1>
					<p class="mt-2 max-w-2xl text-sm text-slate-300">
						An integrated workforce management platform designed to streamline time tracking,
						document compliance, and project coordination for enhanced operational productivity.
					</p>
				</div>
			</div>
		</div>
	</div>

	<!-- Page Content -->
	<div class="mx-auto max-w-6xl space-y-20 px-8 py-16">
		<!-- Overview -->
		<div class="space-y-4 border-b-2 border-gray-200 pb-16 dark:border-gray-700">
			<h2 class="text-2xl font-bold text-gray-900 dark:text-white">System Overview</h2>
			<p class="leading-relaxed text-gray-700 dark:text-gray-300">
				Timelogs v1.0 was developed by the 2025 batch of interns from
				<strong>City College of Calapan</strong> at
				<strong>Sialdang Information Technology Consultancy</strong>. It is designed to efficiently
				monitor, record, and manage intern attendance and working hours while providing
				comprehensive organizational management capabilities. The system streamlines workflow
				processes, facilitates team coordination, and enables better resource planning through
				integrated tools for leave management, project assignments, and real-time communications.
			</p>
		</div>

		<!-- Features -->
		<div class="space-y-10 border-b-2 border-gray-200 pb-16 dark:border-gray-700">
			<h2 class="text-2xl font-bold text-gray-900 dark:text-white">Key Features</h2>

			<div class="grid gap-10 md:grid-cols-2 lg:grid-cols-3">
				<!-- Feature -->
				<div class="flex gap-4">
					<Icon icon="mdi:clock-check-outline" class="h-8 w-8 text-slate-600 dark:text-slate-300" />
					<div>
						<h3 class="font-semibold text-gray-900 dark:text-white">Time Tracking</h3>
						<p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
							Accurate logging of work hours with structured scheduling support.
						</p>
					</div>
				</div>

				<div class="flex gap-4">
					<Icon
						icon="mdi:folder-multiple-outline"
						class="h-8 w-8 text-slate-600 dark:text-slate-300"
					/>
					<div>
						<h3 class="font-semibold text-gray-900 dark:text-white">Project Onboarding</h3>
						<p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
							Organize interns by project, define roles, and track onboarding progress.
						</p>
					</div>
				</div>

				<div class="flex gap-4">
					<Icon
						icon="mdi:file-document-multiple-outline"
						class="h-8 w-8 text-slate-600 dark:text-slate-300"
					/>
					<div>
						<h3 class="font-semibold text-gray-900 dark:text-white">201 Files Management</h3>
						<p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
							Centralized upload, review, and approval of required documents.
						</p>
					</div>
				</div>

				<div class="flex gap-4">
					<Icon icon="mdi:chart-box-outline" class="h-8 w-8 text-slate-600 dark:text-slate-300" />
					<div>
						<h3 class="font-semibold text-gray-900 dark:text-white">Reports & Analytics</h3>
						<p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
							Weekly summaries and productivity insights for better decisions.
						</p>
					</div>
				</div>
				<div class="flex gap-4">
					<Icon
						icon="mdi:calendar-remove-outline"
						class="h-8 w-8 text-slate-600 dark:text-slate-300"
					/>
					<div>
						<h3 class="font-semibold text-gray-900 dark:text-white">Leave Management</h3>
						<p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
							Track users' available and used sick and vacation leave.
						</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Team -->
		<div class="space-y-10">
			<h2 class="text-2xl font-bold text-gray-900 dark:text-white">Development Team</h2>

			<p class="max-w-3xl text-sm text-gray-700 dark:text-gray-300">
				The system was designed and implemented as part of an internship program aimed at improving
				operational efficiency through real-world software solutions.
			</p>

			<div class="grid gap-12 md:grid-cols-2">
				<!-- Leader -->
				<div class="space-y-4">
					<h3 class="text-xs font-bold tracking-wider text-slate-500 uppercase dark:text-slate-400">
						Team Leader
					</h3>
					<div class="flex items-center gap-3">
						<Icon icon="mdi:account-tie" class="h-5 w-5 text-slate-600 dark:text-slate-300" />
						<div>
							<p class="font-medium text-gray-900 dark:text-white">Julius Benedick Macaguiwa</p>
							<p class="text-xs text-blue-700 dark:text-blue-400">Team Leader</p>
						</div>
					</div>
				</div>

				<!-- Developers -->
				<div class="space-y-4">
					<h3 class="text-xs font-bold tracking-wider text-slate-500 dark:text-slate-400">
						v1.0 DEVELOPERS
					</h3>
					<ul class="space-y-1 text-sm text-gray-700 dark:text-gray-300">
						<li>Ezekiel E. Arandia</li>
						<li class="cursor-default transition-colors duration-300 hover:text-[#FF69B4]">
							Zyrell Acedera Dipasupil
						</li>
						<li>Edrian Benedict F. Faderon</li>
						<li
							class="group relative w-fit cursor-default transition-colors duration-300 hover:text-[#FFD700]"
						>
							Aries King Noche Nieto
							<!-- Floating Tooltip -->
							<div
								class="pointer-events-none absolute top-1/2 left-full z-50 ml-3 -translate-y-1/2 whitespace-nowrap opacity-0 transition-opacity duration-300 group-hover:opacity-100"
							>
								<div
									class="relative rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-xl dark:bg-white dark:text-gray-900"
								>
									<!-- Arrow -->
									<div
										class="absolute top-1/2 right-full -mt-1 -mr-px border-4 border-transparent border-r-gray-900 dark:border-r-white"
									></div>
									Hello from Batch 1 Main developer:)
								</div>
							</div>
						</li>
						<li>Mark Dave L. Noche</li>
						<li>John Paul A. Valdez</li>
					</ul>
				</div>
			</div>
		</div>

		<!-- Sialdang Website Link -->
		<div class="border-t border-gray-200 pt-8 text-center dark:border-gray-700">
			<p class="text-gray-700 dark:text-gray-300">
				Also visit Sialdang website at
				<a
					href="https://sialdang.com"
					target="_blank"
					rel="noopener noreferrer"
					class="font-medium text-blue-600 underline hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
				>
					sialdang.com
				</a>
			</p>
		</div>
	</div>

	<!-- Footer -->
	<div
		class="border-t border-gray-200 bg-gray-100 px-8 py-6 text-center text-xs tracking-wide text-gray-500 uppercase dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
	>
		&copy; {new Date().getFullYear()} Timelogs System. All rights reserved. Version 1.0.0
	</div>
</div>
