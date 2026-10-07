import { cn } from "./utils.js";

const VARIANTS = {
  default: "scn-badge-default",
  secondary: "scn-badge-secondary",
  outline: "scn-badge-outline",
  success: "scn-badge-success",
  warning: "scn-badge-warning",
  destructive: "scn-badge-destructive",
};

function Badge({ variant = "default", className, ...props }) {
  return <span className={cn("scn-badge", VARIANTS[variant], className)} {...props} />;
}

export default Badge;
export { Badge };
