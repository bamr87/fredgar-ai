import { Card, Pager } from 'frontend'

export const FirstPage = () => (
  <Card>
    <Pager page={1} count={1284} pageSize={25} onPage={() => {}} />
  </Card>
)

export const MiddlePage = () => (
  <Card>
    <Pager page={7} count={1284} pageSize={25} onPage={() => {}} />
  </Card>
)

export const LastPage = () => (
  <Card>
    <Pager page={52} count={1284} pageSize={25} onPage={() => {}} />
  </Card>
)

export const SinglePage = () => (
  <Card>
    <Pager page={1} count={12} pageSize={25} onPage={() => {}} />
  </Card>
)
