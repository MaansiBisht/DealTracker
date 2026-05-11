import { useState } from 'react';
import { Console } from './pages/Console';
import { SignIn } from './pages/SignIn';
import { Tabs, type View } from './components/Tabs';
import { useAuth } from './hooks/useAuth';
import type { User } from './types/job';

export function App() {
  const auth = useAuth();
  const [view, setView] = useState<View>('products');

  // Wait for the first /api/auth/me round-trip so the sign-in screen
  // doesn't flash for an authenticated mount.
  if (!auth.bootstrapped) {
    return <BootSplash />;
  }
  if (auth.user === null) {
    return <SignIn />;
  }

  return (
    <div className="relative z-10 min-h-full flex flex-col">
      <TopBar
        view={view}
        onChangeView={setView}
        currentUser={auth.user}
        onLogout={auth.logout}
      />
      <main className="flex-1 mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-6 sm:py-10">
        <Console
          view={view}
          currentUser={auth.user}
          telegramBotConfigured={auth.telegramBotConfigured}
          telegramBotUsername={auth.telegramBotUsername}
          onAuthRefresh={auth.refresh}
        />
      </main>
      <Footer view={view} />
    </div>
  );
}

function TopBar({
  view,
  onChangeView,
  currentUser,
  onLogout,
}: {
  view: View;
  onChangeView: (v: View) => void;
  currentUser: User;
  onLogout: () => Promise<void> | void;
}) {
  return (
    <header className="hairline-b sticky top-0 z-20 backdrop-blur-sm bg-bg/80">
      <div
        className="
          mx-auto max-w-[1280px] px-4 sm:px-6
          flex items-center justify-between gap-3 sm:gap-6
          h-14
        "
      >
        <div className="flex items-baseline gap-2 sm:gap-3 min-w-0">
          <span className="font-sans text-fg tracking-[0.06em] text-[13px] sm:text-[14px] font-semibold">
            DEALTRACKER
          </span>
          <span className="text-mute hidden sm:inline">·</span>
          <span className="chrome-label hidden sm:inline">ops console</span>
        </div>

        <Tabs value={view} onChange={onChangeView} />

        <div className="chrome-label tabular hidden md:flex items-center gap-3">
          <span className="text-mute truncate max-w-[20ch]">{currentUser.email}</span>
          {currentUser.is_admin && (
            <span className="text-alert tracking-[0.18em]">ADMIN</span>
          )}
          <button
            type="button"
            onClick={() => void onLogout()}
            className="text-dim hover:text-err transition-colors tracking-[0.18em]"
          >
            [logout]
          </button>
        </div>
      </div>
    </header>
  );
}

function BootSplash() {
  return (
    <div className="min-h-full flex items-center justify-center">
      <span className="chrome-label tabular text-mute">loading…</span>
    </div>
  );
}

function Footer({ view }: { view: View }) {
  const tickRate =
    view === 'hotels'
      ? 'tick rate · 3h hotels'
      : 'tick rate · 1h products';
  return (
    <footer className="hairline-t mt-12">
      <div
        className="
          mx-auto max-w-[1280px] px-4 sm:px-6
          flex flex-col sm:flex-row items-start sm:items-center justify-between
          gap-1 sm:gap-3
          py-2 sm:py-0 sm:h-10
          chrome-label
        "
      >
        <span>v0.0.1 · single-tenant</span>
        <span className="tabular">{tickRate}</span>
      </div>
    </footer>
  );
}
