import { cn } from "./utils.js";

function Card({ className, ...props }) {
  return <div className={cn("scn-card", className)} {...props} />;
}

function CardHeader({ className, ...props }) {
  return <div className={cn("scn-card-header", className)} {...props} />;
}

function CardTitle({ className, ...props }) {
  return <h3 className={cn("scn-card-title", className)} {...props} />;
}

function CardDescription({ className, ...props }) {
  return <p className={cn("scn-card-desc", className)} {...props} />;
}

function CardContent({ className, ...props }) {
  return <div className={cn("scn-card-content", className)} {...props} />;
}

function CardFooter({ className, ...props }) {
  return <div className={cn("scn-card-footer", className)} {...props} />;
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter };
