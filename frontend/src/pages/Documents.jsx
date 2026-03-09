import { useState, useEffect, useRef, useCallback } from 'react';
import { FileText, Upload, Trash2, RefreshCw, AlertCircle, FolderOpen } from 'lucide-react';
import { getCollections, getDocuments, uploadDocuments, deleteDocument } from '../api.js';
import { useAuth } from '../context/AuthContext.jsx';

export default function Documents({ addToast }) {
  const { isAdmin } = useAuth();

  const [collections, setCollections] = useState([]);
  const [selected, setSelected]       = useState('');
  const [docs, setDocs]               = useState([]);
  const [loading, setLoading]         = useState(false);
  const [uploading, setUploading]     = useState(false);
  const [dragover, setDragover]       = useState(false);

  const fileRef = useRef(null);

  useEffect(() => {
    if (!localStorage.getItem('token')) return;
    getCollections()
      .then((cols) => { setCollections(cols); if (cols.length) setSelected(cols[0]); })
      .catch(() => addToast('Failed to load collections', 'error'));
  }, [addToast]);

  const fetchDocs = useCallback(async () => {
    if (!selected) return;
    setLoading(true);
    try {
      const list = await getDocuments(selected);
      setDocs(list);
    } catch {
      addToast('Failed to load documents', 'error');
    } finally {
      setLoading(false);
    }
  }, [selected, addToast]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const handleUpload = async (files) => {
    if (!files.length || !selected) return;
    setUploading(true);
    try {
      const res = await uploadDocuments(selected, files);
      addToast('Uploaded ' + res.ingested_files.length + ' file(s) successfully', 'success');
      fetchDocs();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Upload failed', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docName) => {
    if (!window.confirm(`Delete "${docName}" from ${selected.replace(/_/g, ' ')}?`)) return;
    try {
      await deleteDocument(docName, selected);
      addToast('Deleted ' + docName, 'success');
      fetchDocs();
    } catch {
      addToast('Delete failed', 'error');
    }
  };

  const onDrop = (e) => { e.preventDefault(); setDragover(false); handleUpload(Array.from(e.dataTransfer.files)); };

  const collectionLabel = selected
    ? selected.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
    : '';

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Documents</h2>
          <p>Manage documents across your knowledge base collections</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={fetchDocs} disabled={loading}>
          <RefreshCw size={13} style={loading ? { animation: 'spin 0.6s linear infinite' } : {}} />
          Refresh
        </button>
      </div>

      <div className="docs-page">
        <div className="docs-toolbar">
          <FolderOpen size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {collections.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}</option>
            ))}
          </select>
          <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
            {loading ? 'Loading…' : `${docs.length} document${docs.length !== 1 ? 's' : ''}`}
          </span>
        </div>

        {isAdmin && (
          <div
            className={`upload-zone${dragover ? ' dragover' : ''}`}
            onClick={() => !uploading && fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
            onDragLeave={() => setDragover(false)}
            onDrop={onDrop}
          >
            <Upload />
            <p>{uploading ? 'Uploading, please wait…' : 'Click or drag files here to upload'}</p>
            <span>PDF, DOCX, TXT and more — parsed by LlamaParse</span>
            <input ref={fileRef} type="file" multiple hidden
              onChange={(e) => { handleUpload(Array.from(e.target.files)); e.target.value = ''; }}
            />
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            <p style={{ fontSize: 13 }}>Loading documents…</p>
          </div>
        ) : docs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <AlertCircle size={36} style={{ marginBottom: 12, opacity: 0.3, color: 'var(--text-muted)' }} />
            <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-2)' }}>
              No documents in "{collectionLabel}"
            </p>
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 4 }}>
              {isAdmin ? 'Upload files above to get started.' : 'Ask an admin to upload documents.'}
            </p>
          </div>
        ) : (
          <div className="docs-list">
            {docs.map((doc) => (
              <div className="doc-row" key={doc}>
                <FileText />
                <span className="doc-row-name" title={doc}>{doc}</span>
                {isAdmin && (
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(doc)}>
                    <Trash2 size={12} /> Delete
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
