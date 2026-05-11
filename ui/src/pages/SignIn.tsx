import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ApiError, api } from '~/lib/api';

type Phase = 'compose' | 'sent';

export function SignIn() {
  const [phase, setPhase] = useState<Phase>('compose');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Surface the magic-link redirect's ?login_error=... so the SPA can
  // explain why a click failed instead of silently returning to compose.
  const [linkError, setLinkError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const e = params.get('login_error');
    if (e) {
      setLinkError(e);
      // Strip the query string so refreshing the page doesn't keep flashing the error.
      const url = new URL(window.location.href);
      url.search = '';
      window.history.replaceState({}, '', url.toString());
    }
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLinkError(null);
    const trimmed = email.trim();
    if (!trimmed) {
      setError('enter your email');
      return;
    }
    setSubmitting(true);
    try {
      await api.authRequestMagicLink(trimmed);
      setPhase('sent');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError('too many requests · try again in a few minutes');
        } else if (err.status === 422) {
          setError('that doesn’t look like a valid email');
        } else {
          setError(err.message || 'could not send link');
        }
      } else {
        setError('could not send link');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-full flex flex-col">
      <header className="hairline-b">
        <div className="mx-auto max-w-[1280px] px-4 sm:px-6 h-14 flex items-center">
          <span className="font-sans text-fg tracking-[0.06em] text-[13px] sm:text-[14px] font-semibold">
            DEALTRACKER
          </span>
          <span className="text-mute mx-2">·</span>
          <span className="chrome-label">sign in</span>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-[420px] px-4 py-12 sm:py-20">
        <AnimatePresence mode="wait">
          {phase === 'compose' ? (
            <motion.section
              key="compose"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18 }}
            >
              <h1 className="font-sans text-[20px] sm:text-[22px] text-fg mb-2 font-semibold">
                Sign in
              </h1>
              <p className="text-[13px] text-mute mb-6 leading-relaxed">
                Drop your email below. We&rsquo;ll send you a one-time link
                that signs you in for the next 24 hours on this browser.
                No password.
              </p>

              <form onSubmit={handleSubmit} className="bg-surface hairline grid gap-px">
                <label className="bg-surface px-4 py-3 flex flex-col gap-1 focus-within:bg-elevated transition-colors">
                  <span className="chrome-label">email</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    autoFocus
                    required
                    className="bg-transparent outline-none text-fg placeholder:text-mute font-mono text-[14px] tabular"
                  />
                </label>
                <button
                  type="submit"
                  disabled={submitting}
                  className="
                    bg-ok text-bg
                    hover:brightness-95 active:brightness-90
                    disabled:opacity-70 disabled:cursor-progress
                    transition-[filter] duration-150
                    h-11 px-4
                    font-mono text-[13px] tracking-[0.16em]
                  "
                >
                  {submitting ? '[ SENDING… ]' : '[ SEND LOGIN LINK ]'}
                </button>
              </form>

              <AnimatePresence>
                {error && (
                  <motion.p
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.18 }}
                    className="text-err text-[12.5px] mt-3"
                  >
                    {error}
                  </motion.p>
                )}
              </AnimatePresence>

              {linkError && !error && (
                <p className="text-err text-[12.5px] mt-3">
                  {linkErrorMessage(linkError)}
                </p>
              )}
            </motion.section>
          ) : (
            <motion.section
              key="sent"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18 }}
              className="bg-surface hairline px-5 py-6"
            >
              <h1 className="font-sans text-[18px] text-fg mb-2 font-semibold">
                Check your inbox
              </h1>
              <p className="text-[13px] text-mute leading-relaxed">
                We sent a sign-in link to{' '}
                <span className="text-fg font-mono">{email}</span>. The link
                is valid for 15 minutes and can only be used once.
              </p>
              <button
                type="button"
                onClick={() => setPhase('compose')}
                className="chrome-label tabular tracking-[0.18em] text-mute hover:text-fg transition-colors mt-4"
              >
                [ use a different email ]
              </button>
            </motion.section>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

function linkErrorMessage(code: string): string {
  if (code === 'token_expired')      return 'that link expired · request a fresh one below';
  if (code === 'token_already_used') return 'that link was already used · request a new one below';
  if (code === 'unknown_token')      return 'unknown login link · request a new one below';
  return `sign-in link error · ${code}`;
}
