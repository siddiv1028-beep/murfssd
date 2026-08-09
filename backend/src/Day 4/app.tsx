'use client';

import { useMemo, useEffect, useState } from 'react';
import { TokenSource } from 'livekit-client';
import { useSession, useVoiceAssistant } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react/dist/ssr';
import type { AppConfig } from '@/app-config';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/ui/sonner';
import { useAgentErrors } from '@/hooks/useAgentErrors';
import { useDebugMode } from '@/hooks/useDebug';
import { getSandboxTokenSource } from '@/lib/utils';

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';

function TopNavigationBar() {
  const { state } = useVoiceAssistant();
  
  const getStateText = () => {
    switch (state) {
      case 'disconnected': return 'Call Ended';
      case 'connecting': return 'Connecting...';
      case 'listening': return 'Listening...';
      case 'speaking': return 'Speaking — Mita';
      default: return 'Ready';
    }
  };

  if (state === 'disconnected') return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex justify-between items-start p-4 md:p-6 pointer-events-none">
      
      {/* Top Left Branding */}
      <div className="flex items-center gap-3 bg-zinc-900/90 backdrop-blur-md px-4 py-3 rounded-2xl border border-zinc-800 shadow-lg pointer-events-auto">
        <span className="text-2xl bg-zinc-800 p-2 rounded-lg">🏪</span>
        <div>
          <h2 className="text-emerald-400 font-bold text-base md:text-lg leading-tight">Home Fresh Grocery</h2>
          <p className="text-zinc-400 text-xs font-medium">Digital Kirana Assistant</p>
        </div>
      </div>

      {/* Top Right Status Pill */}
      <div className="bg-emerald-950/80 backdrop-blur-md px-5 py-2.5 rounded-full border border-emerald-800/50 shadow-lg pointer-events-auto flex items-center gap-2">
        {state === 'speaking' && (
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
        )}
        <p className="text-emerald-400 text-sm font-bold tracking-wide">{getStateText()}</p>
      </div>

    </div>
  );
}

function MicPermissionCheck() {
  const [micError, setMicError] = useState(false);

  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ audio: true }).catch(() => {
      setMicError(true);
    });
  }, []);

  if (!micError) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-lg bg-red-950 px-6 py-4 shadow-2xl border border-red-800 w-11/12 max-w-md">
      <p className="text-red-400 font-semibold text-center">
        ⚠️ Microphone access blocked. <br/>
        Please allow microphone permissions in your browser.
      </p>
    </div>
  );
}

function AppSetup() {
  useDebugMode({ enabled: IN_DEVELOPMENT });
  useAgentErrors();
  return null;
}

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
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
      
      <MicPermissionCheck />
      
      {/* The new Navigation Header */}
      <TopNavigationBar />

      <main className="grid h-svh grid-cols-1 place-content-center bg-zinc-950">
        <ViewController appConfig={appConfig} />
      </main>
      
      <StartAudioButton label="Start Audio" />
      <Toaster
        icons={{ warning: <WarningIcon weight="bold" /> }}
        position="top-center"
        className="toaster group"
        style={
          {
            '--normal-bg': 'var(--popover)',
            '--normal-text': 'var(--popover-foreground)',
            '--normal-border': 'var(--border)',
          } as React.CSSProperties
        }
      />
    </AgentSessionProvider>
  );
}