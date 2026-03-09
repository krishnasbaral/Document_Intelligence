import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ConversationProvider } from './context/ConversationContext';
import { useToast } from './hooks/useToast';
import Sidebar from './components/Sidebar';
import ToastContainer from './components/ToastContainer';
import Login from './pages/Login';
import Chat from './pages/Chat';
import Documents from './pages/Documents';

function ProtectedLayout() {
  const { user } = useAuth();
  const { toasts, addToast } = useToast();

  if (!user) return <Navigate to="/login" replace />;

  return (
    <ConversationProvider>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/chat"      element={<Chat addToast={addToast} />} />
            <Route path="/documents" element={<Documents addToast={addToast} />} />
            <Route path="*"          element={<Navigate to="/chat" replace />} />
          </Routes>
        </main>
        <ToastContainer toasts={toasts} />
      </div>
    </ConversationProvider>
  );
}

function LoginRoute() {
  const { user } = useAuth();
  if (user) return <Navigate to="/chat" replace />;
  return <Login />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/*"     element={<ProtectedLayout />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
