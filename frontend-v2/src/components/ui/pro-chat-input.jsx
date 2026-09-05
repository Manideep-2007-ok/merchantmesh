import React, { useState, useRef, useEffect } from "react";
import { IconSend } from "@tabler/icons-react";
import { cn } from "@/lib/utils";

export const ProChatInput = ({ onSubmit, placeholder = "Message Buyer Agent..." }) => {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [value]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim()) {
        onSubmit(value);
        setValue("");
      }
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      <div className="relative group bg-black/40 backdrop-blur-md border border-white/10 rounded-2xl shadow-xl focus-within:border-emerald-500/50 focus-within:shadow-[0_0_20px_rgba(16,185,129,0.15)] transition-all duration-300 overflow-hidden flex items-end">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full bg-transparent text-zinc-200 placeholder:text-zinc-500 px-4 py-4 resize-none outline-none text-sm leading-relaxed min-h-[56px] overflow-y-auto"
          rows={1}
        />
        <div className="p-2 shrink-0">
          <button 
            onClick={() => { if(value.trim()){ onSubmit(value); setValue(""); } }}
            disabled={!value.trim()}
            className={cn(
              "p-2.5 rounded-xl flex items-center justify-center transition-all duration-300",
              value.trim() 
                ? "bg-emerald-500 text-black shadow-[0_0_15px_rgba(16,185,129,0.4)]" 
                : "bg-white/5 text-zinc-500 cursor-not-allowed"
            )}
          >
            <IconSend className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
