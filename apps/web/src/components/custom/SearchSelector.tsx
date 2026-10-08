// Searchable name/code selector shared by geographic and market navigation.
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { filterOptions } from '../../lib/search-options';
import type { SearchOption } from '../../interfaces/search-option';

interface SearchSelectorProps {
  id: string;
  label: string;
  options: SearchOption[];
  value: string;
  disabled: boolean;
  placeholder: string;
  onChange: (code: string) => void;
  showCode?: boolean;
  clearable?: boolean;
  optionDetail?: (code: string) => string;
  describedBy?: string;
}

function scrollActiveOption(node: HTMLLIElement | null) {
  if (!node?.parentElement) return;
  const list = node.parentElement;
  const optionBounds = node.getBoundingClientRect();
  const listBounds = list.getBoundingClientRect();
  const top = listBounds.top + list.clientTop;
  const bottom = top + list.clientHeight;
  if (optionBounds.top < top) list.scrollTop += optionBounds.top - top;
  else if (optionBounds.bottom > bottom)
    list.scrollTop += optionBounds.bottom - bottom;
}

export function SearchSelector({
  id,
  label,
  options,
  value,
  disabled,
  placeholder,
  onChange,
  showCode = true,
  clearable = true,
  optionDetail,
  describedBy,
}: SearchSelectorProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const [context, setContext] = useState({ value, disabled });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState<string | null>(null);
  const selected = options.find((option) => option.code === value);
  const results = filterOptions(options, editing ? query : '');
  const activeCode =
    results.find((option) => option.code === active)?.code ?? results[0]?.code;
  const text = editing
    ? query
    : selected
      ? showCode
        ? `${selected.title} · ${selected.code}`
        : selected.title
      : '';

  function close() {
    setOpen(false);
    setEditing(false);
    setQuery('');
    setActive(null);
  }

  // Reset the draft before committing a changed selection, preserving input focus.
  if (context.value !== value || context.disabled !== disabled) {
    setContext({ value, disabled });
    close();
  }

  function choose(code: string) {
    close();
    onChange(code);
  }

  useEffect(() => {
    if (!open) return;
    function closeOutside(event: PointerEvent) {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) {
        setOpen(false);
        setEditing(false);
        setQuery('');
        setActive(null);
      }
    }
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [open]);

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.nativeEvent.isComposing) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      if (!results.length) return;
      const index = results.findIndex((option) => option.code === activeCode);
      const next = !open
        ? event.key === 'ArrowDown'
          ? 0
          : results.length - 1
        : (index + (event.key === 'ArrowDown' ? 1 : -1) + results.length) %
          results.length;
      setActive(results[next]?.code ?? null);
    } else if (event.key === 'Enter' && open) {
      event.preventDefault();
      if (activeCode !== undefined) choose(activeCode);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      close();
    } else if (event.key === 'Tab') {
      close();
    }
  }

  return (
    <div
      ref={rootRef}
      className={`territory-selector${clearable ? '' : ' selector-required'}`}
      onBlur={(event) => {
        if (
          !(event.relatedTarget instanceof Node) ||
          !event.currentTarget.contains(event.relatedTarget)
        )
          close();
      }}
    >
      <div className="selector-input-wrap">
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-expanded={open}
          aria-controls={`${id}-opciones`}
          aria-autocomplete="list"
          aria-describedby={describedBy}
          aria-activedescendant={
            open && activeCode !== undefined
              ? `${id}-opcion-${activeCode}`
              : undefined
          }
          disabled={disabled}
          placeholder={placeholder}
          value={text}
          onFocus={(event) => {
            setOpen(true);
            setActive(value || null);
            event.currentTarget.select();
          }}
          onClick={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setEditing(true);
            setOpen(true);
            setActive(null);
          }}
          onKeyDown={handleKeyDown}
        />
        {clearable && (value || query) && (
          <button
            type="button"
            className="selector-clear"
            aria-label={`Borrar ${label.toLocaleLowerCase('es')}`}
            disabled={disabled}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              if (value) choose('');
              else {
                setQuery('');
                setActive(null);
                setOpen(true);
              }
            }}
          >
            ×
          </button>
        )}
        <button
          type="button"
          className="selector-toggle"
          aria-label={`${open ? 'Cerrar' : 'Mostrar'} opciones de ${label.toLocaleLowerCase('es')}`}
          disabled={disabled}
          tabIndex={-1}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            if (open) close();
            else {
              inputRef.current?.focus();
              setOpen(true);
            }
          }}
        >
          <span aria-hidden="true">⌄</span>
        </button>
      </div>
      {open && !disabled && (
        <ul
          id={`${id}-opciones`}
          className="selector-options"
          role="listbox"
          aria-label={label}
        >
          {results.map((option) => (
            <li
              key={option.code}
              id={`${id}-opcion-${option.code}`}
              role="option"
              aria-selected={option.code === value}
              className={option.code === activeCode ? 'is-active' : ''}
              ref={option.code === activeCode ? scrollActiveOption : undefined}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(option.code)}
            >
              <span className="selector-option-title">{option.title}</span>
              {showCode && <span className="selector-code">{option.code}</span>}
              {optionDetail && <span className="selector-option-detail">{optionDetail(option.code)}</span>}
            </li>
          ))}
          {!results.length && (
            <li className="selector-empty" role="presentation">
              No hay coincidencias
            </li>
          )}
        </ul>
      )}
      <span className="visually-hidden" role="status">
        {open ? `${results.length} resultados disponibles` : ''}
      </span>
    </div>
  );
}
