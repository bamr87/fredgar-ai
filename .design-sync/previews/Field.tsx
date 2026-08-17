import { Field } from 'frontend'

export const TextInput = () => (
  <div className="col gap-4" style={{ maxWidth: 420 }}>
    <Field label="SEC contact email" hint="SEC requires a contact address in the User-Agent header.">
      <input className="input" defaultValue="amr.abdel@gmail.com" />
    </Field>
    <Field label="Admin token" hint="Stored locally; required for sync and write actions.">
      <input className="input" type="password" defaultValue="a1b2c3d4e5f6" />
    </Field>
  </div>
)

export const SelectAndTextarea = () => (
  <div className="col gap-4" style={{ maxWidth: 420 }}>
    <Field label="Statement type">
      <select className="select" defaultValue="income">
        <option value="income">Income statement</option>
        <option value="balance">Balance sheet</option>
        <option value="cash">Cash flow</option>
      </select>
    </Field>
    <Field label="Peer group notes" hint="Optional — shown on the group detail page.">
      <textarea className="textarea" rows={3} defaultValue="Mega-cap technology issuers, rebalanced annually." />
    </Field>
  </div>
)

export const NoLabel = () => (
  <div style={{ maxWidth: 420 }}>
    <Field hint="Searches company name, ticker, and CIK.">
      <input className="input" placeholder="Filter companies…" />
    </Field>
  </div>
)
