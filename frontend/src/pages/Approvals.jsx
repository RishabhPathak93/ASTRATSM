import React, { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, XCircle, ChevronDown, ChevronUp, FileEdit, Trash2, Edit2, Save, X } from 'lucide-react'
import { Spinner, Input } from '@/components/ui/index.jsx'
import { timeAgo, extractError } from '@/utils/index.js'
import { useAuthStore } from '@/stores/authStore.js'
import { approvalsApi, timelineApprovalsApi } from '@/api/index.js'

const TYPE_COLOR   = { edit: 'var(--info)', delete: 'var(--danger)', create: 'var(--accent)' }
const TYPE_BG      = { edit: 'rgba(122,166,184,0.12)', delete: 'rgba(217,108,108,0.12)', create: 'rgba(35,114,39,0.12)' }
const TYPE_ICON    = { edit: FileEdit, delete: Trash2, create: Edit2 }
const STATUS_COLOR = { pending: 'var(--warning)', approved: 'var(--success)', rejected: 'var(--danger)' }
const STATUS_BG    = { pending: 'rgba(111,166,118,0.12)', approved: 'rgba(73,163,95,0.12)', rejected: 'rgba(217,108,108,0.12)' }
const SEL = { width: '100%', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', color: 'var(--text-1)', fontSize: '13px', padding: '8px 12px', outline: 'none', boxSizing: 'border-box' }

// FIX: Approvals had no mobile awareness at all
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])
  return isMobile
}

