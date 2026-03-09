import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (
      err.response?.status === 401 &&
      !err.config?.url?.includes('/auth/login')
    ) {
      if (!localStorage.getItem('token')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────
export async function login(username, password) {
  const { data } = await api.post('/auth/login', { username, password });
  return data;
}

// ── Collections ───────────────────────────────────────────────────────
export async function getCollections() {
  const { data } = await api.get('/collections');
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.collections)) return data.collections;
  if (typeof data.collections === 'string') return data.collections.split(',');
  if (typeof data === 'string') return data.split(',');
  return [];
}

// ── Documents ─────────────────────────────────────────────────────────
export async function getDocuments(collection) {
  const { data } = await api.get('/documents', { params: { collection } });
  return data.documents;
}

export async function uploadDocuments(collection, files) {
  const form = new FormData();
  form.append('collection', collection);
  for (const f of files) form.append('files', f);
  const { data } = await api.post('/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteDocument(docName, collection) {
  const { data } = await api.delete(
    '/documents/' + encodeURIComponent(docName),
    { params: { collection } }
  );
  return data;
}

// ── Workspaces ────────────────────────────────────────────────────────
export async function createWorkspace() {
  const { data } = await api.post('/workspaces');
  return data;
}

export async function uploadWorkspaceDocuments(workspaceId, files) {
  const form = new FormData();
  for (const f of files) form.append('files', f);
  const { data } = await api.post(
    '/workspaces/' + workspaceId + '/documents',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export async function deleteWorkspace(workspaceId) {
  const { data } = await api.delete('/workspaces/' + workspaceId);
  return data;
}

// ── Chat ──────────────────────────────────────────────────────────────
export async function sendChat({ collection, question, workspaceId, conversationId }) {
  const body = { question };
  if (workspaceId)    body.workspace_id    = workspaceId;
  if (collection)     body.collection      = collection;
  if (conversationId) body.conversation_id = conversationId;
  const { data } = await api.post('/chat', body);
  return data;
}

// ── Conversations ─────────────────────────────────────────────────────
export async function getConversations() {
  const { data } = await api.get('/conversations');
  return data;
}

export async function getConversation(id) {
  const { data } = await api.get('/conversations/' + id);
  return data;
}

export async function deleteConversation(id) {
  const { data } = await api.delete('/conversations/' + id);
  return data;
}

export async function renameConversation(id, title) {
  const { data } = await api.patch('/conversations/' + id, { title });
  return data;
}

export default api;

// ── Feedback ──────────────────────────────────────────────────────────
export async function submitFeedback(payload) {
  const { data } = await api.post('/feedback', payload);
  return data;
}