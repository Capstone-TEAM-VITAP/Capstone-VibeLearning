import { cn } from "./utils.js";

function Input({ className, ...props }) {
  return <input className={cn("scn-input", className)} {...props} />;
}

function Select({ className, children, ...props }) {
  return (
    <span className="scn-select-wrap">
      <select className={cn("scn-select", className)} {...props}>
        {children}
      </select>
      <span className="material-symbols-outlined scn-select-chevron" aria-hidden="true">
        expand_more
      </span>
    </span>
  );
}

export { Input, Select };
