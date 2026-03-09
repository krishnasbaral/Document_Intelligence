import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileSearch, Zap, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const FEATURES = [
  { icon: FileSearch, label: 'Instant answers from your documents' },
  { icon: Zap,        label: 'Context-aware answers with source citations' },
  { icon: Shield,     label: 'Role-based access control' },
];

export default function Login() {
  const { login }   = useAuth();
  const navigate    = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/chat');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Left — brand panel */}
      <div className="login-left">
        <div className="login-left-content">
          <div className="login-brand-mark">
            <img src="/logo.png" alt="Pon Pure" className="login-brand-logo" />
            <h1>Intellidoc</h1>
          </div>
          <div className="login-hero">
            <h2>Your documents,<br />intelligently answered.</h2>
            <p>
              Ask questions in plain English and get precise answers
              from your knowledge base — powered by AI with full source attribution.
            </p>
            <div className="login-features">
              {FEATURES.map(({ icon: Icon, label }) => (
                <div key={label} className="login-feature">
                  <div className="login-feature-dot"><Icon size={14} /></div>
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="login-left-footer">
          © {new Date().getFullYear()} Intellidoc · AI-Powered Document Intelligence
        </div>
      </div>

      {/* Right — form */}
      <div className="login-right">
        <div className="login-card">
          <div className="login-card-header">
            <h2>Welcome back</h2>
            <p>Sign in to your workspace to continue</p>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                className="form-input"
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
                autoComplete="username"
              />
            </div>
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                className="form-input"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <button type="submit" className="btn btn-primary login-btn" disabled={loading}>
              {loading
                ? <><span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Signing in…</>
                : 'Sign in'}
            </button>
          </form>
          {error && <div className="login-error">{error}</div>}
        </div>
      </div>
    </div>
  );
}
