'use client';

import { useMemo, useState } from 'react';
import { TokenSource } from 'livekit-client';
import {
  useSession,
  useConnectionState,
  useVoiceAssistant,
} from '@livekit/components-react';
import { ConnectionState } from 'livekit-client';
import { WarningIcon } from '@phosphor-icons/react/dist/ssr';
import type { AppConfig } from '@/app-config';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { Toaster } from '@/components/ui/sonner';
import { useAgentErrors } from '@/hooks/useAgentErrors';
import { useDebugMode } from '@/hooks/useDebug';
import { getSandboxTokenSource } from '@/lib/utils';

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';

function AppSetup() {
  useDebugMode({ enabled: IN_DEVELOPMENT });
  useAgentErrors();
  return null;
}

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  const [micError, setMicError] = useState<string | null>(null);

  const tokenSource = useMemo(() => {
    return typeof process.env.NEXT_PUBLIC_CONN_DETAILS_ENDPOINT === 'string'
      ? getSandboxTokenSource(appConfig)
      : TokenSource.endpoint('/api/token');
  }, [appConfig]);

  const session = useSession(
    tokenSource,
    appConfig.agentName ? { agentName: appConfig.agentName } : undefined
  );

  return (
    <AgentSessionProvider session={session}>
      <AppSetup />
      <KiranaCard session={session} setMicError={setMicError} micError={micError} />
      <Toaster icons={{ warning: <WarningIcon weight="bold" /> }} position="top-center" />
    </AgentSessionProvider>
  );
}

function KiranaCard({
  session,
  setMicError,
  micError,
}: {
  session: any;
  setMicError: (err: string | null) => void;
  micError: string | null;
}) {
  const connectionState = useConnectionState();
  const { state: agentState } = useVoiceAssistant();
  const [chatMessage, setChatMessage] = useState('');

  const handleStartCall = async () => {
    try {
      setMicError(null);
      await navigator.mediaDevices.getUserMedia({ audio: true });
      if (session?.start) {
        await session.start();
      }
    } catch (err) {
      setMicError(
        'Microphone access blocked! Please click the icon in your browser address bar to allow permissions.'
      );
    }
  };

  const handleEndCall = () => {
    if (session?.end) {
      session.end();
    }
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;

    // Send text message via LiveKit session data channel
    if (session?.sendData) {
      const encoder = new TextEncoder();
      session.sendData(encoder.encode(chatMessage), { topic: 'chat' });
    }
    setChatMessage('');
  };

  return (
    <div className="w-full max-w-xl mx-auto flex flex-col items-center justify-center p-6 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl">
      {/* Microphone Error Alert */}
      {micError && (
        <div className="w-full mb-6 bg-red-950/80 border border-red-600 text-red-200 text-xs p-3 rounded-xl text-center font-medium">
          ⚠️ {micError}
        </div>
      )}

      {/* STATE 1: Ready */}
      {connectionState === ConnectionState.Disconnected && (
        <div className="flex flex-col items-center gap-6 py-6">
          <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center text-4xl border border-slate-700 shadow-inner">
            🛒
          </div>
          <div className="text-center">
            <h2 className="text-lg font-bold text-slate-100">Ready to Take Your Order</h2>
            <p className="text-xs text-slate-400 mt-1">Check stock, prices, or order daily groceries</p>
          </div>

          <button
            onClick={handleStartCall}
            className="flex items-center justify-center gap-3 px-8 py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl shadow-lg shadow-emerald-900/40 transition-all transform hover:scale-105 active:scale-95 cursor-pointer"
          >
            <span>Start Kirana Call</span>
            <span className="text-xl bg-emerald-700 p-1.5 rounded-lg border border-emerald-400/30">🛒</span>
            <span>(कॉल सुरू करा)</span>
          </button>
        </div>
      )}

      {/* STATE 2: Connecting */}
      {connectionState === ConnectionState.Connecting && (
        <div className="flex flex-col items-center gap-4 py-8">
          <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-emerald-400 text-sm font-medium">Connecting to shop... (कृपया थांबा)</p>
        </div>
      )}

      {/* CONNECTED STATES: Old Waveform + Typeable Chat Input */}
      {connectionState === ConnectionState.Connected && (
        <div className="w-full flex flex-col items-center gap-5">
          
          {/* STATE 3: Listening Badge */}
          {agentState === 'listening' && (
            <div className="flex items-center gap-2 bg-blue-950 border border-blue-700 px-4 py-1.5 rounded-full text-blue-300 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping"></span>
              Listening to you... (तुमचे बोलणे ऐकत आहे)
            </div>
          )}

          {/* STATE 4: Speaking Badge */}
          {agentState === 'speaking' && (
            <div className="flex items-center gap-2 bg-emerald-950 border border-emerald-700 px-4 py-1.5 rounded-full text-emerald-300 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              Kirana Assistant is speaking... (उत्तर देत आहे)
            </div>
          )}

          {(agentState === 'thinking' || agentState === 'initializing') && (
            <div className="flex items-center gap-2 bg-amber-950 border border-amber-700 px-4 py-1.5 rounded-full text-amber-300 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
              Thinking... (विचार करत आहे)
            </div>
          )}

          {/* Restored Old Spectrum Waveform */}
          <SpectrumWaveform state={agentState} />

          {/* Typeable Chat Input Box */}
          <form onSubmit={handleSendMessage} className="w-full flex items-center gap-2">
            <input
              type="text"
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              placeholder="Type something... (इथे टाईप करा)"
              className="flex-1 bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-500 text-xs rounded-xl px-4 py-3 focus:outline-none focus:border-emerald-500 transition-colors"
            />
            <button
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-3 rounded-xl transition-all cursor-pointer"
            >
              Send
            </button>
          </form>

          {/* STATE 5: Call Ended Option */}
          <button
            onClick={handleEndCall}
            className="px-6 py-2 bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white border border-red-800 rounded-xl text-xs font-bold transition-all cursor-pointer mt-2"
          >
            End Call (कॉल संपवा)
          </button>
        </div>
      )}
    </div>
  );
}

{/* Restored Spectrum Bar Waveform */}
function SpectrumWaveform({ state }: { state: string }) {
  const isListening = state === 'listening';
  const isSpeaking = state === 'speaking';
  
  const barColor = isSpeaking
    ? 'bg-emerald-400 border-emerald-300'
    : isListening
    ? 'bg-blue-400 border-blue-300'
    : 'bg-slate-600 border-slate-500';

  return (
    <div className="w-full h-24 flex items-center justify-center gap-2 bg-slate-950 rounded-xl p-4 border border-slate-800 shadow-inner">
      {[40, 75, 30, 90, 60, 100, 45, 80, 35, 70, 50, 85, 25, 65].map((height, i) => (
        <div
          key={i}
          style={{
            height: isSpeaking || isListening ? `${height}%` : '15%',
            transition: 'height 0.15s ease-in-out',
          }}
          className={`w-2 rounded-full border-t ${barColor} ${
            isSpeaking || isListening ? 'animate-pulse' : ''
          }`}
        />
      ))}
    </div>
  );
}