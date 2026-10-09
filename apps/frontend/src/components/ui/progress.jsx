import * as ProgressPrimitive from "@radix-ui/react-progress";

import { cn } from "./utils.js";

function Progress({ className, value = 0, max = 100, ...props }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      value={(value / Math.max(max, 1)) * 100}
      className={cn("bg-secondary relative h-2 w-full overflow-hidden rounded-full", className)}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="h-full w-full flex-1 rounded-full bg-[linear-gradient(90deg,var(--secondary),var(--status-success))] transition-all"
        style={{ transform: `translateX(-${100 - pct}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}

export { Progress };
export { Skeleton } from "./skeleton.jsx";
