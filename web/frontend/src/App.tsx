import { useState, useEffect } from 'react'
import { Container, Nav, Navbar, Tab, Badge, Card, Spinner, Button, Table } from 'react-bootstrap'
import { Wallet, History, PlusCircle, LayoutDashboard } from 'lucide-react'
import { accountingApi } from './api/accounting'
import type { Account, TransactionResponse } from './api/accounting'
import { TransactionForm } from './components/TransactionForm'
import { TransactionList } from './components/TransactionList'

function App() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [transactions, setTransactions] = useState<TransactionResponse[]>([])
  const [loading, setLoading] = useState(true)

  // 데이터 로딩
  const fetchData = async () => {
    try {
      setLoading(true)
      const [accRes, txRes] = await Promise.all([
        accountingApi.getAccounts(),
        accountingApi.getTransactions()
      ])
      setAccounts(accRes.data)
      setTransactions(txRes.data)
    } catch (error) {
      console.error("Failed to fetch data:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  return (
    <div className="bg-light min-vh-100">
      <Navbar bg="dark" variant="dark" expand="lg" className="mb-4 shadow">
        <Container>
          <Navbar.Brand href="#home">
            <LayoutDashboard className="me-2" />
            Utility Belt (CACHE)
          </Navbar.Brand>
        </Container>
      </Navbar>

      <Container>
        {loading && (
          <div className="text-center my-5">
            <Spinner animation="border" role="status">
              <span className="visually-hidden">Loading...</span>
            </Spinner>
          </div>
        )}

        {!loading && (
          <Tab.Container defaultActiveKey="dashboard">
            <Nav variant="pills" className="mb-4 justify-content-center">
              <Nav.Item>
                <Nav.Link eventKey="dashboard">
                  <LayoutDashboard size={18} className="me-2" /> Dashboard
                </Nav.Link>
              </Nav.Item>
              <Nav.Item>
                <Nav.Link eventKey="accounts">
                  <Wallet size={18} className="me-2" /> Accounts
                </Nav.Link>
              </Nav.Item>
              <Nav.Item>
                <Nav.Link eventKey="transactions">
                  <History size={18} className="me-2" /> Transactions
                </Nav.Link>
              </Nav.Item>
              <Nav.Item>
                <Nav.Link eventKey="new_tx" className="text-primary">
                  <PlusCircle size={18} className="me-2" /> New Entry
                </Nav.Link>
              </Nav.Item>
            </Nav>

            <Tab.Content className="bg-white p-4 rounded shadow-sm">
              {/* 대시보드 */}
              <Tab.Pane eventKey="dashboard">
                <h3>Financial Overview</h3>
                <p className="text-muted">Welcome to your double-entry ledger.</p>
                <div className="row mt-4">
                  <div className="col-md-4">
                    <Card className="text-center border-0 bg-primary text-white">
                      <Card.Body>
                        <Card.Title>Total Accounts</Card.Title>
                        <h2>{accounts.length}</h2>
                      </Card.Body>
                    </Card>
                  </div>
                  <div className="col-md-4">
                    <Card className="text-center border-0 bg-success text-white">
                      <Card.Body>
                        <Card.Title>Recent Transactions</Card.Title>
                        <h2>{transactions.length}</h2>
                      </Card.Body>
                    </Card>
                  </div>
                </div>
              </Tab.Pane>

              {/* 계정 목록 */}
              <Tab.Pane eventKey="accounts">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h3>Chart of Accounts</h3>
                  <Button variant="outline-primary" size="sm" onClick={fetchData}>Refresh</Button>
                </div>
                <Table responsive hover>
                  <thead className="table-light">
                    <tr>
                      <th>Code</th>
                      <th>Name</th>
                      <th>Category</th>
                      <th>Side</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map(acc => (
                      <tr key={acc.code}>
                        <td><code>{acc.code}</code></td>
                        <td className="fw-bold">{acc.name}</td>
                        <td><Badge bg="secondary">{acc.category}</Badge></td>
                        <td>{acc.side}</td>
                        <td className="text-muted small">{acc.description}</td>
                      </tr>
                    ))}
                    {accounts.length === 0 && <tr><td colSpan={5} className="text-center py-4">No accounts found.</td></tr>}
                  </tbody>
                </Table>
              </Tab.Pane>

              {/* 거래 내역 (교체됨) */}
              <Tab.Pane eventKey="transactions">
                <TransactionList transactions={transactions} onRefresh={fetchData} />
              </Tab.Pane>

              {/* 새 거래 작성 */}
              <Tab.Pane eventKey="new_tx">
                <TransactionForm 
                  accounts={accounts} 
                  onSuccess={fetchData} 
                />
              </Tab.Pane>
            </Tab.Content>
          </Tab.Container>
        )}
      </Container>
    </div>
  )
}

export default App