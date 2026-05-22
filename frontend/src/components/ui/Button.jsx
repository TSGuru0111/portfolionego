import Spinner from './Spinner.jsx'

const VARIANTS = {
  primary:
    'bg-primary-600 hover:bg-primary-700 text-white font-semibold ' +
    'disabled:opacity-50 disabled:cursor-not-allowed',
  secondary:
    'border border-slate-300 hover:border-primary-500 ' +
    'text-slate-700 hover:text-primary-600 font-medium bg-white',
  ghost:
    'text-slate-500 hover:text-slate-700 font-medium ' +
    'hover:bg-slate-100',
  danger:
    'bg-red-50 hover:bg-red-100 text-red-600 font-medium',
}

const SIZES = {
  sm: 'px-3 py-1.5 text-sm rounded-lg',
  md: 'px-4 py-2 text-sm rounded-lg',
  lg: 'px-6 py-2.5 text-base rounded-lg',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className = '',
  ...rest
}) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={
        `${VARIANTS[variant]} ${SIZES[size]} ` +
        'transition-colors duration-200 inline-flex items-center justify-center gap-2 ' +
        className
      }
    >
      {loading ? <Spinner size="sm" /> : null}
      {children}
    </button>
  )
}
