import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ApiError } from '~/lib/api';
import type { AlertType, JobCreatePayload, JobKind } from '~/types/job';

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
  const [email, setEmail] = useState('');
  const [alertType, setAlertType] = useState<AlertType>(alertOptions[0]);
  const [threshold, setThreshold] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const needsThreshold = alertType === 'price' || alertType === 'price_drop';

  // Reset alert type when the tab flips so the dropdown stays valid.
  if (!alertOptions.includes(alertType)) {
    setAlertType(alertOptions[0]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const payload: JobCreatePayload = {
      url: url.trim(),
      email: email.trim(),
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
      <div className="grid grid-cols-[2fr_1fr] gap-px">
        <Field
          label="Notify email"
          placeholder="you@example.com"
          value={email}
          onChange={setEmail}
          type="email"
          required
        />
        <SelectField
          label="Alert"
          value={alertType}
          options={alertOptions}
          onChange={(v) => setAlertType(v as AlertType)}
        />
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-px">
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

interface SelectFieldProps {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}

function SelectField({ label, value, options, onChange }: SelectFieldProps) {
  return (
    <label className="group bg-surface hover:bg-elevated focus-within:bg-elevated transition-colors px-4 py-3 flex flex-col gap-1">
      <span className="chrome-label">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent outline-none text-fg text-[14px] appearance-none cursor-pointer"
      >
        {options.map((o) => (
          <option key={o} value={o} className="bg-bg text-fg">
            {o}
          </option>
        ))}
      </select>
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
        px-8 font-mono text-[13px] tracking-[0.18em]
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
