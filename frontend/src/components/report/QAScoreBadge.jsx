import Badge from '../ui/Badge.jsx'

export default function QAScoreBadge({ score }) {
  if (score == null) return null
  const tone = score >= 8 ? 'success' : score >= 7 ? 'gold' : 'danger'
  return <Badge tone={tone}>QA {score}/10</Badge>
}
