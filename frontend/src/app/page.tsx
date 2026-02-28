import { ControlPanel } from "@/app/_components/control-panel";

export default function Home() {
	return (
		<main className="min-h-screen bg-background text-foreground">
			<div className="relative overflow-hidden">
				<div className="pointer-events-none absolute -top-48 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-primary/20 blur-[120px]" />
				<div className="mx-auto w-full max-w-6xl px-4 py-10 md:py-14">
					<header className="mb-8 space-y-2">
						<p className="font-medium text-muted-foreground text-sm uppercase tracking-[0.24em]">
							Discord Music Bot
						</p>
						<h1 className="font-bold text-3xl tracking-tight md:text-4xl">
							Control Panel
						</h1>
						<p className="max-w-2xl text-muted-foreground text-sm">
							Manage playback and queue state from the web app via the FastAPI
							control backend.
						</p>
					</header>
					<ControlPanel />
				</div>
			</div>
		</main>
	);
}
