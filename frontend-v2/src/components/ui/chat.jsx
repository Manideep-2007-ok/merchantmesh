import React from 'react';
import { cn } from "@/lib/utils";

// Mimicking shadcn-chat / chat-ui-kit architecture

export const ChatContainer = React.forwardRef(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col w-full h-full overflow-hidden bg-[#0b141a]", className)} {...props}>
    {children}
  </div>
));
ChatContainer.displayName = "ChatContainer";

export const ChatHeader = React.forwardRef(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("h-16 bg-[#202c33] flex items-center justify-between px-4 shrink-0 shadow-md z-10", className)} {...props}>
    {children}
  </div>
));
ChatHeader.displayName = "ChatHeader";

export const ChatMessageList = React.forwardRef(({ className, children, ...props }, ref) => (
  <div 
    ref={ref} 
    className={cn("flex-1 overflow-y-auto p-4 flex flex-col gap-2 relative [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]", className)} 
    style={{ 
      backgroundImage: 'radial-gradient(#202c33 1px, transparent 1px)', 
      backgroundSize: '20px 20px', 
      backgroundPosition: '-10px -10px' 
    }} 
    {...props}
  >
    {children}
  </div>
));
ChatMessageList.displayName = "ChatMessageList";

export const ChatBubble = React.forwardRef(({ className, variant = "received", children, ...props }, ref) => {
  const isSent = variant === "sent";
  return (
    <div ref={ref} className={cn("flex w-full", isSent ? "justify-end" : "justify-start", className)} {...props}>
      <div className={cn(
        "max-w-[85%] lg:max-w-[70%] p-2 rounded-lg relative shadow-sm text-[15px] leading-snug text-[#e9edef]",
        isSent ? "bg-[#005c4b] rounded-tr-none" : "bg-[#202c33] rounded-tl-none"
      )}>
        {/* WhatsApp tail corner */}
        <span className={cn(
          "absolute top-0 w-4 h-4",
          isSent ? "-right-2 text-[#005c4b]" : "-left-2 text-[#202c33]"
        )}>
          <svg viewBox="0 0 8 13" width="8" height="13" className="fill-current">
            {isSent ? (
              <path opacity="1" d="M5.188 1H0v11.193l6.467-8.625C7.526 2.156 6.958 1 5.188 1z" />
            ) : (
              <path opacity="1" d="M1.533 3.568L8 12.193V1H2.812C1.042 1 .474 2.156 1.533 3.568z" />
            )}
          </svg>
        </span>
        {children}
      </div>
    </div>
  );
});
ChatBubble.displayName = "ChatBubble";

export const ChatInputContainer = React.forwardRef(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("h-[62px] bg-[#202c33] flex items-center gap-2 px-4 shrink-0", className)} {...props}>
    {children}
  </div>
));
ChatInputContainer.displayName = "ChatInputContainer";
