import "@/styles/globals.css";

import type { Metadata } from "next";
import { Geist } from "next/font/google";

import { TRPCReactProvider } from "@/trpc/react";

export const metadata: Metadata = {
	title: "Discord Bot Control Panel",
	description: "Control playback of the Discord music bot from a web UI.",
	icons: [{ rel: "icon", url: "/favicon.ico" }],
};

const geist = Geist({
	subsets: ["latin"],
	variable: "--font-geist-sans",
});

export default function RootLayout({
	children,
}: Readonly<{ children: React.ReactNode }>) {
	return (
		<html className={`${geist.variable} dark`} lang="en">
			<body className="bg-background font-sans text-foreground antialiased">
				<TRPCReactProvider>{children}</TRPCReactProvider>
			</body>
		</html>
	);
}
