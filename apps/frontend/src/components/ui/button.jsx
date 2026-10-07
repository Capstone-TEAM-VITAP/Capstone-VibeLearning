import { cn } from "./utils.js";

const VARIANTS = {
  default: "scn-btn-default",
  secondary: "scn-btn-secondary",
  outline: "scn-btn-outline",
  ghost: "scn-btn-ghost",
  destructive: "scn-btn-destructive",
};

const SIZES = {
  sm: "scn-btn-sm",
  default: "scn-btn-md",
  lg: "scn-btn-lg",
  icon: "scn-btn-icon",
};

function Button({ variant = "default", size = "default", className, ...props }) {
  return (
    <button
      className={cn("scn-btn", VARIANTS[variant], SIZES[size], className)}
      {...props}
    />
  );
}

export default Button;
export { Button };
