import './report.css'

export default function MarketContextGrid({ cards }) {
  if (!cards || cards.length === 0) return null
  return (
    <div className="market-card">
      <h3>Market Context</h3>
      <div className="market-grid">
        {cards.map((c, i) => (
          <div key={i} className="market-card-inner">
            <h4>{c.title}</h4>
            <p>{c.body}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
