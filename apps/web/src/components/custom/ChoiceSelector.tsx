import type { SearchOption } from '../../interfaces/search-option';
import { SearchSelector } from './SearchSelector';

export function ChoiceSelector({
  id,
  label,
  options,
  value,
  onChange,
  disabled = false,
  className = '',
}: {
  id: string;
  label: string;
  options: SearchOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div className={`choice-field ${className}`.trim()}>
      <label htmlFor={id}>{label}</label>
      <SearchSelector
        id={id}
        label={label}
        options={options}
        value={value}
        onChange={onChange}
        disabled={disabled}
        placeholder={`Elegir ${label.toLocaleLowerCase('es')}`}
        showCode={false}
        clearable={false}
      />
    </div>
  );
}
