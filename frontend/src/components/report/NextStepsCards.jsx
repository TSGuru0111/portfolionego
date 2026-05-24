import './report.css'

export default function NextStepsCards({ items }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <h3 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 600 }}>What's Next</h3>
      <div className="next-cards">
        {items.map((it, i) => (
          <div key={i} className="next-card">
            <div className="icon">{it.icon || '•'}</div>
            <div className="title">{it.title}</div>
            <div className="body">{it.body}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
