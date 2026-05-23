import './report.css'

export default function ActionBar({
  reportId, isEditing, isDirty, isStreaming,
  onToggleEdit, onSave, onCancel, onDownload,
}) {
  return (
    <div className="action-bar">
      {!isEditing && !isStreaming && reportId ? (
        <button onClick={onToggleEdit}>Edit letter</button>
      ) : null}

      {isEditing ? (
        <>
          <button className="danger" onClick={onCancel}>Cancel</button>
          <button className="primary" onClick={onSave} disabled={!isDirty}>
            Save changes
          </button>
        </>
      ) : null}

      {!isEditing && reportId ? (
        <button className="primary" onClick={onDownload}>Download PDF</button>
      ) : null}
    </div>
  )
}
