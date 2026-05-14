import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ApiError, api } from '~/lib/api';
import type {
  AlertType,
  JobCreatePayload,
  JobKind,
  User,
} from '~/types/job';

interface Props {
  view: JobKind;
  onSubmit: (payload: JobCreatePayload) => Promise<void>;
  // The signed-in user. Their persistent Telegram pairing seeds this
  // form so a refresh, a new tab, or a different device all show the
  // same "✓ connected" without re-pairing.
  currentUser: User;
  // Bot config flows down from /api/auth/me alongside the user. Reused
  // here so the form doesn't need a second API round-trip on mount.
  telegramBotConfigured: boolean;
  telegramBotUsername: string | null;
  // Asks the parent to re-pull /api/auth/me — used after a successful
  // pair or disconnect so the rest of the app reflects the new state.
  onAuthRefresh: () => Promise<void>;
}

const PRODUCT_ALERTS: AlertType[] = ['stock', 'price'];
const HOTEL_ALERTS: AlertType[] = ['price_drop'];

export function WatchForm({
  view,
  onSubmit,
  currentUser,
  telegramBotConfigured,
  telegramBotUsername,
  onAuthRefresh,
}: Props) {
  const isHotel = view === 'hotel';
  const alertOptions = isHotel ? HOTEL_ALERTS : PRODUCT_ALERTS;

  const [url, setUrl] = useState('');
  // Per-watch Telegram chat targeting. Initial value comes from the
  // server-persisted pairing on the User row; the user can still paste
  // a different chat_id per watch via the advanced panel.
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [email, setEmail] = useState('');
  const [tgEnabled, setTgEnabled] = useState(true);
  const [tgChatId, setTgChatId] = useState<string>(currentUser.telegram_chat_id ?? '');
  const [tgDisplayName, setTgDisplayName] = useState<string | null>(
    currentUser.telegram_display_name,
  );
  const [alertType, setAlertType] = useState<AlertType>(alertOptions[0]);
  const [threshold, setThreshold] = useState('');
  // Hotel night-range. Only sent when both are set AND view === 'hotel'.
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsThreshold = alertType === 'price' || alertType === 'price_drop';
  const MAX_NIGHTS = 14;

  if (!alertOptions.includes(alertType)) {
    setAlertType(alertOptions[0]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmedEmail = emailEnabled ? email.trim() : '';
    const trimmedChat = tgEnabled ? tgChatId.trim() : '';

    if (!trimmedEmail && !trimmedChat) {
      setError('enable at least one delivery channel');
      return;
    }
    if (trimmedChat && !/^-?\d+$/.test(trimmedChat)) {
      setError('telegram chat ID must be a number — message the bot to grab yours');
      return;
    }

    // Hotel: dates required. Validate range client-side; server re-validates.
    let dateStartOut: string | null = null;
    let dateEndOut: string | null = null;
    if (isHotel) {
      if (!dateStart || !dateEnd) {
        setError('check-in and check-out dates are required for hotel watches');
        return;
      }
      const s = new Date(dateStart);
      const e = new Date(dateEnd);
      if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) {
        setError('invalid date');
        return;
      }
      if (e <= s) {
        setError('check-out must be after check-in');
        return;
      }
      const nights = Math.round((e.getTime() - s.getTime()) / 86_400_000);
      if (nights > MAX_NIGHTS) {
        setError(`date range too long — max ${MAX_NIGHTS} nights`);
        return;
      }
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (s < today) {
        setError('check-in must be today or later');
        return;
      }
      dateStartOut = dateStart;
      dateEndOut = dateEnd;
    }

    const payload: JobCreatePayload = {
      url: url.trim(),
      email: trimmedEmail || null,
      webhook_url: null,
      telegram_chat_id: trimmedChat || null,
      alert_type: alertType,
      threshold: needsThreshold ? parseFloat(threshold) : null,
      date_start: dateStartOut,
      date_end: dateEndOut,
    };
    if (needsThreshold && (!Number.isFinite(payload.threshold) || (payload.threshold ?? 0) <= 0)) {
      setError('threshold must be a positive number');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit(payload);
      setUrl('');
      setEmail('');
      setThreshold('');
      setDateStart('');
      setDateEnd('');
      // Keep tgChatId + display name so a follow-up watch reuses the
      // pairing without making the user tap Start again.
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'submit failed');
    } finally {
      setSubmitting(false);
    }
  }

  const urlPlaceholder = isHotel
    ? 'https://www.booking.com/hotel/in/... (no dates needed)'
    : 'https://www.amazon.in/dp/...';
  // ISO YYYY-MM-DD for <input type="date" min=...> — today.
  const todayIso = new Date().toISOString().slice(0, 10);

  return (
    <form onSubmit={handleSubmit} className="bg-surface hairline grid gap-px">
      <Field
        label="URL"
        placeholder={urlPlaceholder}
        value={url}
        onChange={setUrl}
        required
      />

      {isHotel && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-px">
          <DateField
            label="check-in"
            value={dateStart}
            onChange={setDateStart}
            min={todayIso}
          />
          <DateField
            label="check-out"
            value={dateEnd}
            onChange={setDateEnd}
            min={dateStart || todayIso}
          />
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-[2fr_1fr] gap-px">
        <ToggleField
          label="notify email"
          checked={emailEnabled}
          onToggle={setEmailEnabled}
          placeholder="you@example.com"
          value={email}
          onChange={setEmail}
          type="email"
        />
        <SelectField
          label="Alert"
          value={alertType}
          options={alertOptions}
          onChange={(v) => setAlertType(v as AlertType)}
        />
      </div>

      <TelegramToggle
        configured={telegramBotConfigured}
        botUsername={telegramBotUsername}
        enabled={tgEnabled}
        onToggle={setTgEnabled}
        chatId={tgChatId}
        displayName={tgDisplayName}
        onPaired={async (chatId, name) => {
          setTgChatId(chatId);
          setTgDisplayName(name);
          // Pull the fresh user row so the rest of the app reflects the
          // new persistent pairing.
          await onAuthRefresh();
        }}
        onChatIdChange={(v) => {
          // Manual paste is a per-watch override — does not touch the
          // server-side persistent pairing.
          setTgChatId(v);
          setTgDisplayName(null);
        }}
        onDisconnect={async () => {
          // Clears both the local "this watch will use…" state and the
          // user's persistent pairing on the server.
          try {
            await api.telegramDisconnect();
          } catch {
            /* swallow — even if the server call fails, the local form
               state below should still clear so submit works. */
          }
          setTgChatId('');
          setTgDisplayName(null);
          await onAuthRefresh();
        }}
      />

      <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-px">
        <Field
          label="Threshold"
          placeholder={needsThreshold ? '₹ amount' : '—  not used for this alert'}
          value={threshold}
          onChange={setThreshold}
          disabled={!needsThreshold}
          inputMode="decimal"
        />
        <SubmitButton submitting={submitting} />
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="bg-bg px-4 py-2 text-err text-[12.5px]"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>
    </form>
  );
}


