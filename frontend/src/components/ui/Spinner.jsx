const SIZES = {
  sm: 'w-3.5 h-3.5 border-2',
  md: 'w-5 h-5 border-2',
  lg: 'w-8 h-8 border-[3px]',
}

export default function Spinner({ size = 'md', className = '' }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={
        `${SIZES[size]} inline-block border-current border-t-transparent ` +
        `rounded-full animate-spin ${className}`
      }
    />
  )
}
