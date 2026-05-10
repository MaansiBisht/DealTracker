import { useState } from 'react';
import { Console } from './pages/Console';
import { Tabs, type View } from './components/Tabs';

export function App() {
  const [view, setView] = useState<View>('products');

  return (
    <div className="relative z-10 min-h-full flex flex-col">
      <TopBar view={view} onChangeView={setView} />
      <main className="flex-1 mx-auto w-full max-w-[1280px] px-4 sm:px-6 py-6 sm:py-10">
        <Console view={view} />
      </main>
      <Footer view={view} />
    </div>
  );
}

function TopBar({ view, onChangeView }: { view: View; onChangeView: (v: View) => void }) {
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

        <div className="chrome-label tabular hidden md:flex">
          <span className="text-mute">user</span>
          <span className="text-dim">@</span>
          <span className="text-dim">contabo</span>
        </div>
      </div>
    </header>
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
