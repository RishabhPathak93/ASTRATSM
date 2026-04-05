import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, Lock, Eye, EyeOff } from 'lucide-react'
import { authApi } from '@/api/index.js'
import { useAuthStore } from '@/stores/authStore.js'
import { extractError } from '@/utils/index.js'

export default function LoginPage() {
  const navigate = useNavigate()
  const setTokens = useAuthStore(s => s.setTokens)
  const setUser = useAuthStore(s => s.setUser)

  const [form, setForm] = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await authApi.login(form)
      setTokens(data.access, data.refresh)
      setUser(data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(extractError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      background: 'var(--bg-0)',
    }}>
      {/* Left panel — branding */}
      <div style={{
        width: '50%', display: 'flex', flexDirection: 'column',
        justifyContent: 'center', alignItems: 'center',
        background: 'linear-gradient(145deg, rgba(19,36,64,0.95) 0%, rgba(35,114,39,0.16) 100%)', borderRight: '1px solid var(--border)',
        padding: 'var(--sp-12)', position: 'relative', overflow: 'hidden',
      }}>
        {/* Grid background */}
        <div style={{
          position: 'absolute', inset: 0, opacity: 0.04,
          backgroundImage: 'linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }} />
        {/* Accent glow */}
        <div style={{
          position: 'absolute', width: 400, height: 400,
          background: 'radial-gradient(circle, rgba(35,114,39,0.22) 0%, transparent 70%)',
          left: '50%', top: '50%', transform: 'translate(-50%,-50%)',
          pointerEvents: 'none',
        }} />

        <div style={{ position: 'relative', textAlign: 'center', maxWidth: 400 }}>
          {/* Logo */}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--sp-6)' }}>
            <img src="/logo.png" style={{ width: 56, height: 56, objectFit: 'contain' }} />
          </div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '3rem', letterSpacing: '-0.04em', marginBottom: 'var(--sp-4)', lineHeight: 1 }}>
            AstraTSM<br /><span style={{ color: 'var(--accent)' }}></span>
          </h1>
          <p style={{ fontSize: '15px', color: 'var(--text-2)', lineHeight: 1.6 }}>
            Timesheet and delivery intelligence platform.<br />
            Hours, phases, accountability, and visibility in one place.
          </p>

          <div style={{ marginTop: 'var(--sp-10)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)', textAlign: 'left' }}>
            {[
              'Role-based access control',
              'Delivery and timeline visibility',
              'Resource utilization tracking',
              'Timesheet-based performance insights',
            ].map(f => (
              <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', color: 'var(--text-2)', fontSize: '13px' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0 }} />
                {f}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 'var(--sp-12)',
      }}>
        <div style={{ width: '100%', maxWidth: 380, animation: 'fadeIn 0.4s ease both' }}>
          <div style={{ marginBottom: 'var(--sp-8)' }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.75rem', marginBottom: '6px' }}>
              Welcome back
            </h2>
            <p style={{ color: 'var(--text-2)', fontSize: '14px' }}>Sign in to your workspace</p>
          </div>

          {error && (
            <div style={{
              background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)',
              borderRadius: 'var(--r-md)', padding: '10px 14px',
              color: 'var(--danger)', fontSize: '13px', marginBottom: 'var(--sp-5)',
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
            {/* Email */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Email</label>
              <div style={{ position: 'relative' }}>
                <Mail size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-3)', pointerEvents: 'none' }} />
                <input
                  type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="admin@company.com" required
                  style={{
                    width: '100%', background: 'var(--bg-2)', border: '1px solid var(--border)',
                    borderRadius: 'var(--r-md)', color: 'var(--text-0)', fontSize: '14px',
                    padding: '10px 12px 10px 36px', outline: 'none',
                  }}
                  onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                />
              </div>
            </div>

            {/* Password */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Password</label>
              <div style={{ position: 'relative' }}>
                <Lock size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-3)', pointerEvents: 'none' }} />
                <input
                  type={showPass ? 'text' : 'password'} value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  placeholder="••••••••" required
                  style={{
                    width: '100%', background: 'var(--bg-2)', border: '1px solid var(--border)',
                    borderRadius: 'var(--r-md)', color: 'var(--text-0)', fontSize: '14px',
                    padding: '10px 36px 10px 36px', outline: 'none',
                  }}
                  onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                />
                <button type="button" onClick={() => setShowPass(s => !s)} style={{
                  position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', lineHeight: 0,
                }}>
                  {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            <button
              type="submit" disabled={loading}
              style={{
                width: '100%', background: loading ? 'var(--bg-3)' : 'var(--accent)',
                color: loading ? 'var(--text-2)' : '#0a0a0a', border: 'none',
                borderRadius: 'var(--r-md)', padding: '11px', fontSize: '14px',
                fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'var(--font-display)', letterSpacing: '0.04em',
                transition: 'all var(--t-mid)', marginTop: 'var(--sp-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}
            >
              {loading ? (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" style={{ animation: 'spin 0.8s linear infinite' }}>
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.3" strokeWidth="3" fill="none" />
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" fill="none" />
                  </svg>
                  Signing in…
                </>
              ) : 'SIGN IN'}
            </button>
          </form>

          <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text-3)', marginTop: 'var(--sp-6)' }}>
            Rate limited to 10 attempts / minute
          </p>
        </div>
      </div>
    </div>
  )
}
