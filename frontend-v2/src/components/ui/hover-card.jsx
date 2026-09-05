import React from "react"
import { cn } from "@/lib/utils"

function HoverCard({ children, delay, closeDelay, ...props }) {
  return (
    <div className="relative group inline-block" {...props}>
      {children}
    </div>
  )
}

function HoverCardTrigger({ children, asChild, ...props }) {
  // We just render children. If asChild is true, we assume it's a single element.
  return <div className="cursor-pointer" {...props}>{children}</div>
}

function HoverCardContent({
  className,
  children,
  side = "bottom",
  align,
  sideOffset,
  ...props
}) {
  // Determine positioning based on side
  let positionClass = "top-full left-1/2 -translate-x-1/2 mt-2";
  if (side === "top") positionClass = "bottom-full left-1/2 -translate-x-1/2 mb-2";
  if (side === "right") positionClass = "left-full top-1/2 -translate-y-1/2 ml-2";
  if (side === "left") positionClass = "right-full top-1/2 -translate-y-1/2 mr-2";

  return (
    <div
      className={cn(
        "absolute z-50 w-64 rounded-lg bg-zinc-900 p-4 text-sm text-zinc-200 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.8)] border border-zinc-700 outline-none",
        "opacity-0 invisible group-hover:opacity-100 group-hover:visible",
        positionClass,
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export { HoverCard, HoverCardTrigger, HoverCardContent }
