import type * as React from "react";

import { cn } from "@/lib/utils";

function Label({ className, ...props }: React.ComponentProps<"label">) {
	return (
		/* biome-ignore lint/a11y/noLabelWithoutControl: wrapper component receives htmlFor from callers */
		<label
			className={cn(
				"inline-flex items-center gap-2 font-medium text-sm leading-none",
				className,
			)}
			data-slot="label"
			{...props}
		/>
	);
}

export { Label };
