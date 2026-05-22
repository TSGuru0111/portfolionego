import { Link } from 'react-router-dom'

import Badge from '../ui/Badge.jsx'
import Card from '../ui/Card.jsx'
import { formatCr, formatDateIN } from '../../utils/formatters.js'
import { RISK_LABELS } from '../../utils/constants.js'

export default function ClientCard({ client }) {
  const risk = RISK_LABELS[client.risk_profile] || RISK_LABELS.moderate
  return (
    <Link to={`/clients/${client.id}`}>
      <Card hoverable className="h-full">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              {client.name}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Client since {formatDateIN(client.client_since)}
            </p>
          </div>
          <Badge tone={client.language_pref === 'hindi' ? 'gold' : 'primary'}>
            {client.language_pref === 'hindi' ? 'HI' : 'EN'}
          </Badge>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">AUM</div>
            <div className="text-lg font-semibold text-slate-900">
              {formatCr(client.aum_cr)}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Risk</div>
            <Badge className={risk.color}>{risk.label}</Badge>
          </div>
        </div>
      </Card>
    </Link>
  )
}
