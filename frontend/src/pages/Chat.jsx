import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, MessageSquare, Upload, FileText,
  Bot, User, FolderOpen, Mic, MicOff,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import {
  getCollections, sendChat,
  createWorkspace, uploadWorkspaceDocuments, deleteWorkspace,
} from '../api.js';
import { useConversation } from '../context/ConversationContext';
import MessageActions from '../components/MessageActions';

export default function Chat({ addToast }) {
  const {
    sidebarSelection,
    loadingMessages,
    notifyNewConversation,
    refreshConversations,
    startNewChat,
  } = useConversation();

  const [mode, setMode]                 = useState('collection');
  const [collections, setCollections]   = useState([]);
  const [selectedCollection, setSelectedCollection] = useState('');
  const [workspaceId, setWorkspaceId]   = useState(null);
  const [workspaceFiles, setWorkspaceFiles] = useState([]);
  const [uploading, setUploading]       = useState(false);
  const [messages, setMessages]         = useState([]);
  const [currentConvId, setCurrentConvId] = useState(null);
  const [input, setInput]               = useState('');
  const [sending, setSending]           = useState(false);
  const [isListening, setIsListening]   = useState(false);

  const messagesEnd  = useRef(null);
  const textareaRef  = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  // Load collections
  useEffect(() => {
    if (!localStorage.getItem('token')) return;
    getCollections()
      .then((cols) => { setCollections(cols); if (cols.length) setSelectedCollection(cols[0]); })
      .catch(() => addToast('Failed to load collections', 'error'));
  }, [addToast]);

  // Sync when sidebar makes an atomic selection (New Chat or click past conversation).
  // mountedRef skips only the very first render — after that every sidebarSelection
  // change (ts always increments) reliably updates the chat view.
  const mountedRef = useRef(false);
  useEffect(() => {
    if (!mountedRef.current) { mountedRef.current = true; return; }
    setMessages(sidebarSelection.messages);
    setCurrentConvId(sidebarSelection.id);
    setInput('');
  }, [sidebarSelection]);

  // Scroll to bottom
  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // Auto-resize textarea
  const handleInputChange = (e) => {
    setInput(e.target.value);
    const ta = textareaRef.current;
    if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 150) + 'px'; }
  };

  // ── Voice Input ────────────────────────────────────────────────────
  const startVoice = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { addToast('Voice input requires Chrome or Edge', 'error'); return; }

    const rec = new SR();
    rec.continuous     = false;
    rec.interimResults = true;
    rec.lang           = 'en-IN';

    rec.onresult = (e) => {
      const transcript = Array.from(e.results).map((r) => r[0].transcript).join('');
      setInput(transcript);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
      }
    };
    rec.onend   = () => setIsListening(false);
    rec.onerror = (e) => {
      setIsListening(false);
      if (e.error !== 'no-speech') addToast('Voice error: ' + e.error, 'error');
    };

    rec.start();
    recognitionRef.current = rec;
    setIsListening(true);
  }, [addToast]);

  const stopVoice  = useCallback(() => { recognitionRef.current?.stop(); setIsListening(false); }, []);
  const toggleVoice = () => (isListening ? stopVoice() : startVoice());

  // ── Mode switch ────────────────────────────────────────────────────
  const switchMode = useCallback(async (newMode) => {
    if (newMode === mode) return;
    setMessages([]);
    setInput('');
    setCurrentConvId(null);
    startNewChat();
    if (mode === 'workspace' && workspaceId) {
      try { await deleteWorkspace(workspaceId); } catch {}
      setWorkspaceId(null);
      setWorkspaceFiles([]);
    }
    setMode(newMode);
  }, [mode, workspaceId, startNewChat]);

  // ── Workspace upload ───────────────────────────────────────────────
  const handleWorkspaceUpload = async (files) => {
    if (!files.length) return;
    setUploading(true);
    try {
      let wsId = workspaceId;
      if (!wsId) { const res = await createWorkspace(); wsId = res.workspace_id; setWorkspaceId(wsId); }
      const res = await uploadWorkspaceDocuments(wsId, files);
      setWorkspaceFiles((prev) => [...prev, ...res.ingested_files.filter((f) => !prev.includes(f))]);
      addToast('Uploaded ' + res.ingested_files.length + ' file(s) to workspace', 'success');
    } catch {
      addToast('Failed to upload workspace files', 'error');
    } finally {
      setUploading(false);
    }
  };

  // ── Send ───────────────────────────────────────────────────────────
  const handleSend = async () => {
    const q = input.trim();
    if (!q || sending) return;
    if (mode === 'collection' && !selectedCollection) { addToast('Select a collection first', 'error'); return; }
    if (mode === 'workspace'  && !workspaceId)        { addToast('Upload documents first', 'error'); return; }

    setMessages((prev) => [...prev, { role: 'user', content: q }]);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setSending(true);

    try {
      const res = await sendChat({
        collection:     mode === 'collection' ? selectedCollection : null,
        question:       q,
        workspaceId:    mode === 'workspace'  ? workspaceId       : null,
        conversationId: currentConvId,
      });
      setMessages((prev) => [...prev, { role: 'assistant', content: res.answer, sources: res.sources }]);

      if (!currentConvId && res.conversation_id) {
        setCurrentConvId(res.conversation_id);
        notifyNewConversation(); // refreshes sidebar list only
      } else {
        refreshConversations();
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Something went wrong';
      setMessages((prev) => [...prev, { role: 'assistant', content: '⚠️ ' + detail }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const voiceSupported =
    typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  const collectionLabel = selectedCollection
    ? selectedCollection.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
    : '';

  if (loadingMessages) {
    return (
      <div className="chat-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="chat-container">
      {/* Toolbar */}
      <div className="chat-toolbar">
        <div className="mode-toggle">
          <button className={mode === 'collection' ? 'active' : ''} onClick={() => switchMode('collection')}>
            <FolderOpen size={13} /> Collection
          </button>
          <button className={mode === 'workspace' ? 'active' : ''} onClick={() => switchMode('workspace')}>
            <Upload size={13} /> Workspace
          </button>
        </div>

        {mode === 'collection' && (
          <select
            value={selectedCollection}
            onChange={(e) => { setSelectedCollection(e.target.value); setMessages([]); setCurrentConvId(null); startNewChat(); }}
          >
            {collections.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}</option>
            ))}
          </select>
        )}

        {mode === 'workspace' && (
          <>
            <button className="btn btn-secondary btn-sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
              <Upload size={13} /> {uploading ? 'Uploading…' : 'Upload Files'}
            </button>
            <input ref={fileInputRef} type="file" multiple hidden
              onChange={(e) => { handleWorkspaceUpload(Array.from(e.target.files)); e.target.value = ''; }}
            />
            {workspaceId && (
              <div className="workspace-banner">
                Workspace active <code>{workspaceId.slice(0, 8)}…</code>
              </div>
            )}
          </>
        )}
      </div>

      {/* Workspace file chips */}
      {mode === 'workspace' && workspaceFiles.length > 0 && (
        <div className="workspace-files-bar">
          {workspaceFiles.map((f) => (
            <span key={f} className="workspace-file-chip"><FileText size={11} /> {f}</span>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon"><MessageSquare size={26} /></div>
            <h3>{mode === 'collection' ? 'Ask anything about your documents' : 'Upload files, then ask questions'}</h3>
            <p>
              {mode === 'collection'
                ? `Querying "${collectionLabel}". You can also click the mic to speak your question.`
                : 'Click "Upload Files" to add documents to your workspace, then start chatting.'}
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === 'user' ? <User size={15} /> : <Bot size={15} />}
            </div>
            <div className="message-body">
              <div className="message-bubble">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
              {msg.sources && msg.sources.length > 0 && (
                <div className="message-sources">
                  <details>
                    <summary>{msg.sources.length} source{msg.sources.length !== 1 ? 's' : ''} referenced</summary>
                    <div className="source-list">
                      {msg.sources.map((s, j) => (
                        <span key={j} className="source-chip">
                          {s.source || s.id} ({(s.score * 100).toFixed(0)}%)
                        </span>
                      ))}
                    </div>
                  </details>
                </div>
              )}
              {msg.role === 'assistant' && (
                <MessageActions
                  key={`actions-${i}`}
                  question={messages[i - 1]?.content || ''}
                  answer={msg.content}
                  sources={msg.sources}
                  collection={mode === 'collection' ? selectedCollection : null}
                  workspaceId={mode === 'workspace' ? workspaceId : null}
                  conversationId={currentConvId}
                />
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="message assistant">
            <div className="message-avatar"><Bot size={15} /></div>
            <div className="message-body">
              <div className="message-bubble">
                <div className="loading-dots"><span /><span /><span /></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEnd} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? 'Listening… speak now' : 'Type your question… (Enter to send, Shift+Enter for new line)'}
            rows={1}
            disabled={sending || isListening}
          />
          <div className="input-actions">
            {voiceSupported && (
              <button
                className={`mic-btn${isListening ? ' listening' : ''}`}
                onClick={toggleVoice}
                title={isListening ? 'Stop listening' : 'Voice input'}
                disabled={sending}
              >
                {isListening ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
            )}
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={sending || !input.trim()}
              title="Send (Enter)"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
        {isListening && <div className="voice-hint">🎤 Speak now — click mic again to stop and send</div>}
      </div>
    </div>
  );
}
