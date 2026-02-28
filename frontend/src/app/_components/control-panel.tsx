"use client";

import {
	LoaderCircle,
	Music2,
	Pause,
	Play,
	RefreshCw,
	SkipForward,
	Square,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/trpc/react";

function isDiscordId(value: string): boolean {
	return /^\d+$/.test(value.trim());
}

function getErrorMessage(error: unknown): string {
	if (error instanceof Error) {
		return error.message;
	}
	return "Unexpected error.";
}

const DEFAULT_GUILD_ID = process.env.NEXT_PUBLIC_DEFAULT_GUILD_ID ?? "";

export function ControlPanel() {
	const [guildIdInput, setGuildIdInput] = useState(DEFAULT_GUILD_ID);
	const [query, setQuery] = useState("");
	const [requestedBy, setRequestedBy] = useState("Web Control");
	const [voiceChannelId, setVoiceChannelId] = useState("");
	const [textChannelId, setTextChannelId] = useState("");
	const [notice, setNotice] = useState<string | null>(null);

	const guildId = guildIdInput.trim();
	const hasValidGuild = isDiscordId(guildId);

	const utils = api.useUtils();

	const health = api.control.health.useQuery(undefined, {
		refetchInterval: 15_000,
	});

	const queue = api.control.queue.useQuery(
		{ guildId },
		{
			enabled: hasValidGuild,
			refetchInterval: 5_000,
		},
	);

	const play = api.control.play.useMutation();
	const pause = api.control.pause.useMutation();
	const resume = api.control.resume.useMutation();
	const skip = api.control.skip.useMutation();
	const stop = api.control.stop.useMutation();

	const isMutating =
		play.isPending ||
		pause.isPending ||
		resume.isPending ||
		skip.isPending ||
		stop.isPending;

	async function refreshQueue() {
		if (!hasValidGuild) return;
		await utils.control.queue.invalidate({ guildId });
	}

	async function handleAction(
		action: "pause" | "resume" | "skip" | "stop",
	): Promise<void> {
		if (!hasValidGuild) {
			setNotice("Enter a valid guild id first.");
			return;
		}

		try {
			const result =
				action === "pause"
					? await pause.mutateAsync({ guildId })
					: action === "resume"
						? await resume.mutateAsync({ guildId })
						: action === "skip"
							? await skip.mutateAsync({ guildId })
							: await stop.mutateAsync({ guildId });
			setNotice(result.message);
			await refreshQueue();
		} catch (error) {
			setNotice(getErrorMessage(error));
		}
	}

	async function onPlaySubmit(event: React.FormEvent<HTMLFormElement>) {
		event.preventDefault();

		if (!hasValidGuild) {
			setNotice("Enter a valid guild id first.");
			return;
		}

		if (!query.trim()) {
			setNotice("Track query is required.");
			return;
		}

		try {
			const result = await play.mutateAsync({
				guildId,
				query: query.trim(),
				requestedBy: requestedBy.trim() || "Web Control",
				voiceChannelId: voiceChannelId.trim() || undefined,
				textChannelId: textChannelId.trim() || undefined,
			});
			setNotice(`Queued: ${result.track.title}`);
			setQuery("");
			await refreshQueue();
		} catch (error) {
			setNotice(getErrorMessage(error));
		}
	}

	return (
		<div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
			<section className="grid gap-4 md:grid-cols-2">
				<Card className="border-border/80 bg-card/90 backdrop-blur">
					<CardHeader>
						<CardTitle>Bot Health</CardTitle>
						<CardDescription>
							Live status from FastAPI control endpoint.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3">
						<div className="flex items-center gap-2">
							<Badge
								variant={health.data?.discord_ready ? "default" : "secondary"}
							>
								{health.data?.discord_ready
									? "Discord Ready"
									: "Discord Not Ready"}
							</Badge>
							<Badge variant="outline">
								{health.data
									? `${health.data.guild_count} guild(s)`
									: "No data"}
							</Badge>
						</div>
						<p className="text-muted-foreground text-sm">
							{health.isLoading ? "Checking backend..." : null}
							{health.error ? `Health error: ${health.error.message}` : null}
							{health.data?.bot_user_id
								? `Bot user id: ${health.data.bot_user_id}`
								: null}
						</p>
					</CardContent>
				</Card>

				<Card className="border-border/80 bg-card/90 backdrop-blur">
					<CardHeader>
						<CardTitle>Target Guild</CardTitle>
						<CardDescription>
							All controls apply to this Discord guild.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3">
						<div className="space-y-2">
							<Label htmlFor="guild-id">Guild ID</Label>
							<Input
								id="guild-id"
								onChange={(event) => setGuildIdInput(event.target.value)}
								placeholder="123456789012345678"
								value={guildIdInput}
							/>
						</div>
						<div className="flex items-center gap-2">
							<Badge variant={hasValidGuild ? "default" : "destructive"}>
								{hasValidGuild ? "Valid guild id" : "Guild id required"}
							</Badge>
							<Button
								onClick={() => void refreshQueue()}
								size="sm"
								type="button"
								variant="outline"
							>
								<RefreshCw />
								Refresh queue
							</Button>
						</div>
					</CardContent>
				</Card>
			</section>

			<section className="grid gap-4 lg:grid-cols-3">
				<Card className="border-border/80 bg-card/90 backdrop-blur lg:col-span-2">
					<CardHeader>
						<CardTitle>Play Track</CardTitle>
						<CardDescription>
							Queue a YouTube URL or search term.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<form className="space-y-4" onSubmit={onPlaySubmit}>
							<div className="space-y-2">
								<Label htmlFor="query">Track query</Label>
								<Input
									id="query"
									onChange={(event) => setQuery(event.target.value)}
									placeholder="lofi hip hop"
									value={query}
								/>
							</div>
							<div className="grid gap-4 sm:grid-cols-2">
								<div className="space-y-2">
									<Label htmlFor="requested-by">Requested by</Label>
									<Input
										id="requested-by"
										onChange={(event) => setRequestedBy(event.target.value)}
										placeholder="Web Control"
										value={requestedBy}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="voice-channel">
										Voice channel id (optional)
									</Label>
									<Input
										id="voice-channel"
										onChange={(event) => setVoiceChannelId(event.target.value)}
										placeholder="123456789012345678"
										value={voiceChannelId}
									/>
								</div>
							</div>
							<div className="space-y-2">
								<Label htmlFor="text-channel">Text channel id (optional)</Label>
								<Input
									id="text-channel"
									onChange={(event) => setTextChannelId(event.target.value)}
									placeholder="123456789012345678"
									value={textChannelId}
								/>
							</div>
							<Button
								className="w-full sm:w-auto"
								disabled={isMutating}
								type="submit"
							>
								{play.isPending ? (
									<LoaderCircle className="animate-spin" />
								) : (
									<Play />
								)}
								Queue track
							</Button>
						</form>
					</CardContent>
				</Card>

				<Card className="border-border/80 bg-card/90 backdrop-blur">
					<CardHeader>
						<CardTitle>Transport</CardTitle>
						<CardDescription>
							Playback controls for the active guild.
						</CardDescription>
					</CardHeader>
					<CardContent className="grid grid-cols-2 gap-3">
						<Button
							disabled={isMutating}
							onClick={() => void handleAction("pause")}
							variant="secondary"
						>
							<Pause />
							Pause
						</Button>
						<Button
							disabled={isMutating}
							onClick={() => void handleAction("resume")}
							variant="secondary"
						>
							<Play />
							Resume
						</Button>
						<Button
							disabled={isMutating}
							onClick={() => void handleAction("skip")}
							variant="outline"
						>
							<SkipForward />
							Skip
						</Button>
						<Button
							disabled={isMutating}
							onClick={() => void handleAction("stop")}
							variant="destructive"
						>
							<Square />
							Stop
						</Button>
					</CardContent>
				</Card>
			</section>

			<Card className="border-border/80 bg-card/90 backdrop-blur">
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<Music2 className="size-5" />
						Queue
					</CardTitle>
					<CardDescription>
						Current playback and next tracks for guild{" "}
						{hasValidGuild ? guildId : "N/A"}.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					{notice ? (
						<p className="rounded-md border border-border bg-muted px-3 py-2 text-sm">
							{notice}
						</p>
					) : null}

					{queue.isLoading ? (
						<p className="text-muted-foreground text-sm">Loading queue...</p>
					) : null}

					{queue.error ? (
						<p className="text-destructive text-sm">{queue.error.message}</p>
					) : null}

					{queue.data?.now_playing ? (
						<div className="rounded-lg border border-border p-3">
							<p className="font-medium text-sm">Now playing</p>
							<p className="mt-1">{queue.data.now_playing.title}</p>
							<p className="text-muted-foreground text-sm">
								Requested by {queue.data.now_playing.requested_by}
							</p>
						</div>
					) : (
						<p className="text-muted-foreground text-sm">
							Nothing is playing right now.
						</p>
					)}

					<div className="space-y-2">
						<div className="flex items-center justify-between">
							<p className="font-medium text-sm">Up next</p>
							<Badge variant="outline">
								Volume {queue.data?.volume_percent ?? 100}%
							</Badge>
						</div>

						{queue.data?.queue.length ? (
							<ul className="space-y-2">
								{queue.data.queue.slice(0, 10).map((track, index) => (
									<li
										className="rounded-md border border-border/80 bg-background/60 px-3 py-2 text-sm"
										key={`${track.webpage_url}-${index}`}
									>
										<p className="font-medium">{track.title}</p>
										<p className="text-muted-foreground text-xs">
											Requested by {track.requested_by}
										</p>
									</li>
								))}
							</ul>
						) : (
							<p className="text-muted-foreground text-sm">Queue is empty.</p>
						)}
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
