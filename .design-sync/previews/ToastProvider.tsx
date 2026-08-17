import { useEffect } from 'react'
import { Button, Card, ToastProvider, useToast } from 'frontend'

// Pushes one of each kind on mount so the card shows a populated toaster.
// Toasts auto-dismiss after 3.5s (6s for errors), which is well after the
// preview is captured.
function Emit() {
  const toast = useToast()
  useEffect(() => {
    toast.success('Submissions synced — 128 filings ingested.')
    toast.info('Recomputing derived metrics…')
    toast.error('SEC rate limit reached — retrying in 10s.')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return null
}

function Triggers() {
  const toast = useToast()
  return (
    <Card>
      <div className="card-pad row gap-2 wrap">
        <Button onClick={() => toast.success('Saved.')}>Success</Button>
        <Button onClick={() => toast.info('Working…')}>Info</Button>
        <Button variant="danger" onClick={() => toast.error('Request failed.')}>
          Error
        </Button>
      </div>
    </Card>
  )
}

// `.toaster` is position:fixed bottom-right, so the preview reserves real
// height — otherwise the card collapses to the trigger row and the stack is
// captured clipped.
export const AllThreeKinds = () => (
  <ToastProvider>
    <div style={{ minHeight: 460 }}>
      <Triggers />
    </div>
    <Emit />
  </ToastProvider>
)
