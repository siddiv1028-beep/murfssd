'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import { useAgent, useSessionContext, useSessionMessages, useDataChannel } from '@livekit/components-react';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { Shimmer } from '@/components/ai-elements/shimmer';
import { cn } from '@/lib/shadcn/utils';
import { TileLayout } from './tile-view';

const MotionMessage = motion.create(Shimmer);

const SHIMMER_MOTION_PROPS: MotionProps = {
  variants: {
    visible: { opacity: 1, transition: { ease: 'easeIn', duration: 0.5, delay: 0.8 } },
    hidden: { opacity: 0, transition: { ease: 'easeIn', duration: 0.5, delay: 0 } },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

const QUICK_PROMPTS = [
  "Do you have 5kg Rice?",
  "What is the price of Mustard Oil?",
  "Please delete my data."
];

export interface AgentSessionView_01Props {
  preConnectMessage?: string;
  supportsChatInput?: boolean;
  supportsVideoInput?: boolean;
  supportsScreenShare?: boolean;
  isPreConnectBufferEnabled?: boolean;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;
  className?: string;
}

export function AgentSessionView_01({
  preConnectMessage = 'Agent is listening, say hello or ask a question',
  supportsChatInput = true,
  supportsVideoInput = true,
  supportsScreenShare = true,
  isPreConnectBufferEnabled = true,
  audioVisualizerType = 'aura',
  audioVisualizerColor = '#10b981',
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerWaveLineWidth,
  ref,
  className,
  ...props
}: React.ComponentProps<'section'> & AgentSessionView_01Props) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const [chatOpen, setChatOpen] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { state: agentState } = useAgent();

  // --- NEW: Toast State ---
  const [toast, setToast] = useState<{message: string, type: string} | null>(null);

  const controls: AgentControlBarControls = {
    leave: false,
    microphone: true,
    chat: supportsChatInput,
    camera: supportsVideoInput,
    screenShare: supportsScreenShare,
  };

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // --- NEW: Listening for Python Backend Signals ---
  useDataChannel('ui-events', (msg) => {
    try {
      const data = JSON.parse(new TextDecoder().decode(msg.payload));
      if (data.action === 'toast') {
        setToast({ message: data.message, type: data.type });
        // Auto-hide the toast after 4 seconds
        setTimeout(() => setToast(null), 4000);
      }
    } catch (error) {
      console.error("Failed to parse ui-event payload", error);
    }
  });

  return (
    <section
      ref={ref}
      className={cn('bg-zinc-950 relative z-10 min-h-[100dvh] w-full overflow-hidden flex flex-col font-outfit', className)}
      {...props}
    >
      <style dangerouslySetInnerHTML={{ __html: `
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
        .font-outfit { font-family: 'Outfit', sans-serif; }
        .lk-participant-tile, .lk-video-container { background-color: transparent !important; border: none !important; box-shadow: none !important; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(16, 185, 129, 0.5); }
      `}} />

      {/* --- NEW: Cinematic Glass Toast Notification --- */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -40, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
            className={`fixed top-8 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-full backdrop-blur-xl border flex items-center gap-3 font-semibold text-sm tracking-wide shadow-2xl ${
              toast.type === 'success' 
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 shadow-[0_0_30px_rgba(16,185,129,0.2)]'
                : 'bg-red-500/10 border-red-500/30 text-red-300 shadow-[0_0_30px_rgba(239,68,68,0.2)]'
            }`}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="absolute top-[20%] left-[20%] w-[30rem] h-[30rem] bg-emerald-500/20 rounded-full blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[20%] right-[20%] w-[30rem] h-[30rem] bg-teal-600/20 rounded-full blur-[150px] pointer-events-none" />

      <div className="relative z-10 flex-1 w-full max-w-[1300px] mx-auto px-4 md:px-8 pt-24 pb-6 flex flex-col lg:flex-row gap-8 h-full">
        
        {/* COLUMN 1: VISUALIZER */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
          className="flex flex-col w-full lg:w-5/12 bg-zinc-900/60 backdrop-blur-[20px] border border-white/[0.05] rounded-[2rem] p-6 shadow-2xl relative min-h-[400px]"
        >
          <div className="flex items-center justify-center shrink-0 mb-8 z-10">
            <h3 className="text-emerald-400 font-bold text-xs tracking-[0.2em] uppercase px-5 py-2 bg-zinc-950/80 rounded-full border border-emerald-900/50 shadow-inner">
              Active Connection
            </h3>
          </div>
          
          <div className="flex-1 flex items-center justify-center w-full">
            <div className="w-[260px] h-[260px] md:w-[320px] md:h-[320px] relative bg-transparent">
              <TileLayout
                chatOpen={false}
                audioVisualizerType={audioVisualizerType}
                audioVisualizerColor={audioVisualizerColor}
                audioVisualizerColorShift={audioVisualizerColorShift}
                audioVisualizerBarCount={audioVisualizerBarCount}
                audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
                audioVisualizerRadialRadius={audioVisualizerRadialRadius}
                audioVisualizerGridRowCount={audioVisualizerGridRowCount}
                audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
                audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
              />
            </div>
          </div>

          <button
            onClick={() => session.end()}
            className="shrink-0 mt-6 w-full rounded-2xl bg-red-950/80 border border-red-900/50 py-4 text-sm font-bold text-red-400 tracking-wider hover:bg-red-900 hover:text-red-100 hover:shadow-[0_0_20px_rgba(220,38,38,0.3)] hover:scale-[1.02] transition-all duration-300 active:scale-95 z-10 relative"
          >
            END CALL
          </button>
        </motion.div>

        {/* COLUMN 2: LIVE CHAT */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
          className="flex flex-col w-full lg:w-7/12 bg-zinc-900/60 backdrop-blur-[20px] border border-white/[0.05] rounded-[2rem] p-6 shadow-2xl relative flex-1 min-h-[500px] lg:h-full lg:max-h-[85vh]"
        >
          <div className="flex items-center justify-between mb-4 border-b border-white/[0.05] pb-4 shrink-0">
            <h3 className="text-zinc-300 font-bold text-sm tracking-widest uppercase flex items-center gap-3">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
              Live Transcript
            </h3>
          </div>

          <div className="flex-1 w-full overflow-y-auto scroll-smooth mb-4 pr-3 flex flex-col" ref={scrollAreaRef}>
            
            {isPreConnectBufferEnabled && messages.length === 0 && (
              <AnimatePresence>
                <div className="flex flex-col items-center justify-center h-full gap-6 mt-10">
                  <MotionMessage
                    key="pre-connect-message"
                    duration={2}
                    {...SHIMMER_MOTION_PROPS}
                    className="text-emerald-400/90 text-lg font-medium tracking-wide"
                  >
                    {preConnectMessage}
                  </MotionMessage>
                  
                  <div className="flex flex-col gap-2 mt-4 items-center">
                    <p className="text-zinc-500 text-xs font-semibold uppercase tracking-widest mb-1">Try saying:</p>
                    {QUICK_PROMPTS.map((prompt, i) => (
                      <span key={i} className="bg-white/[0.03] border border-white/[0.05] px-4 py-2 rounded-full text-zinc-400 text-sm font-light hover:bg-white/[0.08] hover:text-emerald-300 transition-colors cursor-default">
                        "{prompt}"
                      </span>
                    ))}
                  </div>
                </div>
              </AnimatePresence>
            )}

            <AgentChatTranscript
              agentState={agentState}
              messages={messages}
              className="w-full text-base md:text-lg font-light leading-relaxed flex flex-col gap-5 mt-4
              [&_.is-user]:ml-auto [&_.is-user>div]:bg-zinc-800/80 [&_.is-user>div]:border [&_.is-user>div]:border-zinc-700/50 [&_.is-user>div]:text-zinc-200 [&_.is-user>div]:rounded-3xl [&_.is-user>div]:rounded-tr-sm [&_.is-user>div]:px-5 [&_.is-user>div]:py-3 
              [&_.is-agent]:mr-auto [&_.is-agent>div]:bg-emerald-950/50 [&_.is-agent>div]:border [&_.is-agent>div]:border-emerald-900/50 [&_.is-agent>div]:text-emerald-50 [&_.is-agent>div]:rounded-3xl [&_.is-agent>div]:rounded-tl-sm [&_.is-agent>div]:px-5 [&_.is-agent>div]:py-3"
            />
          </div>

          <div className="shrink-0 mt-auto bg-zinc-950/80 rounded-2xl border border-zinc-800/50 p-2 focus-within:ring-2 focus-within:ring-emerald-500/50 focus-within:border-emerald-500/50 transition-all duration-300 shadow-lg">
            <AgentControlBar
              variant="livekit"
              controls={controls}
              isChatOpen={chatOpen}
              isConnected={session.isConnected}
              onDisconnect={session.end}
              onIsChatOpenChange={setChatOpen}
            />
          </div>
        </motion.div>

      </div>
    </section>
  );
}