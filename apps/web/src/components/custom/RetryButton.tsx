import type { ButtonHTMLAttributes } from 'react';

export function RetryButton({
  children,
  loading = false,
  disabled,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button
      {...props}
      type="button"
      className={`retry-button ${className}`.trim()}
      disabled={disabled || loading}
      aria-busy={loading}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>{loading ? 'Reintentando…' : children}</span>
    </button>
  );
}
