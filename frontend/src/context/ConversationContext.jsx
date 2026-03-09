import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import {
  getConversations,
  getConversation,
  deleteConversation as apiDelete,
  renameConversation as apiRename,
} from '../api';
import { useAuth } from './AuthContext';

const ConversationContext = createContext(null);

export function ConversationProvider({ children }) {
  const { user } = useAuth();

  const [conversations, setConversations]     = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  // Atomic selection: id + messages set together AFTER fetch completes.
  // ts (timestamp) ensures the effect fires even when null → null (New Chat).
  const [sidebarSelection, setSidebarSelection] = useState({ id: null, messages: [], ts: 0 });

  const loadConversations = useCallback(async () => {
    if (!user) return;
    try {
      const list = await getConversations();
      setConversations(list);
    } catch {}
  }, [user]);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  // Called when user clicks a conversation in the sidebar
  const selectConversation = useCallback(async (id) => {
    if (!id) {
      setSidebarSelection({ id: null, messages: [], ts: Date.now() });
      return;
    }
    setLoadingMessages(true);
    try {
      const conv = await getConversation(id);
      const msgs = (conv.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        sources: m.sources
          ? (() => { try { return JSON.parse(m.sources); } catch { return null; } })()
          : null,
      }));
      // id + messages set together atomically
      setSidebarSelection({ id, messages: msgs, ts: Date.now() });
    } catch {
      setSidebarSelection({ id, messages: [], ts: Date.now() });
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // New Chat — ts ensures effect fires even if id was already null
  const startNewChat = useCallback(() => {
    setSidebarSelection({ id: null, messages: [], ts: Date.now() });
  }, []);

  // Only refreshes sidebar list — does NOT interfere with chat messages
  const notifyNewConversation = useCallback(() => {
    loadConversations();
  }, [loadConversations]);

  const refreshConversations = useCallback(() => {
    loadConversations();
  }, [loadConversations]);

  const removeConversation = useCallback(async (id) => {
    try {
      await apiDelete(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      setSidebarSelection((prev) =>
        prev.id === id ? { id: null, messages: [], ts: Date.now() } : prev
      );
    } catch {}
  }, []);

  const updateTitle = useCallback(async (id, title) => {
    try {
      await apiRename(id, title);
      setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
    } catch {}
  }, []);

  return (
    <ConversationContext.Provider value={{
      conversations,
      sidebarSelection,
      loadingMessages,
      loadConversations,
      selectConversation,
      startNewChat,
      notifyNewConversation,
      refreshConversations,
      removeConversation,
      updateTitle,
    }}>
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation() {
  const ctx = useContext(ConversationContext);
  if (!ctx) throw new Error('useConversation must be used within ConversationProvider');
  return ctx;
}
