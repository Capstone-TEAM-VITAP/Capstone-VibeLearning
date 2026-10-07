import { cn } from "./utils.js";

function Progress({ value = 0, max = 100, className, ...props }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div
      className={cn("scn-progress", className)}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      {...props}
    >
      <div className="scn-progress-bar" style={{ width: `${pct}%` }} />
    </div>
  );
}

function Skeleton({ className, ...props }) {
  return <div className={cn("scn-skeleton", className)} {...props} />;
}

export { Progress, Skeleton };
