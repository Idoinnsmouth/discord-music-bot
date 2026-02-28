import { TRPCError } from "@trpc/server";
import { z } from "zod";

import { env } from "@/env";
import { createTRPCRouter, publicProcedure } from "@/server/api/trpc";

const idSchema = z
	.string()
	.regex(/^\d+$/, "Value must be a numeric Discord ID.");

const queueInput = z.object({
	guildId: idSchema,
});

const playInput = z.object({
	guildId: idSchema,
	query: z.string().min(1),
	requestedBy: z.string().min(1).max(80).default("Control Panel"),
	voiceChannelId: idSchema.optional(),
	textChannelId: idSchema.optional(),
});

const actionInput = z.object({
	guildId: idSchema,
});

function toNumber(id: string): number {
	return Number.parseInt(id, 10);
}

function getApiUrl(path: string): string {
	const base = env.CONTROL_API_BASE_URL.replace(/\/$/, "");
	const route = path.startsWith("/") ? path : `/${path}`;
	return `${base}${route}`;
}

async function parseJsonOrThrow(response: Response): Promise<unknown> {
	const contentType = response.headers.get("content-type") ?? "";
	const bodyText = await response.text();

	let payload: unknown = null;
	if (bodyText) {
		if (contentType.includes("application/json")) {
			try {
				payload = JSON.parse(bodyText);
			} catch {
				payload = bodyText;
			}
		} else {
			payload = bodyText;
		}
	}

	if (!response.ok) {
		let detail = response.statusText;
		if (payload && typeof payload === "object" && "detail" in payload) {
			const maybeDetail = (payload as { detail: unknown }).detail;
			detail = String(maybeDetail);
		}

		throw new TRPCError({
			code: "BAD_REQUEST",
			message: `Control API ${response.status}: ${detail}`,
		});
	}

	return payload;
}

async function controlRequest(
	path: string,
	init?: RequestInit,
): Promise<unknown> {
	const headers = new Headers(init?.headers);
	if (!headers.has("Content-Type")) {
		headers.set("Content-Type", "application/json");
	}
	if (env.CONTROL_API_TOKEN) {
		headers.set("X-API-Key", env.CONTROL_API_TOKEN);
	}

	try {
		const response = await fetch(getApiUrl(path), {
			...init,
			cache: "no-store",
			headers,
		});
		return await parseJsonOrThrow(response);
	} catch (error) {
		if (error instanceof TRPCError) {
			throw error;
		}
		throw new TRPCError({
			code: "INTERNAL_SERVER_ERROR",
			message: "Failed to reach control API backend.",
			cause: error,
		});
	}
}

export const controlRouter = createTRPCRouter({
	health: publicProcedure.query(async () => {
		return (await controlRequest("/health", {
			method: "GET",
		})) as {
			status: string;
			discord_ready: boolean;
			guild_count: number;
			bot_user_id: number | null;
		};
	}),

	queue: publicProcedure.input(queueInput).query(async ({ input }) => {
		return (await controlRequest(`/guilds/${input.guildId}/queue`, {
			method: "GET",
		})) as {
			guild_id: number;
			volume_percent: number;
			now_playing: {
				title: string;
				webpage_url: string;
				requested_by: string;
			} | null;
			queue: Array<{
				title: string;
				webpage_url: string;
				requested_by: string;
			}>;
		};
	}),

	play: publicProcedure.input(playInput).mutation(async ({ input }) => {
		return (await controlRequest(`/guilds/${input.guildId}/play`, {
			method: "POST",
			body: JSON.stringify({
				query: input.query,
				requested_by: input.requestedBy,
				voice_channel_id: input.voiceChannelId
					? toNumber(input.voiceChannelId)
					: undefined,
				text_channel_id: input.textChannelId
					? toNumber(input.textChannelId)
					: undefined,
			}),
		})) as {
			message: string;
			guild_id: number;
			queue_length: number;
			track: {
				title: string;
				webpage_url: string;
				requested_by: string;
			};
		};
	}),

	pause: publicProcedure.input(actionInput).mutation(async ({ input }) => {
		return (await controlRequest(`/guilds/${input.guildId}/pause`, {
			method: "POST",
		})) as { message: string };
	}),

	resume: publicProcedure.input(actionInput).mutation(async ({ input }) => {
		return (await controlRequest(`/guilds/${input.guildId}/resume`, {
			method: "POST",
		})) as { message: string };
	}),

	skip: publicProcedure.input(actionInput).mutation(async ({ input }) => {
		return (await controlRequest(`/guilds/${input.guildId}/skip`, {
			method: "POST",
		})) as { message: string };
	}),

	stop: publicProcedure.input(actionInput).mutation(async ({ input }) => {
		return (await controlRequest(`/guilds/${input.guildId}/stop`, {
			method: "POST",
		})) as { message: string };
	}),
});
