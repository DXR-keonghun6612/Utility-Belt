import { useState } from 'react';
import { Table, Badge, Button, Modal, Form, Image, Row, Col } from 'react-bootstrap';
import { Edit2, Save, X, MapPin, Upload } from 'lucide-react';
import type { TransactionResponse } from '../api/accounting';
import { accountingApi } from '../api/accounting';
import { assetsApi } from '../api/assets';
import { geoApi } from '../api/geo';

interface TransactionListProps {
  transactions: TransactionResponse[];
  onRefresh: () => void;
}

export function TransactionList({ transactions, onRefresh }: TransactionListProps) {
  const [selectedTx, setSelectedTx] = useState<TransactionResponse | null>(null);
  const [showModal, setShowModal] = useState(false);

  // Edit Form State
  const [description, setDescription] = useState('');
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [evidenceUrl, setEvidenceUrl] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [locationText, setLocationText] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [geoLoading, setGeoLoading] = useState(false);

  const handleEditClick = (tx: TransactionResponse) => {
    setSelectedTx(tx);
    setDescription(tx.description);
    setEvidenceId(tx.evidence_id || null);
    // 이미지 URL은 별도 API 호출이 필요할 수도 있지만, 여기서는 ID만 있다고 가정하고
    // 기존 이미지를 보여주려면 백엔드에서 URL을 주는 것이 좋음.
    // 현재 구조상 ID만 있으므로, 수정 시 새로 올리는 것 위주로 구현.
    setEvidenceUrl(tx.evidence_id ? `http://127.0.0.1:8000/assets/${tx.evidence_id}` : null);
    
    setLocationId(tx.location_id || null);
    setLocationText(tx.location_id ? "Location ID: " + tx.location_id.substring(0, 8) : null);
    
    setShowModal(true);
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
        console.error("Upload failed", err);
        alert("Failed to upload image");
      } finally {
        setUploading(false);
      }
    }
  };

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported");
      return;
    }
    setGeoLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const { latitude, longitude } = pos.coords;
          const res = await geoApi.create(latitude, longitude);
          setLocationId(res.data.id);
          setLocationText(`${latitude.toFixed(4)}, ${longitude.toFixed(4)}`);
        } catch (err) {
          console.error("Geo save failed", err);
          alert("Failed to save location");
        } finally {
          setGeoLoading(false);
        }
      },
      (err) => {
        console.error("Geo error", err);
        alert("Failed to retrieve location");
        setGeoLoading(false);
      }
    );
  };

  const handleSave = async () => {
    if (!selectedTx) return;
    try {
      await accountingApi.updateTransaction(selectedTx.id, {
        description,
        evidence_id: evidenceId || undefined,
        location_id: locationId || undefined
      });
      setShowModal(false);
      onRefresh(); // 목록 새로고침
    } catch (err) {
      console.error("Update failed", err);
      alert("Failed to update transaction");
    }
  };

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3>Transaction History</h3>
        <Button variant="outline-primary" size="sm" onClick={onRefresh}>Refresh</Button>
      </div>
      <Table responsive hover>
        <thead className="table-light">
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Details</th>
            <th>Evid/Loc</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map(tx => (
            <tr key={tx.id}>
              <td className="text-nowrap">{tx.date}</td>
              <td className="fw-bold">{tx.description}</td>
              <td>
                <div className="small">
                  {tx.debits.map((e, i) => <div key={i} className="text-success">Dr {e.account_code}: {e.amount}</div>)}
                  {tx.credits.map((e, i) => <div key={i} className="text-danger">Cr {e.account_code}: {e.amount}</div>)}
                </div>
              </td>
              <td>
                <div className="d-flex gap-1">
                  {tx.evidence_id && <Badge bg="info">Img</Badge>}
                  {tx.location_id && <Badge bg="secondary">Loc</Badge>}
                </div>
              </td>
              <td>
                {tx.is_balanced ? 
                  <Badge bg="success">Balanced</Badge> : 
                  <Badge bg="danger">Error</Badge>
                }
              </td>
              <td>
                <Button variant="link" size="sm" onClick={() => handleEditClick(tx)}>
                  <Edit2 size={16} />
                </Button>
              </td>
            </tr>
          ))}
          {transactions.length === 0 && <tr><td colSpan={6} className="text-center py-4">No transactions recorded.</td></tr>}
        </tbody>
      </Table>

      {/* Edit Modal */}
      <Modal show={showModal} onHide={() => setShowModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Edit Transaction Details</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Description</Form.Label>
              <Form.Control 
                type="text" 
                value={description} 
                onChange={(e) => setDescription(e.target.value)} 
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Evidence</Form.Label>
              <div>
                {!evidenceUrl ? (
                  <div className="d-flex align-items-center">
                    <Form.Control type="file" onChange={handleFileUpload} disabled={uploading} size="sm" />
                    {uploading && <span className="ms-2 small text-muted">Uploading...</span>}
                  </div>
                ) : (
                  <div className="position-relative d-inline-block border rounded p-1">
                    <Image src={evidenceUrl} thumbnail style={{ maxHeight: '100px' }} />
                    <Button 
                      variant="danger" size="sm" 
                      className="position-absolute top-0 start-100 translate-middle p-0 rounded-circle"
                      style={{width: '20px', height: '20px'}}
                      onClick={() => { setEvidenceId(null); setEvidenceUrl(null); }}
                    >
                      <X size={12} />
                    </Button>
                  </div>
                )}
              </div>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Location</Form.Label>
              <div>
                {!locationId ? (
                  <Button variant="outline-secondary" size="sm" onClick={handleGetLocation} disabled={geoLoading}>
                    <MapPin size={14} className="me-1" /> Get Current Location
                  </Button>
                ) : (
                  <div className="d-flex align-items-center border rounded p-2">
                    <MapPin size={16} className="me-2 text-success" />
                    <span className="small me-2">{locationText}</span>
                    <Button variant="link" size="sm" className="p-0 text-danger ms-auto" onClick={() => { setLocationId(null); setLocationText(null); }}>
                      <X size={16} />
                    </Button>
                  </div>
                )}
              </div>
            </Form.Group>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
          <Button variant="primary" onClick={handleSave}>
            <Save size={16} className="me-2" /> Save Changes
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
}
