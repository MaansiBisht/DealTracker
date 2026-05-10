import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ApiError, api } from '~/lib/api';
import type {
  AlertType,
  JobCreatePayload,
  JobKind,
  TelegramStatus,
} from '~/types/job';

interface Props {
  view: JobKind;
  onSubmit: (payload: JobCreatePayload) => Promise<void>;
}

const PRODUCT_ALERTS: AlertType[] = ['stock', 'price'];
const HOTEL_ALERTS: AlertType[] = ['price_drop'];

export function WatchForm({ view, onSubmit }: Props) {
  const isHotel = view === 'hotel';
  const alertOptions = isHotel ? HOTEL_ALERTS : PRODUCT_ALERTS;

  const [url, setUrl] = useState('');
  // Per-watch routing: every product can target a different Telegram chat.
  // The Connect button hides the chat_id behind a token-pairing flow.
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [email, setEmail] = useState('');
  const [tgEnabled, setTgEnabled] = useState(true);
  const [tgChatId, setTgChatId] = useState('');
  const [tgDisplayName, setTgDisplayName] = useState<string | null>(null);
  const [alertType, setAlertType] = useState<AlertType>(alertOptions[0]);
  const [threshold, setThreshold] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsThreshold = alertType === 'price' || alertType === 'price_drop';

  if (!alertOptions.includes(alertType)) {
    setAlertType(alertOptions[0]);
  }

  const [tgStatus, setTgStatus] = useState<TelegramStatus | null>(null);
  useEffect(() => {
    api
      .telegramStatus()
      .then(setTgStatus)
      .catch(() => setTgStatus({ configured: false, bot_username: null }));
  }, []);

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

    const payload: JobCreatePayload = {
      url: url.trim(),
      email: trimmedEmail || null,
      webhook_url: null,
      telegram_chat_id: trimmedChat || null,
      alert_type: alertType,
      threshold: needsThreshold ? parseFloat(threshold) : null,
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
      // Keep tgChatId + display name so a follow-up watch reuses the
      // pairing without making the user tap Start again.
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'submit failed');
    } finally {
      setSubmitting(false);
    }
  }

  const urlPlaceholder = isHotel
    ? 'https://www.booking.com/hotel/in/...?checkin=...'
    : 'https://www.amazon.in/dp/...';

  return (
    <form onSubmit={handleSubmit} className="bg-surface hairline grid gap-px">
      <Field
        label="URL"
        placeholder={urlPlaceholder}
        value={url}
        onChange={setUrl}
        required
      />

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
        status={tgStatus}
        enabled={tgEnabled}
        onToggle={setTgEnabled}
        chatId={tgChatId}
        displayName={tgDisplayName}
        onPaired={(chatId, name) => {
          setTgChatId(chatId);
          setTgDisplayName(name);
        }}
        onChatIdChange={(v) => {
          setTgChatId(v);
          setTgDisplayName(null);
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
  status: TelegramStatus | null;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  chatId: string;
  displayName: string | null;
  onPaired: (chatId: string, displayName: string | null) => void;
  onChatIdChange: (v: string) => void;
}

function TelegramToggle({
  status,
  enabled,
  onToggle,
  chatId,
  displayName,
  onPaired,
  onChatIdChange,
}: TelegramToggleProps) {
  const configured = status?.configured ?? false;
  const [pairing, setPairing] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  function stopPolling() {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }
  useEffect(() => stopPolling, []);

  async function startConnect() {
    setError(null);
    setPairing(true);
    try {
      const { token, deep_link } = await api.telegramStartPairing();
      window.open(deep_link, '_blank', 'noopener');
      pollRef.current = window.setInterval(async () => {
        try {
          const s = await api.telegramPairingStatus(token);
          if (s.paired && s.chat_id) {
            stopPolling();
            setPairing(false);
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
    onPaired('', null);
    onChatIdChange('');
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
            <div className="flex items-center gap-3">
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
