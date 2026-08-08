import { headers } from 'next/headers';
import { App } from '@/components/app/app';
import { getAppConfig } from '@/lib/utils';

export default async function Page() {
  const hdrs = await headers();
  const appConfig = await getAppConfig(hdrs);

  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-6 bg-slate-950 text-slate-100">
      {/* Header Section */}
      <header className="w-full max-w-3xl flex items-center justify-between pb-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-emerald-600 flex items-center justify-center font-bold text-xl text-white shadow-lg shadow-emerald-900/30">
            🛒
          </div>
          <div>
            <h1 className="text-xl font-bold text-emerald-400">
              The Grocery
            </h1>
            <p className="text-xs text-slate-400">
              किराणा • Voice Ordering System
            </p>
          </div>
        </div>
        <span className="bg-emerald-950/80 text-emerald-300 text-xs font-medium px-3 py-1 rounded-full border border-emerald-800">
          Local Commerce
        </span>
      </header>

      {/* Main Interface */}
      <section className="w-full max-w-xl my-auto flex flex-col items-center justify-center py-8">
        <App appConfig={appConfig} />
      </section>

      {/* Footer */}
      <footer className="text-center text-xs text-slate-500 pt-6">
        <p>Ask about daily produce rates, stock availability, or place a home delivery order.</p>
        <p className="mt-1 text-slate-600">Powered by Murf Falcon & LiveKit</p>
      </footer>
    </main>
  );
}