export default function ApprovalsPage() {
  const isMobile = useIsMobile()
  const qc      = useQueryClient()
  const user    = useAuthStore(s => s.user)
  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    qc.setQueryData(['approval-count'], { count: 0 })
  }, [])

  async function handleMarkAllRead() {
    try {
      await approvalsApi.markAllRead()
      qc.setQueryData(['approval-count'], { count: 0 })
      flash('All marked as read.')
    } catch (e) { /* silent */ }
  }

  const [statusFilter, setStatusFilter] = useState(isAdmin ? 'pending' : '')
  const [expanded, setExpanded]         = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [adminNote, setAdminNote]       = useState({})
  const [applyingId, setApplyingId]     = useState(null)
  const [applyForm, setApplyForm]       = useState({})
  const [applyLoading, setApplyLoading] = useState(false)
  const [error, setError]               = useState('')
  const [successMsg, setSuccessMsg]     = useState('')

  const { data: projectData, isLoading: projectLoading } = useQuery({
    queryKey: ['approvals', statusFilter],
    queryFn: () => approvalsApi.list({ status: statusFilter || undefined }).then(r => r.data.results || r.data),
    refetchInterval: 15000,
  })

  const { data: timelineData, isLoading: timelineLoading } = useQuery({
    queryKey: ['timeline-approvals', statusFilter],
    queryFn: () => timelineApprovalsApi.list({ status: statusFilter || undefined }).then(r => r.data.results || r.data),
    refetchInterval: 15000,
  })

  const isLoading = projectLoading || timelineLoading

  const requests = React.useMemo(() => {
    const proj = (projectData || []).map(r => ({ ...r, _kind: 'project' }))
    const tl   = (timelineData  || []).map(r => ({ ...r, _kind: 'timeline', project_name: r.timeline_name || r.project_name || 'Timeline' }))
    return [...proj, ...tl].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  }, [projectData, timelineData])

  const pendingCount = requests.filter(r => r.status === 'pending').length

  function flash(msg) { setSuccessMsg(msg); setTimeout(() => setSuccessMsg(''), 4000) }
  const af = (k, v) => setApplyForm(p => ({ ...p, [k]: v }))

  async function handleApprove(id, kind) {
    setActionLoading(id + '_approve'); setError('')
    try {
      const api = kind === 'timeline' ? timelineApprovalsApi : approvalsApi
      await api.approve(id, { admin_note: adminNote[id] || '' })
      qc.invalidateQueries(['approvals'])
      qc.invalidateQueries(['timeline-approvals'])
      qc.invalidateQueries(['approval-count'])
      qc.invalidateQueries(['projects'])
      qc.invalidateQueries(['timelines'])
      setExpanded(null)
      flash('Request approved — user has been notified.')
    } catch (err) { setError(extractError(err)) }
    finally { setActionLoading(null) }
  }

  async function handleReject(id, kind) {
    setActionLoading(id + '_reject'); setError('')
    try {
      const api = kind === 'timeline' ? timelineApprovalsApi : approvalsApi
      await api.reject(id, { admin_note: adminNote[id] || '' })
      qc.invalidateQueries(['approvals'])
      qc.invalidateQueries(['timeline-approvals'])
      qc.invalidateQueries(['approval-count'])
      setExpanded(null)
      flash('Request rejected.')
    } catch (err) { setError(extractError(err)) }
    finally { setActionLoading(null) }
  }

  function openApplyForm(req) {
    setApplyingId(req.id)
    setExpanded(null)

    if (req._kind === 'timeline') {
      const t = req.timeline_detail || {}
      setApplyForm({
        name:            t.name            || '',
        description:     t.description     || '',
        status:          t.status          || '',
        start_date:      t.start_date      || '',
        end_date:        t.end_date        || '',
        hours_allocated: t.hours_allocated != null ? String(t.hours_allocated) : '',
      })
      return
    }

    const p = req.project_detail || {}
    setApplyForm({
      name:        p.name        || '',
      description: p.description || '',
      status:      p.status      || '',
      priority:    p.priority    || '',
      start_date:  p.start_date  || '',
      end_date:    p.end_date    || '',
      resource_l1: p.resource_l1 != null ? String(p.resource_l1) : '',
      resource_l2: p.resource_l2 != null ? String(p.resource_l2) : '',
      resource_l3: p.resource_l3 != null ? String(p.resource_l3) : '',
      resource_l4: p.resource_l4 != null ? String(p.resource_l4) : '',
      hours:       p.hours       != null ? String(p.hours)       : '',
      activity:    p.activity    || '',
    })
  }

  async function submitApply(req) {
    setApplyLoading(true); setError('')
    try {
      if (req._kind === 'timeline') {
        const payload = {}
        Object.entries(applyForm).forEach(([k, v]) => { if (v !== '') payload[k] = v })
        if (payload.hours_allocated !== undefined) payload.hours_allocated = parseInt(payload.hours_allocated) || 0
        await timelineApprovalsApi.applyEdit(req.id, payload)
        qc.invalidateQueries(['timeline-approvals'])
        qc.invalidateQueries(['timelines'])
      } else {
        const payload = {}
        Object.entries(applyForm).forEach(([k, v]) => { if (v !== '') payload[k] = v })
        ;['resource_l1','resource_l2','resource_l3','resource_l4'].forEach(k => {
          if (payload[k] !== undefined) payload[k] = parseInt(payload[k]) || 0
        })
        if (payload.hours !== undefined) payload.hours = parseFloat(payload.hours) || 0
        await approvalsApi.applyEdit(req.id, payload)
        qc.invalidateQueries(['approvals'])
        qc.invalidateQueries(['projects'])
        qc.invalidateQueries(['project', String(req.project)])
      }
      setApplyingId(null)
      flash('Edit applied successfully!')
    } catch (err) { setError(extractError(err)) }
    finally { setApplyLoading(false) }
  }

  const filterTabs = isAdmin
    ? [['pending','Pending'], ['approved','Approved'], ['rejected','Rejected'], ['','All']]
    : [['','All'], ['pending','Pending'], ['approved','Approved'], ['rejected','Rejected']]

  // FIX: On mobile, margin:'-32px' and padding:'20px 32px' caused horizontal overflow.
  // Now use responsive padding that matches the main layout gutter.
  const hPad = isMobile ? '16px' : '32px'

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:0, height:'calc(100vh - 60px)', overflow:'hidden', margin: isMobile ? '-16px' : '-32px' }}>

      {/* Sticky top bar */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', padding:`16px ${hPad}`, borderBottom:'1px solid var(--border)', background:'var(--bg-1)', flexShrink:0, flexWrap:'wrap', gap:10 }}>
        <div style={{ display:'flex', alignItems:'flex-start', gap:12, flexWrap:'wrap', flex:1, minWidth:0 }}>
          <div style={{ minWidth:0 }}>
            <h1 style={{ fontFamily:'var(--font-display)', fontWeight:800, fontSize: isMobile ? '1.3rem' : '1.6rem', letterSpacing:'-0.02em' }}>Approvals</h1>
            <p style={{ color:'var(--text-2)', fontSize:'12px', marginTop:2 }}>
              {isAdmin
                ? pendingCount > 0 ? <><span style={{ color:'var(--warning)', fontWeight:700 }}>{pendingCount} pending</span> · needs your review</> : <span style={{ color:'var(--success)' }}>All caught up ✓</span>
                : 'Your edit & delete requests'
              }
            </p>
          </div>

          {/* Filter tabs — scroll horizontally on mobile instead of wrapping */}
          <div style={{ display:'flex', gap:3, background:'var(--bg-2)', padding:3, borderRadius:'var(--r-md)', border:'1px solid var(--border)', overflowX:'auto', flexShrink:0 }}>
            {filterTabs.map(([val, label]) => (
              <button key={val} onClick={() => setStatusFilter(val)} style={{ background:statusFilter===val?'var(--bg-1)':'transparent', border:statusFilter===val?'1px solid var(--border)':'1px solid transparent', borderRadius:'var(--r-sm)', padding:'5px 12px', fontSize:'12px', fontWeight:statusFilter===val?600:400, color:statusFilter===val?'var(--text-0)':'var(--text-3)', cursor:'pointer', transition:'all var(--t-fast)', whiteSpace:'nowrap' }}>
                {label}
              </button>
            ))}
          </div>

          {/* Mark all read */}
          <button
            onClick={handleMarkAllRead}
            style={{ fontSize:'12px', color:'var(--text-3)', background:'none', border:'1px solid var(--border)', borderRadius:'var(--r-md)', padding:'5px 12px', cursor:'pointer', display:'flex', alignItems:'center', gap:5, transition:'all var(--t-fast)', whiteSpace:'nowrap', flexShrink:0 }}
            onMouseEnter={e => { e.currentTarget.style.color='var(--text-0)'; e.currentTarget.style.borderColor='var(--accent)' }}
            onMouseLeave={e => { e.currentTarget.style.color='var(--text-3)'; e.currentTarget.style.borderColor='var(--border)' }}
          >
            <CheckCircle size={12} /> Mark all read
          </button>
        </div>

        {(successMsg || error) && (
          <div style={{ fontSize:'12px', fontWeight:600, padding:'6px 14px', borderRadius:'var(--r-md)', background:successMsg?'rgba(74,222,128,0.1)':'rgba(248,113,113,0.1)', color:successMsg?'var(--success)':'var(--danger)', border:`1px solid ${successMsg?'rgba(74,222,128,0.35)':'rgba(248,113,113,0.3)'}`, display:'flex', alignItems:'center', gap:6, flexShrink:0 }}>
            {successMsg ? <><CheckCircle size={13}/> {successMsg}</> : error}
          </div>
        )}
      </div>

      {/* Scrollable content */}
      <div style={{ flex:1, overflowY:'auto', padding:`20px ${hPad}` }}>
        {isLoading ? (
          <div style={{ display:'flex', justifyContent:'center', paddingTop:80 }}><Spinner /></div>
        ) : requests.length === 0 ? (
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', paddingTop:100, gap:12 }}>
            <div style={{ width:56, height:56, borderRadius:'50%', background:'var(--bg-2)', display:'flex', alignItems:'center', justifyContent:'center' }}>
              <CheckCircle size={24} color="var(--text-3)" />
            </div>
            <div style={{ fontWeight:600, fontSize:'15px', color:'var(--text-1)' }}>{isAdmin ? 'No requests to review.' : 'No approval requests yet.'}</div>
            <div style={{ fontSize:'13px', color:'var(--text-3)', textAlign:'center' }}>{isAdmin ? 'Manager requests will appear here.' : 'Use "Request Edit" or "Request Delete" on a project.'}</div>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {requests.map(req => {
              const TypeIcon    = TYPE_ICON[req.request_type] || FileEdit
              const isOpen      = expanded === req.id
              const isApplying  = applyingId === req.id
              const alreadyDone = req.proposed_changes?._applied === true

              return (
                <div key={req.id} style={{ background:'var(--bg-1)', border:'1px solid var(--border)', borderLeft:`3px solid ${STATUS_COLOR[req.status]}`, borderRadius:'var(--r-md)', overflow:'hidden' }}>

                  {/* Header row */}
                  <div onClick={() => { if (!isApplying) setExpanded(isOpen ? null : req.id) }}
                    style={{ display:'flex', alignItems:'center', gap: isMobile ? 10 : 16, padding: isMobile ? '12px 14px' : '14px 20px', cursor:isApplying?'default':'pointer', flexWrap: isMobile ? 'wrap' : 'nowrap' }}
                    onMouseEnter={e => { if(!isApplying) e.currentTarget.style.background='var(--bg-2)' }}
                    onMouseLeave={e => e.currentTarget.style.background='transparent'}
                  >
                    <div style={{ width:38, height:38, borderRadius:'var(--r-md)', flexShrink:0, background:TYPE_BG[req.request_type], border:`1px solid ${TYPE_COLOR[req.request_type]}30`, display:'flex', alignItems:'center', justifyContent:'center' }}>
                      <TypeIcon size={16} color={TYPE_COLOR[req.request_type]} />
                    </div>

                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:3 }}>
                        <span style={{ fontWeight:700, fontSize:'13px', color:'var(--text-0)' }}>{req.project_name || 'Unknown Project'}</span>
                        <span style={{ fontSize:'10px', fontWeight:700, padding:'2px 8px', borderRadius:'var(--r-full)', background:TYPE_BG[req.request_type], color:TYPE_COLOR[req.request_type], border:`1px solid ${TYPE_COLOR[req.request_type]}30`, textTransform:'uppercase', letterSpacing:'0.06em' }}>{req.request_type}</span>
                        <span style={{ fontSize:'10px', fontWeight:700, padding:'2px 8px', borderRadius:'var(--r-full)', background:STATUS_BG[req.status], color:STATUS_COLOR[req.status], border:`1px solid ${STATUS_COLOR[req.status]}30`, textTransform:'uppercase', letterSpacing:'0.06em' }}>{alreadyDone ? 'applied ✓' : req.status}</span>
                      </div>
                      <div style={{ fontSize:'12px', color:'var(--text-2)' }}>
                        {isAdmin ? <><strong>{req.requested_by_name}</strong> · </> : ''}{timeAgo(req.created_at)}
                        {req.resolved_by_name && <> · by <strong>{req.resolved_by_name}</strong></>}
                      </div>
                      {req.reason && <div style={{ fontSize:'12px', color:'var(--text-3)', marginTop:2, fontStyle:'italic' }}>"{req.reason}"</div>}
                    </div>

                    {/* Manager: Apply Edit button */}
                    {!isAdmin && req.status === 'approved' && req.request_type === 'edit' && !alreadyDone && !isApplying && (
                      <button
                        onClick={e => { e.stopPropagation(); openApplyForm(req) }}
                        style={{ display:'flex', alignItems:'center', gap:6, background:'rgba(74,222,128,0.1)', border:'1px solid rgba(74,222,128,0.4)', borderRadius:'var(--r-md)', padding:'8px 14px', cursor:'pointer', color:'var(--success)', fontSize:'12px', fontWeight:600, flexShrink:0, transition:'all var(--t-fast)', whiteSpace:'nowrap' }}
                        onMouseEnter={e => e.currentTarget.style.background='rgba(74,222,128,0.2)'}
                        onMouseLeave={e => e.currentTarget.style.background='rgba(74,222,128,0.1)'}
                      >
                        <Edit2 size={13} /> {isMobile ? 'Apply' : 'Apply Edit Now'}
                      </button>
                    )}

                    {!isApplying && (
                      <div style={{ color:'var(--text-3)', flexShrink:0 }}>{isOpen ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}</div>
                    )}
                  </div>

                  {/* Apply Edit form */}
                  {isApplying && (
                    <div style={{ borderTop:'1px solid var(--border)', padding: isMobile ? '16px 14px' : '20px 24px', background:'var(--bg-2)', display:'flex', flexDirection:'column', gap:16 }}>
                      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:8 }}>
                        <div style={{ fontSize:'12px', fontWeight:700, color:'var(--success)', textTransform:'uppercase', letterSpacing:'0.08em' }}>
                          Apply Approved Edit — {req.project_name}
                        </div>
                        <button onClick={() => setApplyingId(null)} style={{ background:'none', border:'1px solid var(--border)', borderRadius:'var(--r-sm)', padding:'4px 10px', cursor:'pointer', color:'var(--text-3)', fontSize:'12px', display:'flex', alignItems:'center', gap:4 }}>
                          <X size={12} /> Cancel
                        </button>
                      </div>

                      <div style={{ fontSize:'12px', color:'var(--text-2)', background:'rgba(74,222,128,0.06)', border:'1px solid rgba(74,222,128,0.2)', borderRadius:'var(--r-md)', padding:'10px 14px' }}>
                        Fields are pre-filled with current values. Change only what you need — empty fields stay as-is.
                      </div>

                      {req._kind === 'timeline' ? (
                        <>
                          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', gap:12 }}>
                            <Input label="Phase Name" value={applyForm.name} onChange={e => af('name', e.target.value)} />
                            <div>
                              <div style={{ fontSize:'12px', fontWeight:600, color:'var(--text-2)', marginBottom:6 }}>Status</div>
                              <select value={applyForm.status} onChange={e => af('status', e.target.value)} style={SEL}>
                                <option value="">— no change —</option>
                                <option value="pending">Pending</option>
                                <option value="in_progress">In Progress</option>
                                <option value="completed">Completed</option>
                                <option value="on_hold">On Hold</option>
                              </select>
                            </div>
                          </div>
                          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', gap:12 }}>
                            <Input label="Start Date" type="date" value={applyForm.start_date} onChange={e => af('start_date', e.target.value)} />
                            <Input label="End Date" type="date" value={applyForm.end_date} onChange={e => af('end_date', e.target.value)} />
                          </div>
                          <Input label="Hours Allocated" type="number" min="0" value={applyForm.hours_allocated} onChange={e => af('hours_allocated', e.target.value)} placeholder="Leave blank to keep" />
                          <div>
                            <div style={{ fontSize:'12px', fontWeight:600, color:'var(--text-2)', marginBottom:6 }}>Description</div>
                            <textarea value={applyForm.description} onChange={e => af('description', e.target.value)} placeholder="Leave blank to keep existing…" rows={3}
                              style={{ width:'100%', boxSizing:'border-box', background:'var(--bg-1)', border:'1px solid var(--border)', borderRadius:'var(--r-md)', color:'var(--text-0)', fontSize:'13px', padding:'10px 12px', outline:'none', resize:'vertical', fontFamily:'inherit' }}
                              onFocus={e => e.target.style.borderColor='var(--accent)'} onBlur={e => e.target.style.borderColor='var(--border)'}
                            />
                          </div>
                        </>
                      ) : (
                        <>
                          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', gap:12 }}>
                            <Input label="Project Name" value={applyForm.name} onChange={e => af('name', e.target.value)} />
                            <div>
                              <div style={{ fontSize:'12px', fontWeight:600, color:'var(--text-2)', marginBottom:6 }}>Status</div>
                              <select value={applyForm.status} onChange={e => af('status', e.target.value)} style={SEL}>
                                <option value="">— no change —</option>
                                <option value="planning">Planning</option><option value="in_progress">In Progress</option><option value="review">Review</option><option value="completed">Completed</option><option value="on_hold">On Hold</option>
                              </select>
                            </div>
                          </div>
                          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', gap:12 }}>
                            <div>
                              <div style={{ fontSize:'12px', fontWeight:600, color:'var(--text-2)', marginBottom:6 }}>Priority</div>
                              <select value={applyForm.priority} onChange={e => af('priority', e.target.value)} style={SEL}>
                                <option value="">— no change —</option>
                                <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
                              </select>
                            </div>
                            <Input label="Activity" value={applyForm.activity} onChange={e => af('activity', e.target.value)} placeholder="e.g. Development, Testing…" />
                          </div>
                          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', gap:12 }}>
                            <Input label="Start Date" type="date" value={applyForm.start_date} onChange={e => af('start_date', e.target.value)} />
                            <Input label="End Date" type="date" value={applyForm.end_date} onChange={e => af('end_date', e.target.value)} />
                          </div>
                          <Input label="Hours" type="number" min="0" value={applyForm.hours} onChange={e => af('hours', e.target.value)} placeholder="Leave blank to keep" />
                          <div>
                            <div style={{ fontSize:'12px', fontWeight:600, color:'var(--text-2)', marginBottom:8 }}>Resource Levels</div>
                            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(80px, 1fr))', gap:10 }}>
                              {['l1','l2','l3','l4'].map(l => (
                                <Input key={l} label={l.toUpperCase()} type="number" min="0" value={applyForm[`resource_${l}`]} onChange={e => af(`resource_${l}`, e.target.value)} placeholder="0" />
                              ))}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize:'12px', fontWeight:600, color:'var(--text-2)', marginBottom:6 }}>Description</div>
                            <textarea value={applyForm.description} onChange={e => af('description', e.target.value)} placeholder="Leave blank to keep existing…" rows={3}
                              style={{ width:'100%', boxSizing:'border-box', background:'var(--bg-1)', border:'1px solid var(--border)', borderRadius:'var(--r-md)', color:'var(--text-0)', fontSize:'13px', padding:'10px 12px', outline:'none', resize:'vertical', fontFamily:'inherit' }}
                              onFocus={e => e.target.style.borderColor='var(--accent)'} onBlur={e => e.target.style.borderColor='var(--border)'}
                            />
                          </div>
                        </>
                      )}

                      <div style={{ display:'flex', justifyContent:'flex-end' }}>
                        <button onClick={() => submitApply(req)} disabled={applyLoading}
                          style={{ display:'flex', alignItems:'center', gap:6, background:'rgba(74,222,128,0.12)', border:'1px solid rgba(74,222,128,0.4)', borderRadius:'var(--r-md)', padding:'10px 24px', cursor:'pointer', color:'var(--success)', fontSize:'13px', fontWeight:700, opacity:applyLoading?0.7:1 }}>
                          <Save size={14}/> {applyLoading ? 'Applying…' : 'Apply Changes'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Expanded detail */}
                  {isOpen && !isApplying && (
                    <div style={{ borderTop:'1px solid var(--border)', padding: isMobile ? '14px' : '16px 24px', background:'var(--bg-2)', display:'flex', flexDirection:'column', gap:14 }}>

                      {req.admin_note && (
                        <div style={{ background:req.status==='rejected'?'rgba(248,113,113,0.08)':'rgba(74,222,128,0.08)', border:`1px solid ${req.status==='rejected'?'rgba(248,113,113,0.3)':'rgba(74,222,128,0.3)'}`, borderRadius:'var(--r-md)', padding:'10px 14px' }}>
                          <div style={{ fontSize:'10px', fontWeight:700, color:'var(--text-3)', textTransform:'uppercase', marginBottom:4 }}>Admin Note</div>
                          <div style={{ fontSize:'13px', color:'var(--text-1)', fontStyle:'italic' }}>"{req.admin_note}"</div>
                        </div>
                      )}

                      {isAdmin && req.status === 'pending' && (
                        <>
                          <div>
                            <div style={{ fontSize:'11px', fontWeight:700, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:6 }}>Note to Manager <span style={{ fontWeight:400 }}>(optional)</span></div>
                            <textarea value={adminNote[req.id] || ''} onChange={e => setAdminNote(n => ({ ...n, [req.id]: e.target.value }))} placeholder="Explain your decision…" rows={2}
                              style={{ width:'100%', boxSizing:'border-box', background:'var(--bg-1)', border:'1px solid var(--border)', borderRadius:'var(--r-md)', color:'var(--text-0)', fontSize:'13px', padding:'10px 12px', outline:'none', resize:'vertical', fontFamily:'inherit' }}
                              onFocus={e => e.target.style.borderColor='var(--accent)'} onBlur={e => e.target.style.borderColor='var(--border)'}
                            />
                          </div>
                          {/* FIX: Buttons stack vertically on mobile to avoid overflow */}
                          <div style={{ display:'flex', gap:10, justifyContent:'flex-end', flexWrap: isMobile ? 'wrap' : 'nowrap' }}>
                            <button onClick={() => handleReject(req.id, req._kind)} disabled={!!actionLoading}
                              style={{ display:'flex', alignItems:'center', gap:6, background:'rgba(248,113,113,0.1)', border:'1px solid rgba(248,113,113,0.4)', borderRadius:'var(--r-md)', padding:'9px 20px', cursor:'pointer', color:'var(--danger)', fontSize:'13px', fontWeight:600, opacity:actionLoading?0.6:1, transition:'all var(--t-fast)', flex: isMobile ? '1 1 auto' : 'none', justifyContent:'center' }}>
                              <XCircle size={14}/> {actionLoading === req.id+'_reject' ? 'Rejecting…' : 'Reject'}
                            </button>
                            <button onClick={() => handleApprove(req.id, req._kind)} disabled={!!actionLoading}
                              style={{ display:'flex', alignItems:'center', gap:6, background:'rgba(74,222,128,0.12)', border:'1px solid rgba(74,222,128,0.4)', borderRadius:'var(--r-md)', padding:'9px 20px', cursor:'pointer', color:'var(--success)', fontSize:'13px', fontWeight:600, opacity:actionLoading?0.6:1, transition:'all var(--t-fast)', flex: isMobile ? '1 1 auto' : 'none', justifyContent:'center' }}>
                              <CheckCircle size={14}/> {actionLoading === req.id+'_approve' ? 'Approving…' : 'Approve'}
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {successMsg && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
          background: 'rgba(74,222,128,0.12)', border: '1px solid rgba(74,222,128,0.4)',
          borderRadius: 'var(--r-md)', padding: '12px 20px',
          color: 'var(--success)', fontSize: '13px', fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 8,
          boxShadow: '0 4px 24px rgba(0,0,0,0.18)',
          animation: 'fadeIn 0.2s ease',
        }}>
          <CheckCircle size={16} /> {successMsg}
        </div>
      )}
    </div>
  )
}