/* ---------- Telegram Connect-button toggle ------------------------------- */

interface TelegramToggleProps {
  configured: boolean;
  botUsername: string | null;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  chatId: string;
  displayName: string | null;
  onPaired: (chatId: string, displayName: string | null) => void | Promise<void>;
  onChatIdChange: (v: string) => void;
  onDisconnect: () => void | Promise<void>;
}

function TelegramToggle({
  configured,
  botUsername,
  enabled,
  onToggle,
  chatId,
  displayName,
  onPaired,
  onChatIdChange,
  onDisconnect,
}: TelegramToggleProps) {
  const username = botUsername ?? 'your_bot';
  const [pairing, setPairing] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Last-issued pairing token + how long we've been waiting. After ~6s
  // we surface a manual fallback for Telegram Web users — its "Start Bot"
  // button is known to silently fail to fire /start to the bot.
  const [activeToken, setActiveToken] = useState<string | null>(null);
  const [pairingElapsedSec, setPairingElapsedSec] = useState(0);
  const pollRef = useRef<number | null>(null);
  const tickRef = useRef<number | null>(null);

  function stopPolling() {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }
  useEffect(() => stopPolling, []);

  async function startConnect() {
    setError(null);
    setPairing(true);
    setPairingElapsedSec(0);
    try {
      const { token, deep_link } = await api.telegramStartPairing();
      setActiveToken(token);
      window.open(deep_link, '_blank', 'noopener');

      // Drive the elapsed counter so the fallback panel can decide when
      // to surface itself.
      tickRef.current = window.setInterval(() => {
        setPairingElapsedSec((s) => s + 1);
      }, 1000);

      pollRef.current = window.setInterval(async () => {
        try {
          const s = await api.telegramPairingStatus(token);
          if (s.paired && s.chat_id) {
            stopPolling();
            setPairing(false);
            setActiveToken(null);
            setPairingElapsedSec(0);
            onPaired(s.chat_id, s.display_name);
          }
        } catch {
          // ignore transient poll failures — keep polling.
        }
      }, 2000);
    } catch (e) {
      setPairing(false);
      setError(e instanceof ApiError ? e.message : 'could not start pairing');
    }
  }

  function disconnect() {
    stopPolling();
    setPairing(false);
    setActiveToken(null);
    setPairingElapsedSec(0);
    void onDisconnect();
  }

  async function copyManualCommand() {
    if (!activeToken) return;
    const cmd = `/start ${activeToken}`;
    try {
      await navigator.clipboard.writeText(cmd);
    } catch {
      // older browsers — silently no-op; user can read+type it manually.
    }
  }

  if (!configured) {
    return (
      <div className="bg-surface px-4 py-3 flex flex-col gap-1 opacity-60">
        <span className="chrome-label flex items-center gap-2">
          <CheckBox checked={false} />
          notify telegram
          <span className="text-mute normal-case tracking-normal">
            — disabled · operator hasn't set TELEGRAM_BOT_TOKEN
          </span>
        </span>
      </div>
    );
  }

  const inactive = !enabled;
  return (
    <div
      className={`
        bg-surface px-4 py-3 flex flex-col gap-2
        transition-colors
        ${inactive ? 'opacity-60' : 'hover:bg-elevated focus-within:bg-elevated'}
      `}
    >
      <button
        type="button"
        onClick={() => onToggle(!enabled)}
        className="chrome-label flex items-center gap-2 self-start text-left cursor-pointer hover:text-fg transition-colors"
      >
        <CheckBox checked={enabled} />
        <span>notify telegram</span>
        <span className="text-mute normal-case tracking-normal">
          — alerts go straight to a Telegram chat
        </span>
      </button>

      {enabled && (
        <div className="flex flex-col gap-1.5">
          {chatId ? (
            <div className="flex items-center gap-3 font-mono text-[13px]">
              <span className="text-ok">
                ✓ connected{displayName ? ` to ${displayName}` : ''}
              </span>
              <button
                type="button"
                onClick={disconnect}
                className="chrome-label tabular tracking-[0.18em] text-mute hover:text-err transition-colors"
              >
                [disconnect]
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  type="button"
                  onClick={startConnect}
                  disabled={pairing}
                  className="
                    bg-info text-bg
                    hover:brightness-95 disabled:opacity-70 disabled:cursor-progress
                    transition-[filter] duration-150
                    h-9 px-4 font-mono text-[12px] tracking-[0.16em]
                    focus-visible:outline-2 focus-visible:outline-fg focus-visible:outline-offset-[-2px]
                  "
                >
                  {pairing ? '[ WAITING IN TELEGRAM… ]' : '[ CONNECT TELEGRAM ⇗ ]'}
                </button>
                {error && <span className="text-err text-[12.5px]">{error}</span>}
              </div>

              {/* Telegram Web sometimes fails to send /start when the user
                  taps "Start Bot" on the t.me intro page. After 6s we give
                  them a one-paste manual fallback. */}
              {pairing && activeToken && pairingElapsedSec >= 6 && (
                <div className="flex flex-col gap-1 text-[12px] text-mute">
                  <span>
                    Stuck on Telegram Web? Open{' '}
                    <a
                      href={`https://t.me/${username}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-info underline-offset-2 hover:underline"
                    >
                      @{username}
                    </a>{' '}
                    in Telegram and send this exact command:
                  </span>
                  <div className="flex items-center gap-2 flex-wrap">
                    <code
                      className="
                        font-mono text-fg bg-bg
                        hairline px-2 py-1 select-all
                        text-[12.5px]
                      "
                    >
                      /start {activeToken}
                    </code>
                    <button
                      type="button"
                      onClick={copyManualCommand}
                      className="chrome-label tabular tracking-[0.18em] text-mute hover:text-fg transition-colors"
                    >
                      [copy]
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Advanced: paste a chat ID directly (for routing alerts to someone
              else without making them click Start). */}
          {!chatId && (
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="chrome-label text-mute hover:text-dim transition-colors text-left self-start"
            >
              {showAdvanced ? '↑ hide manual chat ID' : '↓ I already have a chat ID'}
            </button>
          )}
          {showAdvanced && !chatId && (
            <input
              type="text"
              inputMode="numeric"
              placeholder="paste chat ID, e.g. 987654321"
              value={chatId}
              onChange={(e) => onChatIdChange(e.target.value)}
              className="
                bg-transparent outline-none text-fg placeholder:text-mute
                font-mono text-[14px] tabular
                hairline-b pb-1
              "
            />
          )}
        </div>
      )}
    </div>
  );
}


/* ---------- shared field primitives --------------------------------------- */

interface FieldProps {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  disabled?: boolean;
  inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode'];
}

function Field({ label, placeholder, value, onChange, type = 'text', required, disabled, inputMode }: FieldProps) {
  return (
    <label
      className={`
        group bg-surface px-4 py-3 flex flex-col gap-1
        transition-colors
        ${disabled ? 'opacity-50' : 'hover:bg-elevated focus-within:bg-elevated'}
      `}
    >
      <span className="chrome-label">{label}</span>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        disabled={disabled}
        inputMode={inputMode}
        className="bg-transparent outline-none text-fg placeholder:text-mute font-mono text-[14px] tabular disabled:cursor-not-allowed"
      />
    </label>
  );
}

interface ToggleFieldProps {
  label: string;
  checked: boolean;
  onToggle: (v: boolean) => void;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}

function ToggleField({
  label,
  checked,
  onToggle,
  placeholder,
  value,
  onChange,
  type = 'text',
}: ToggleFieldProps) {
  const inactive = !checked;
  return (
    <div
      className={`
        group bg-surface px-4 py-3 flex flex-col gap-1
        transition-colors
        ${inactive ? 'opacity-60' : 'hover:bg-elevated focus-within:bg-elevated'}
      `}
    >
      <button
        type="button"
        onClick={() => onToggle(!checked)}
        className="chrome-label flex items-center gap-2 self-start text-left cursor-pointer hover:text-fg transition-colors"
      >
        <CheckBox checked={checked} />
        <span>{label}</span>
      </button>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={inactive}
        className="bg-transparent outline-none text-fg placeholder:text-mute font-mono text-[14px] tabular disabled:cursor-not-allowed"
      />
    </div>
  );
}

interface DateFieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  min?: string;
}

function DateField({ label, value, onChange, min }: DateFieldProps) {
  return (
    <label className="group bg-surface hover:bg-elevated focus-within:bg-elevated transition-colors px-4 py-3 flex flex-col gap-1">
      <span className="chrome-label">{label}</span>
      <input
        type="date"
        value={value}
        min={min}
        onChange={(e) => onChange(e.target.value)}
        required
        className="bg-transparent outline-none text-fg font-mono text-[14px] tabular"
      />
    </label>
  );
}


function CheckBox({ checked }: { checked: boolean }) {
  return (
    <span
      className={`
        inline-block w-3 h-3 hairline tabular text-[10px] leading-[10px] text-center
        transition-colors
        ${checked ? 'bg-ok text-bg' : 'bg-transparent text-transparent'}
      `}
    >
      ×
    </span>
  );
}

interface SelectFieldProps {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}

function SelectField({ label, value, options, onChange }: SelectFieldProps) {
  return (
    <label className="group bg-surface hover:bg-elevated focus-within:bg-elevated transition-colors px-4 py-3 flex flex-col gap-1 cursor-pointer">
      <span className="chrome-label flex items-center justify-between">
        <span>{label}</span>
        <span className="text-mute normal-case tracking-normal text-[10px]">change ▾</span>
      </span>
      <div className="flex items-center justify-between gap-2">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="bg-transparent outline-none text-fg text-[14px] appearance-none cursor-pointer flex-1"
        >
          {options.map((o) => (
            <option key={o} value={o} className="bg-bg text-fg">
              {o}
            </option>
          ))}
        </select>
        <span className="text-dim group-hover:text-fg transition-colors text-[12px] select-none pointer-events-none">
          ▾
        </span>
      </div>
    </label>
  );
}

function SubmitButton({ submitting }: { submitting: boolean }) {
  const label = submitting ? '[ STARTING… ]' : '[ START ]';
  return (
    <button
      type="submit"
      disabled={submitting}
      className="
        bg-ok text-bg
        hover:brightness-95 active:brightness-90 disabled:opacity-70 disabled:cursor-progress
        transition-[filter,letter-spacing] duration-150
        h-11 sm:h-10
        w-full sm:w-auto
        sm:self-center sm:mr-3
        px-4
        font-mono text-[13px] tracking-[0.16em]
        flex items-center justify-center gap-2
        focus-visible:outline-2 focus-visible:outline-fg focus-visible:outline-offset-[-2px]
      "
    >
      <motion.span
        key={label}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.15 }}
      >
        {label}
      </motion.span>
    </button>
  );
}
