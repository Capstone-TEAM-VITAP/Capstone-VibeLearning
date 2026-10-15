import { cn } from "./utils.js";

const inputBase =
  "border-input file:text-foreground placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground dark:bg-input/30 flex h-9 w-full min-w-0 rounded-md border bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive";

function Input({ className, type, ...props }) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(inputBase, className)}
      {...props}
    />
  );
}

function Select({ className, children, ...props }) {
  return (
    <span className="relative inline-flex w-full" data-slot="select-native-wrap">
      <select
        data-slot="select-native"
        className={cn(inputBase, "cursor-pointer appearance-none pr-8", className)}
        {...props}
      >
        {children}
      </select>
      <span
        className="material-symbols-outlined pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-lg text-muted-foreground"
        aria-hidden="true"
      >
        expand_more
      </span>
    </span>
  );
}

export { Input, Select };
