import { useState, useMemo } from 'react';
import { Form, Button, Row, Col, Table, Alert, Card, Badge, Image } from 'react-bootstrap';
import { Plus, Trash2, Save, Upload, X, MapPin } from 'lucide-react';
import { accountingApi } from '../api/accounting';
import { assetsApi } from '../api/assets';
import { geoApi } from '../api/geo';
import type { Account, JournalEntry } from '../api/accounting';

interface TransactionFormProps {
  accounts: Account[];
  onSuccess: () => void;
}

// 초기 빈 분개 라인
const emptyEntry: JournalEntry = { code: '', amount: 0, description: '' };

export function TransactionForm({ accounts, onSuccess }: TransactionFormProps) {
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [description, setDescription] = useState('');
  
  // 차변(Dr) / 대변(Cr) 상태 관리
  const [debits, setDebits] = useState<JournalEntry[]>([{ ...emptyEntry }]);
  const [credits, setCredits] = useState<JournalEntry[]>([{ ...emptyEntry }]);
  
  // 증빙 자료 (이미지)
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [evidenceUrl, setEvidenceUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  // 위치 정보 (Geo)
  const [locationId, setLocationId] = useState<string | null>(null);
  const [locationText, setLocationText] = useState<string | null>(null);
  const [geoLoading, setGeoLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  // 합계 계산 (Memoization)
  const debitSum = useMemo(() => debits.reduce((sum, item) => sum + Number(item.amount || 0), 0), [debits]);
  const creditSum = useMemo(() => credits.reduce((sum, item) => sum + Number(item.amount || 0), 0), [credits]);
  const isBalanced = Math.abs(debitSum - creditSum) < 0.01; // 부동소수점 오차 고려

  // 입력 핸들러 (동적 리스트용)
  const handleEntryChange = (
    isDebit: boolean,
    index: number,
    field: keyof JournalEntry,
    value: string | number
  ) => {
    const setter = isDebit ? setDebits : setCredits;
    setter(prev => {
      const newList = [...prev];
      newList[index] = { ...newList[index], [field]: value };
      return newList;
    });
  };

  const addRow = (isDebit: boolean) => {
    const setter = isDebit ? setDebits : setCredits;
    setter(prev => [...prev, { ...emptyEntry }]);
  };

  const removeRow = (isDebit: boolean, index: number) => {
    const setter = isDebit ? setDebits : setCredits;
    const list = isDebit ? debits : credits;
    if (list.length > 1) {
      setter(prev => prev.filter((_, i) => i !== index));
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploading(true);
      try {
        const res = await assetsApi.upload(file);
        setEvidenceId(res.data.id);
        setEvidenceUrl(`http://127.0.0.1:8000${res.data.url}`);
      } catch (err) {
        console.error(err);
        setError("Failed to upload image.");
      } finally {
        setUploading(false);
      }
    }
  };

  const removeEvidence = () => {
    setEvidenceId(null);
    setEvidenceUrl(null);
  };

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      return;
    }
    
    setGeoLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { latitude, longitude } = position.coords;
          const res = await geoApi.create(latitude, longitude);
          setLocationId(res.data.id);
          setLocationText(`${latitude.toFixed(4)}, ${longitude.toFixed(4)}`);
        } catch (err) {
          console.error(err);
          setError("Failed to save location data.");
        } finally {
          setGeoLoading(false);
        }
      },
      (err) => {
        console.error(err);
        setError("Failed to retrieve location.");
        setGeoLoading(false);
      }
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 유효성 검사
    if (!description.trim()) {
      setError("Please enter a description.");
      return;
    }
    if (debitSum === 0 || creditSum === 0) {
      setError("Amounts must be greater than 0.");
      return;
    }
    if (!isBalanced) {
      setError("Transaction is not balanced!");
      return;
    }
    // 계정 선택 여부 확인
    if ([...debits, ...credits].some(e => !e.code)) {
      setError("Please select accounts for all entries.");
      return;
    }

    try {
      await accountingApi.createTransaction({
        date,
        description,
        debits,
        credits,
        evidence_id: evidenceId || undefined,
        location_id: locationId || undefined
      });
      
      // 초기화 및 성공 콜백
      setDate(new Date().toISOString().split('T')[0]);
      setDescription('');
      setDebits([{ ...emptyEntry }]);
      setCredits([{ ...emptyEntry }]);
      setEvidenceId(null);
      setEvidenceUrl(null);
      setLocationId(null);
      setLocationText(null);
      
      onSuccess();
      alert("Transaction saved successfully!");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to save transaction.");
    }
  };

  // 계정 선택 옵션 렌더링
  const renderAccountOptions = () => (
    <>
      <option value="">Select Account...</option>
      {accounts.map(acc => (
        <option key={acc.code} value={acc.code}>
          {acc.code} - {acc.name} ({acc.category})
        </option>
      ))}
    </>
  );

  return (
    <Card className="shadow-sm">
      <Card.Header className="bg-white">
        <h5 className="mb-0">New Transaction Entry</h5>
      </Card.Header>
      <Card.Body>
        {error && <Alert variant="danger">{error}</Alert>}
        
        <Form onSubmit={handleSubmit}>
          {/* 1. Header Info */}
          <Row className="mb-4">
            <Col md={4}>
              <Form.Group>
                <Form.Label>Date</Form.Label>
                <Form.Control 
                  type="date" 
                  value={date} 
                  onChange={e => setDate(e.target.value)} 
                  required 
                />
              </Form.Group>
            </Col>
            <Col md={8}>
              <Form.Group>
                <Form.Label>Description (Brief)</Form.Label>
                <Form.Control 
                  type="text" 
                  placeholder="e.g. Lunch at Gangnam" 
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  required 
                />
              </Form.Group>
            </Col>
          </Row>

          {/* Evidence & Location Row */}
          <Row className="mb-4">
            <Col md={6}>
              <Form.Group>
                <Form.Label>Evidence (Receipt)</Form.Label>
                {!evidenceUrl ? (
                  <div className="d-flex align-items-center">
                    <Form.Control 
                      type="file" 
                      accept="image/*"
                      onChange={handleFileUpload}
                      disabled={uploading}
                    />
                    {uploading && <span className="ms-2 text-muted">Uploading...</span>}
                  </div>
                ) : (
                  <div className="position-relative d-inline-block border rounded p-1">
                    <Image src={evidenceUrl} thumbnail style={{ maxHeight: '100px' }} />
                    <Button 
                      variant="danger" 
                      size="sm" 
                      className="position-absolute top-0 start-100 translate-middle rounded-circle p-0"
                      style={{ width: '20px', height: '20px' }}
                      onClick={removeEvidence}
                    >
                      <X size={12} />
                    </Button>
                  </div>
                )}
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group>
                <Form.Label>Location</Form.Label>
                <div className="d-flex align-items-center">
                  {!locationId ? (
                    <Button 
                      variant="outline-secondary" 
                      onClick={handleGetLocation} 
                      disabled={geoLoading}
                    >
                      <MapPin size={18} className="me-2" />
                      {geoLoading ? "Locating..." : "Get Current Location"}
                    </Button>
                  ) : (
                    <div className="d-flex align-items-center text-success border rounded p-2 px-3">
                      <MapPin size={18} className="me-2" />
                      <span className="me-3">{locationText}</span>
                      <Button 
                        variant="link" 
                        className="text-danger p-0 ms-auto" 
                        onClick={() => { setLocationId(null); setLocationText(null); }}
                      >
                        <X size={18} />
                      </Button>
                    </div>
                  )}
                </div>
              </Form.Group>
            </Col>
          </Row>

          {/* 2. Debits (차변) */}
          <h6 className="text-success border-bottom pb-2">Debits (차변) - Where money went</h6>
          <Table borderless size="sm">
            <thead>
              <tr>
                <th style={{width: '40%'}}>Account</th>
                <th style={{width: '30%'}}>Amount</th>
                <th style={{width: '25%'}}>Note (Optional)</th>
                <th style={{width: '5%'}}></th>
              </tr>
            </thead>
            <tbody>
              {debits.map((row, i) => (
                <tr key={i}>
                  <td>
                    <Form.Select 
                      value={row.code} 
                      onChange={e => handleEntryChange(true, i, 'code', e.target.value)}
                      required
                    >
                      {renderAccountOptions()}
                    </Form.Select>
                  </td>
                  <td>
                    <Form.Control 
                      type="number" 
                      min="0" 
                      step="0.01"
                      value={row.amount}
                      onChange={e => handleEntryChange(true, i, 'amount', parseFloat(e.target.value))}
                      required
                    />
                  </td>
                  <td>
                    <Form.Control 
                      type="text" 
                      value={row.description || ''}
                      onChange={e => handleEntryChange(true, i, 'description', e.target.value)}
                    />
                  </td>
                  <td>
                    <Button variant="link" className="text-danger p-0" onClick={() => removeRow(true, i)} disabled={debits.length === 1}>
                      <Trash2 size={18} />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}>
                  <Button variant="outline-success" size="sm" onClick={() => addRow(true)}>
                    <Plus size={16} /> Add Debit Line
                  </Button>
                </td>
              </tr>
            </tfoot>
          </Table>

          {/* 3. Credits (대변) */}
          <h6 className="text-danger border-bottom pb-2 mt-4">Credits (대변) - Source of money</h6>
          <Table borderless size="sm">
            <thead>
              <tr>
                <th style={{width: '40%'}}>Account</th>
                <th style={{width: '30%'}}>Amount</th>
                <th style={{width: '25%'}}>Note (Optional)</th>
                <th style={{width: '5%'}}></th>
              </tr>
            </thead>
            <tbody>
              {credits.map((row, i) => (
                <tr key={i}>
                  <td>
                    <Form.Select 
                      value={row.code} 
                      onChange={e => handleEntryChange(false, i, 'code', e.target.value)}
                      required
                    >
                      {renderAccountOptions()}
                    </Form.Select>
                  </td>
                  <td>
                    <Form.Control 
                      type="number" 
                      min="0" 
                      step="0.01"
                      value={row.amount}
                      onChange={e => handleEntryChange(false, i, 'amount', parseFloat(e.target.value))}
                      required
                    />
                  </td>
                  <td>
                    <Form.Control 
                      type="text" 
                      value={row.description || ''}
                      onChange={e => handleEntryChange(false, i, 'description', e.target.value)}
                    />
                  </td>
                  <td>
                    <Button variant="link" className="text-danger p-0" onClick={() => removeRow(false, i)} disabled={credits.length === 1}>
                      <Trash2 size={18} />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}>
                  <Button variant="outline-danger" size="sm" onClick={() => addRow(false)}>
                    <Plus size={16} /> Add Credit Line
                  </Button>
                </td>
              </tr>
            </tfoot>
          </Table>

          {/* 4. Footer Summary & Action */}
          <Card.Footer className="bg-light mt-3">
            <Row className="align-items-center">
              <Col md={8}>
                <div className="d-flex gap-4">
                  <span className="text-success fw-bold">Total Debit: {debitSum.toLocaleString()}</span>
                  <span className="text-danger fw-bold">Total Credit: {creditSum.toLocaleString()}</span>
                  {isBalanced ? 
                    <Badge bg="success" className="align-self-center">Balanced</Badge> : 
                    <Badge bg="warning" text="dark" className="align-self-center">Difference: {Math.abs(debitSum - creditSum).toLocaleString()}</Badge>
                  }
                </div>
              </Col>
              <Col md={4} className="text-end">
                <Button 
                  type="submit" 
                  variant="primary" 
                  disabled={!isBalanced || debitSum === 0}
                >
                  <Save size={18} className="me-2" /> Save Transaction
                </Button>
              </Col>
            </Row>
          </Card.Footer>
        </Form>
      </Card.Body>
    </Card>
  );
}
