export default function Card({ children, className = '', hoverable = false, ...rest }) {
  const base =
    'bg-white border border-slate-200 rounded-xl p-6 ' +
    'transition-all duration-200'
  const hover = hoverable
    ? ' hover:border-primary-300 hover:shadow-md cursor-pointer'
    : ' shadow-sm'
  return (
    <div {...rest} className={base + hover + ' ' + className}>
      {children}
    </div>
  )
}
