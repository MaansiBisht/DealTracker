import type { View } from './Tabs';

interface Props {
  view: View;
}

/**
 * Visual stub. No logic, no API calls.
 * Confirms typography, field rhythm, hover/focus shapes for the form section.
 * Wired to real submit logic in step 3.
 */
export function WatchFormStub({ view }: Props) {
  const isHotel = view === 'hotels';

  const urlPlaceholder = isHotel
    ? 'https://www.booking.com/hotel/in/...?checkin=...'
    : 'https://www.amazon.in/dp/...';

  const alertOptions = isHotel
    ? ['price drop']
    : ['stock', 'price'];

  const thresholdHint = isHotel
    ? '₹ per night — alert any date below this'
    : '₹ amount (price alerts only)';

  return (
    <form
      onSubmit={(e) => e.preventDefault()}
      className="bg-surface hairline grid gap-px"
    >
      <Field label="URL" placeholder={urlPlaceholder} />
      <div className="grid grid-cols-[2fr_1fr] gap-px">
        <Field label="Notify email" placeholder="you@example.com" />
        <SelectField label="Alert" options={alertOptions} />
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-px">
        <Field label="Threshold" placeholder={thresholdHint} />
        <SubmitButton />
      </div>
    </form>
  );
}

function Field({ label, placeholder }: { label: string; placeholder: string }) {
  return (
    <label className="group bg-surface hover:bg-elevated transition-colors px-4 py-3 flex flex-col gap-1">
      <span className="chrome-label">{label}</span>
      <input
        type="text"
        placeholder={placeholder}
        className="bg-transparent outline-none text-fg placeholder:text-mute font-mono text-[14px] tabular"
      />
    </label>
  );
}

function SelectField({ label, options }: { label: string; options: string[] }) {
  return (
    <label className="group bg-surface hover:bg-elevated transition-colors px-4 py-3 flex flex-col gap-1">
      <span className="chrome-label">{label}</span>
      <select
        defaultValue={options[0]}
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

function SubmitButton() {
  return (
    <button
      type="submit"
      className="
        bg-ok text-bg
        hover:brightness-95 active:brightness-90
        transition-[filter,letter-spacing] duration-150
        px-8 font-mono text-[13px] tracking-[0.18em]
        flex items-center justify-center gap-2
        focus-visible:outline-2 focus-visible:outline-fg focus-visible:outline-offset-[-2px]
      "
    >
      <span>[ START ]</span>
    </button>
  );
}
