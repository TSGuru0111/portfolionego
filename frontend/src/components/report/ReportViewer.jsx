export default function ReportViewer({ reportText, isStreaming }) {
  if (!reportText && !isStreaming) {
    return (
      <div className="border border-dashed border-slate-200 rounded-xl p-12 text-center text-sm text-slate-400">
        Click <strong className="text-slate-600">Generate Report</strong> to begin.
      </div>
    )
  }

  const paragraphs = reportText.split(/\n{2,}/)
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-8 max-w-3xl mx-auto font-serif leading-relaxed text-slate-800">
      {paragraphs.map((para, i) => (
        <p key={i} className="mb-4 text-[15px] leading-8 whitespace-pre-wrap">
          {para}
        </p>
      ))}
      {isStreaming && (
        <span className="inline-block w-0.5 h-5 bg-primary-500 animate-pulse ml-0.5" />
      )}
    </div>
  )
}
