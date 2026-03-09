import { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  MessageSquare, FileText, LogOut,
  Plus, Trash2, Pencil, Check, X, MessageCircle,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useConversation } from '../context/ConversationContext';

function groupByDate(conversations) {
  const now       = new Date();
  const today     = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  const week      = new Date(today); week.setDate(today.getDate() - 7);
  const groups    = { Today: [], Yesterday: [], 'This Week': [], Earlier: [] };

  for (const c of conversations) {
    const d   = new Date(c.updated_at);
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    if (day >= today)          groups['Today'].push(c);
    else if (day >= yesterday) groups['Yesterday'].push(c);
    else if (d >= week)        groups['This Week'].push(c);
    else                       groups['Earlier'].push(c);
  }
  return groups;
}

function ConversationItem({ conv, isActive, onSelect, onDelete, onRename }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle]     = useState(conv.title);
  const inputRef              = useRef(null);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const saveRename = () => {
    const trimmed = title.trim();
    if (trimmed && trimmed !== conv.title) onRename(conv.id, trimmed);
    else setTitle(conv.title);
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter')  { e.preventDefault(); saveRename(); }
    if (e.key === 'Escape') { setTitle(conv.title); setEditing(false); }
  };

  return (
    <div
      className={`conv-item${isActive ? ' active' : ''}`}
      onClick={() => !editing && onSelect(conv.id)}
    >
      <div className="conv-item-icon"><MessageCircle size={13} /></div>

      {editing ? (
        <input
          ref={inputRef}
          className="conv-item-input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={saveRename}
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <span className="conv-item-title" title={conv.title}>{conv.title}</span>
      )}

      <div className="conv-item-actions" onClick={(e) => e.stopPropagation()}>
        {editing ? (
          <>
            <button className="conv-action-btn" onClick={saveRename} title="Save"><Check size={12} /></button>
            <button className="conv-action-btn" onClick={() => { setTitle(conv.title); setEditing(false); }} title="Cancel"><X size={12} /></button>
          </>
        ) : (
          <>
            <button className="conv-action-btn" onClick={() => setEditing(true)} title="Rename"><Pencil size={12} /></button>
            <button className="conv-action-btn danger" onClick={() => onDelete(conv.id)} title="Delete"><Trash2 size={12} /></button>
          </>
        )}
      </div>
    </div>
  );
}

export default function Sidebar() {
  const { user, logout } = useAuth();
  const {
    conversations,
    sidebarSelection,
    selectConversation,
    startNewChat,
    removeConversation,
    updateTitle,
  } = useConversation();
  const navigate = useNavigate();

  const initials = (user?.username || 'U').slice(0, 2).toUpperCase();

  const handleNewChat = () => { startNewChat(); navigate('/chat'); };
  const handleSelect  = (id) => { selectConversation(id); navigate('/chat'); };
  const groups = groupByDate(conversations);

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <h1>
          <img src="/logo.png" alt="Pon Pure" className="brand-logo" />
          Intellidoc
        </h1>
        <span>Chemical Document Intelligence</span>
      </div>

      {/* New Chat */}
      <button className="new-chat-btn" onClick={handleNewChat}>
        <Plus size={15} /> New Chat
      </button>

      {/* Nav links */}
      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Navigation</div>
        <NavLink to="/chat"      className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}>
          <MessageSquare size={16} /> Chat
        </NavLink>
        <NavLink to="/documents" className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}>
          <FileText size={16} /> Documents
        </NavLink>
      </nav>

      {/* Conversation history */}
      <div className="sidebar-conversations">
        <div className="conv-divider" />
        <div className="sidebar-section-label">Recent Chats</div>

        {conversations.length === 0 ? (
          <div className="conv-empty">No conversations yet.<br />Start a new chat above.</div>
        ) : (
          Object.entries(groups).map(([label, items]) =>
            items.length > 0 ? (
              <div key={label}>
                <div className="conv-group-label">{label}</div>
                {items.map((conv) => (
                  <ConversationItem
                    key={conv.id}
                    conv={conv}
                    isActive={conv.id === sidebarSelection.id}
                    onSelect={handleSelect}
                    onDelete={removeConversation}
                    onRename={updateTitle}
                  />
                ))}
              </div>
            ) : null
          )
        )}
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">{initials}</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">{user?.username}</div>
            <div className="sidebar-user-role">{user?.role || 'user'}</div>
          </div>
          <button className="btn-logout" onClick={logout} title="Sign out">
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
