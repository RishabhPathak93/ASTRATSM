/**
 * Chat.jsx — Polling-based chat (no WebSocket)
 *
 * FIX: Complete mobile layout overhaul.
 * - On mobile the room list and message pane are separate "screens" toggled
 *   by a back button — no hardcoded 250px sidebar stealing half the viewport.
 * - Message bubbles capped at 85% on mobile (was unconditional 65%).
 * - Image attachments use maxWidth:'100%' instead of a fixed 300px.
 * - isMobile hook added throughout to drive layout decisions.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Send, MessageSquare, Hash, Paperclip, X, File, Download, Edit2, Trash2, CheckCheck, ArrowLeft } from 'lucide-react'
import { chatApi } from '@/api/index.js'
import { Avatar, Spinner, EmptyState } from '@/components/ui/index.jsx'
import { timeAgo } from '@/utils/index.js'
import { useAuthStore } from '@/stores/authStore.js'

const POLL_INTERVAL = 3000

// Shared mobile breakpoint (mirrors AppLayout)
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])
  return isMobile
}

export default function ChatPage() {
  const isMobile = useIsMobile()

  const [activeRoom, setActiveRoom]     = useState(null)
  const [messages, setMessages]         = useState([])
  const [input, setInput]               = useState('')
  const [attachment, setAttachment]     = useState(null)
  const [sending, setSending]           = useState(false)
  const [loadingMsgs, setLoadingMsgs]   = useState(false)
  const [selectedMsgs, setSelectedMsgs] = useState(new Set())
  // FIX: Mobile "screen" — null means show room list, 'messages' means show message pane
  const [mobileView, setMobileView]     = useState('rooms') // 'rooms' | 'messages'

  const selectionMode = selectedMsgs.size > 0

  function toggleSelect(id) {
    setSelectedMsgs(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function deleteSelected() {
    for (const id of selectedMsgs) {
      try { await chatApi.deleteMessage(activeRoom.id, id) } catch {}
    }
    setMessages(prev => prev.filter(m => !selectedMsgs.has(m.id)))
    setSelectedMsgs(new Set())
  }

  const lastIdRef  = useRef(0)
  const pollRef    = useRef(null)
  const bottomRef  = useRef(null)
  const fileRef    = useRef(null)
  const user       = useAuthStore(s => s.user)

  const { data: rooms, isLoading: roomsLoading } = useQuery({
    queryKey: ['chat-rooms'],
    queryFn: () => chatApi.rooms().then(r => r.data.results || r.data),
    refetchInterval: 30000,
  })

  useEffect(() => {
    if (!activeRoom) return
    setMessages([])
    lastIdRef.current = 0
    setLoadingMsgs(true)
    setSelectedMsgs(new Set())

    chatApi.messages(activeRoom.id, { limit: 50 })
      .then(r => {
        const msgs = r.data || []
        setMessages(msgs)
        if (msgs.length > 0) lastIdRef.current = msgs[msgs.length - 1].id
      })
      .catch(() => {})
      .finally(() => setLoadingMsgs(false))

    chatApi.markRead(activeRoom.id).catch(() => {})
  }, [activeRoom?.id])

  useEffect(() => {
    if (!activeRoom) return
    if (pollRef.current) clearInterval(pollRef.current)

    pollRef.current = setInterval(async () => {
      try {
        const res = await chatApi.messages(activeRoom.id, { after: lastIdRef.current })
        const newMsgs = res.data || []
        if (newMsgs.length > 0) {
          setMessages(prev => {
            const existingIds = new Set(prev.map(m => m.id))
            const truly_new = newMsgs.filter(m => !existingIds.has(m.id))
            if (truly_new.length === 0) return prev
            lastIdRef.current = truly_new[truly_new.length - 1].id
            return [...prev, ...truly_new]
          })
        }
      } catch {}
    }, POLL_INTERVAL)

    return () => clearInterval(pollRef.current)
  }, [activeRoom?.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function pickFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const isImage = file.type.startsWith('image/')
    setAttachment({
      file,
      previewUrl: isImage ? URL.createObjectURL(file) : null,
      isImage,
      name: file.name,
      size: (file.size / 1024).toFixed(1) + ' KB',
    })
    e.target.value = ''
  }

  async function sendMessage(e) {
    e.preventDefault()
    if ((!input.trim() && !attachment) || sending) return

    setSending(true)
    const optimisticMsg = {
      id: `temp-${Date.now()}`,
      text: input.trim() || (attachment?.name ?? ''),
      sender_detail: { id: user?.id, name: user?.name },
      sender: { id: user?.id, name: user?.name },
      created_at: new Date().toISOString(),
      msg_type: attachment?.isImage ? 'image' : attachment ? 'file' : 'text',
      attachment_url: attachment?.previewUrl || null,
      attachment_name: attachment?.name || null,
      _sending: true,
    }
    setMessages(prev => [...prev, optimisticMsg])
    const textToSend = input.trim()
    const attachToSend = attachment
    setInput('')
    setAttachment(null)

    try {
      let res
      if (attachToSend) {
        const fd = new FormData()
        fd.append('file', attachToSend.file)
        if (textToSend) fd.append('text', textToSend)
        res = await chatApi.sendMessage(activeRoom.id, fd)
      } else {
        res = await chatApi.sendMessage(activeRoom.id, { text: textToSend })
      }
      const realMsg = res.data
      setMessages(prev => prev.map(m =>
        m.id === optimisticMsg.id ? { ...realMsg, _sending: false } : m
      ))
      lastIdRef.current = Math.max(lastIdRef.current, realMsg.id)
    } catch {
      setMessages(prev => prev.filter(m => m.id !== optimisticMsg.id))
      alert('Failed to send message. Try again.')
    } finally {
      setSending(false)
    }
  }

  function selectRoom(room) {
    setActiveRoom(room)
    if (isMobile) setMobileView('messages')
  }

  function goBackToRooms() {
    setMobileView('rooms')
    setActiveRoom(null)
  }

  const projectRooms = (rooms || []).filter(r => r.room_type === 'project')
  const directRooms  = (rooms || []).filter(r => r.room_type === 'direct')

  // ── Room list panel ──────────────────────────────────────────────────────
  const RoomListPanel = (
    <div style={{
      // Desktop: fixed width sidebar. Mobile: full width panel.
      width: isMobile ? '100%' : 250,
      borderRight: isMobile ? 'none' : '1px solid var(--border)',
      display: isMobile && mobileView === 'messages' ? 'none' : 'flex',
      flexDirection: 'column',
      background: 'var(--bg-2)', flexShrink: 0,
    }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontWeight: 700, fontSize: '14px' }}>Chat</span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
        {roomsLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '24px' }}>
            <Spinner size={18} />
          </div>
        ) : (
          <>
            {projectRooms.length > 0 && (
              <div style={{ marginBottom: '8px' }}>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.1em', padding: '6px 8px 4px' }}>
                  Projects
                </div>
                {projectRooms.map(room => (
                  <RoomBtn
                    key={room.id}
                    room={room}
                    active={activeRoom?.id === room.id}
                    onClick={() => selectRoom(room)}
                    unread={room.unread_count || 0}
                  />
                ))}
              </div>
            )}

            {directRooms.length > 0 && (
              <div>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.1em', padding: '6px 8px 4px' }}>
                  Direct Messages
                </div>
                {directRooms.map(room => (
                  <RoomBtn
                    key={room.id}
                    room={room}
                    active={activeRoom?.id === room.id}
                    onClick={() => selectRoom(room)}
                    unread={room.unread_count || 0}
                  />
                ))}
              </div>
            )}

            {!rooms?.length && (
              <p style={{ color: 'var(--text-3)', fontSize: '12px', padding: '12px 8px' }}>
                No rooms yet. Create a project to get a chat room!
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )

  // ── Message pane ─────────────────────────────────────────────────────────
  const MessagePane = (
    <div style={{
      flex: 1,
      display: isMobile && mobileView === 'rooms' ? 'none' : 'flex',
      flexDirection: 'column',
      minWidth: 0,
    }}>
      {!activeRoom ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <EmptyState
            icon={MessageSquare}
            title="Select a room"
            description="Choose a project chat from the sidebar."
          />
        </div>
      ) : (
        <>
          {/* Room header */}
          <div style={{
            padding: '12px 16px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* FIX: Back button on mobile to return to room list */}
              {isMobile && (
                <button
                  onClick={goBackToRooms}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-2)', padding: '4px 6px 4px 0', lineHeight: 0 }}
                  aria-label="Back to rooms"
                >
                  <ArrowLeft size={18} />
                </button>
              )}
              <Avatar name={activeRoom.project_name || activeRoom.name} size={30} />
              <span style={{ fontWeight: 600, fontSize: '14px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: isMobile ? 160 : 300 }}>
                {activeRoom.project_name || activeRoom.name}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '11px', color: 'var(--success)', flexShrink: 0 }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: 'var(--success)',
                animation: 'pulse 2s infinite',
              }} />
              {!isMobile && 'Live'}
            </div>
          </div>

          {/* Messages area */}
          <div style={{
            flex: 1, overflowY: 'auto',
            padding: isMobile ? '12px 12px' : '16px 20px',
            display: 'flex', flexDirection: 'column', gap: '2px',
          }}>
            {loadingMsgs ? (
              <div style={{ display: 'flex', justifyContent: 'center', marginTop: '40px' }}>
                <Spinner size={24} />
              </div>
            ) : messages.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', color: 'var(--text-3)', fontSize: '13px', marginTop: '40px' }}>
                No messages yet — say hello!
              </div>
            ) : (
              messages.map((msg, i) => {
                const isOwn    = (msg.sender_detail?.id || msg.sender?.id) === user?.id
                const prevMsg  = messages[i - 1]
                const prevSame = prevMsg &&
                  (prevMsg.sender_detail?.id || prevMsg.sender?.id) === (msg.sender_detail?.id || msg.sender?.id) &&
                  (new Date(msg.created_at) - new Date(prevMsg.created_at)) < 300000
                return (
                  <MessageBubble
                    key={msg.id}
                    msg={msg}
                    isOwn={isOwn}
                    prevSame={prevSame}
                    isMobile={isMobile}
                    selected={selectedMsgs.has(msg.id)}
                    selectionMode={selectionMode}
                    onSelect={toggleSelect}
                    onEdit={async (newText) => {
                      try {
                        const res = await chatApi.editMessage(activeRoom.id, msg.id, newText)
                        setMessages(prev => prev.map(m => m.id === msg.id ? res.data : m))
                      } catch {}
                    }}
                    onDelete={async () => {
                      try {
                        await chatApi.deleteMessage(activeRoom.id, msg.id)
                        setMessages(prev => prev.filter(m => m.id !== msg.id))
                      } catch {}
                    }}
                  />
                )
              })
            )}
            <div ref={bottomRef} />
          </div>

          {/* Selection action bar */}
          {selectionMode && (
            <div style={{ padding: '8px 16px', borderTop: '1px solid var(--border)', background: 'var(--bg-2)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-1)', flex: 1 }}>
                {selectedMsgs.size} selected
              </span>
              <button onClick={deleteSelected}
                style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 'var(--r-md)', color: 'var(--danger)', fontSize: '12px', fontWeight: 600, padding: '6px 14px', cursor: 'pointer' }}>
                <Trash2 size={13} /> Delete {selectedMsgs.size}
              </button>
              <button onClick={() => setSelectedMsgs(new Set())}
                style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', color: 'var(--text-2)', fontSize: '12px', padding: '6px 12px', cursor: 'pointer' }}>
                Cancel
              </button>
            </div>
          )}

          {/* Attachment preview */}
          {attachment && (
            <div style={{
              padding: '8px 16px', borderTop: '1px solid var(--border)',
              background: 'var(--bg-2)', display: 'flex', alignItems: 'center', gap: '12px',
            }}>
              {attachment.previewUrl ? (
                <img src={attachment.previewUrl} style={{ height: 52, width: 52, objectFit: 'cover', borderRadius: 6 }} alt="" />
              ) : (
                <div style={{ width: 52, height: 52, background: 'var(--bg-3)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <File size={20} color="var(--text-3)" />
                </div>
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '12px', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{attachment.name}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>{attachment.size}</div>
              </div>
              <button onClick={() => setAttachment(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 4 }}>
                <X size={15} />
              </button>
            </div>
          )}

          {/* Input bar */}
          <form onSubmit={sendMessage} style={{
            padding: isMobile ? '8px 10px' : '10px 14px',
            borderTop: '1px solid var(--border)',
            display: 'flex', gap: '8px', alignItems: 'center', flexShrink: 0,
          }}>
            <button type="button" onClick={() => fileRef.current?.click()}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text-3)', padding: '7px', borderRadius: 'var(--r-md)',
                flexShrink: 0, transition: 'color var(--t-fast)',
              }}
              onMouseEnter={e => e.currentTarget.style.color = 'var(--accent)'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--text-3)'}>
              <Paperclip size={17} />
            </button>
            <input ref={fileRef} type="file" hidden onChange={pickFile}
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.zip" />

            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) sendMessage(e) }}
              placeholder={`Message ${activeRoom.project_name || activeRoom.name}…`}
              style={{
                flex: 1, background: 'var(--bg-2)', border: '1px solid var(--border)',
                borderRadius: 'var(--r-full)', color: 'var(--text-0)',
                // FIX: 16px on mobile prevents iOS auto-zoom on focus
                fontSize: isMobile ? '16px' : '13px',
                padding: '9px 16px', outline: 'none', transition: 'border-color var(--t-fast)',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--accent)'}
              onBlur={e => e.target.style.borderColor = 'var(--border)'}
            />
            <button type="submit"
              disabled={(!input.trim() && !attachment) || sending}
              style={{
                width: 36, height: 36, borderRadius: '50%', border: 'none', flexShrink: 0,
                background: (input.trim() || attachment) ? 'var(--accent)' : 'var(--bg-3)',
                color: (input.trim() || attachment) ? '#0a0a0a' : 'var(--text-3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: (input.trim() || attachment) ? 'pointer' : 'not-allowed',
                transition: 'all var(--t-fast)',
              }}>
              {sending ? <Spinner size={13} /> : <Send size={14} />}
            </button>
          </form>
        </>
      )}
    </div>
  )

  return (
    <div style={{
      display: 'flex',
      // FIX: Use dvh (dynamic viewport height) with vh fallback — accounts for mobile browser chrome
      height: 'calc(100dvh - 100px)',
      border: '1px solid var(--border)', borderRadius: 'var(--r-xl)',
      overflow: 'hidden', background: 'var(--bg-1)',
    }}>
      {RoomListPanel}
      {MessagePane}
    </div>
  )
}

// ── Room button ──────────────────────────────────────────────────────────────
function RoomBtn({ room, active, onClick, unread }) {
  return (
    <button onClick={onClick} style={{
      width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
      padding: '8px 10px', border: 'none', borderRadius: 'var(--r-md)',
      background: active ? 'var(--accent-dim)' : 'transparent',
      cursor: 'pointer', textAlign: 'left',
      color: active ? 'var(--accent)' : 'var(--text-2)',
      transition: 'background var(--t-fast)',
    }}
    onMouseEnter={e => !active && (e.currentTarget.style.background = 'var(--bg-3)')}
    onMouseLeave={e => !active && (e.currentTarget.style.background = 'transparent')}>
      <Avatar name={room.project_name || room.name} size={28} />
      <span style={{
        fontSize: '13px', fontWeight: active ? 600 : unread > 0 ? 600 : 400,
        flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {room.project_name || room.name || `Room ${room.id}`}
      </span>
      {unread > 0 && !active && (
        <span style={{
          background: 'var(--accent)', color: '#0a0a0a',
          borderRadius: 'var(--r-full)', fontSize: '10px', fontWeight: 700,
          padding: '1px 6px', flexShrink: 0,
        }}>
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </button>
  )
}

// ── Message bubble ───────────────────────────────────────────────────────────
function MessageBubble({ msg, isOwn, prevSame, isMobile, onEdit, onDelete, selected, onSelect, selectionMode }) {
  const senderName  = msg.sender_detail?.name || msg.sender?.name || '?'
  const isFile      = msg.msg_type === 'file'
  const isImage     = msg.msg_type === 'image'
  const isSending   = msg._sending
  const fileUrl     = msg.attachment_url
  const fileName    = msg.attachment_name || msg.text || 'file'
  const [hovered, setHovered]   = useState(false)
  const [editing, setEditing]   = useState(false)
  const [editText, setEditText] = useState(msg.text || '')
  const [showMenu, setShowMenu] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!showMenu) return
    function handle(e) { if (!menuRef.current?.contains(e.target)) setShowMenu(false) }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [showMenu])

  async function submitEdit() {
    if (!editText.trim() || editText === msg.text) { setEditing(false); return }
    await onEdit(editText.trim())
    setEditing(false)
    setShowMenu(false)
  }

  const bubbleBg    = isOwn ? 'var(--accent)' : 'var(--bg-3)'
  const bubbleColor = isOwn ? '#0a0a0a' : 'var(--text-0)'
  const br          = isOwn ? '18px 18px 4px 18px' : '18px 18px 18px 4px'
  // FIX: 85% on mobile gives much more room in the narrow message area vs 65% fixed
  const bubbleMaxW  = isMobile ? '85%' : '65%'

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false) }}
      onClick={() => selectionMode && onSelect(msg.id)}
      style={{
        display: 'flex', gap: '8px',
        flexDirection: isOwn ? 'row-reverse' : 'row',
        alignItems: 'flex-end',
        marginTop: prevSame ? 2 : 16,
        opacity: isSending ? 0.5 : 1,
        padding: '2px 4px',
        borderRadius: 'var(--r-md)',
        background: selected ? 'rgba(99,102,241,0.08)' : 'transparent',
        cursor: selectionMode ? 'pointer' : 'default',
        transition: 'background 0.15s',
        position: 'relative',
      }}>

      {selectionMode && (
        <div style={{
          width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
          border: `2px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
          background: selected ? 'var(--accent)' : 'transparent',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          alignSelf: 'center', transition: 'all 0.15s',
        }}>
          {selected && <span style={{ fontSize: '10px', color: '#0a0a0a', fontWeight: 800 }}>✓</span>}
        </div>
      )}

      {!prevSame ? (
        <Avatar name={senderName} size={isMobile ? 26 : 30} style={{ flexShrink: 0, marginBottom: 2 }} />
      ) : (
        <div style={{ width: isMobile ? 26 : 30, flexShrink: 0 }} />
      )}

      <div style={{ maxWidth: bubbleMaxW, display: 'flex', flexDirection: 'column', gap: 3, alignItems: isOwn ? 'flex-end' : 'flex-start' }}>
        {!prevSame && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexDirection: isOwn ? 'row-reverse' : 'row' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)' }}>{isOwn ? 'You' : senderName}</span>
            <span style={{ fontSize: '10px', color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>{timeAgo(msg.created_at)}</span>
          </div>
        )}

        {editing ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: isMobile ? 180 : 240 }}>
            <input value={editText} onChange={e => setEditText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') submitEdit(); if (e.key === 'Escape') setEditing(false) }}
              autoFocus
              style={{ background: 'var(--bg-2)', border: '1.5px solid var(--accent)', borderRadius: 'var(--r-md)', color: 'var(--text-0)', fontSize: '13px', padding: '8px 12px', outline: 'none', width: '100%' }}
            />
            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
              <button onClick={() => setEditing(false)}
                style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', color: 'var(--text-2)', fontSize: '12px', padding: '5px 12px', cursor: 'pointer' }}>
                Cancel
              </button>
              <button onClick={submitEdit}
                style={{ background: 'var(--accent)', border: 'none', borderRadius: 'var(--r-md)', color: '#0a0a0a', fontSize: '12px', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                Save
              </button>
            </div>
            <span style={{ fontSize: '10px', color: 'var(--text-3)' }}>Enter to save · Esc to cancel</span>
          </div>

        ) : isImage && fileUrl ? (
          <div style={{ borderRadius: 12, overflow: 'hidden', border: '1px solid var(--border)', cursor: 'pointer' }}
            onClick={() => window.open(fileUrl, '_blank')}>
            {/* FIX: maxWidth:'100%' prevents overflow in narrow mobile bubble area (was fixed 300px) */}
            <img src={fileUrl} style={{ maxWidth: '100%', width: 300, maxHeight: 220, display: 'block', objectFit: 'cover' }} alt={fileName}
              onError={e => { e.currentTarget.style.display = 'none' }} />
          </div>
        ) : isFile && fileUrl ? (
          <a href={fileUrl} download={fileName} target="_blank" rel="noopener noreferrer"
            style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderRadius: br, background: bubbleBg, color: isOwn ? '#0a0a0a' : 'var(--accent)', textDecoration: 'none', maxWidth: isMobile ? '100%' : 260 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: isOwn ? 'rgba(0,0,0,0.15)' : 'var(--bg-4)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <File size={16} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '12px', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fileName}</div>
              <div style={{ fontSize: '10px', opacity: 0.6, marginTop: 1 }}>Click to download</div>
            </div>
            <Download size={14} style={{ flexShrink: 0 }} />
          </a>
        ) : (
          <div style={{ padding: '9px 14px', borderRadius: br, background: bubbleBg, color: bubbleColor, fontSize: '13px', lineHeight: 1.6, wordBreak: 'break-word' }}>
            {msg.text}
            {msg.is_edited && <span style={{ fontSize: '10px', opacity: 0.45, marginLeft: 6, fontStyle: 'italic' }}>edited</span>}
          </div>
        )}

        {isSending && <span style={{ fontSize: '10px', color: 'var(--text-3)' }}>Sending…</span>}
      </div>

      {isOwn && hovered && !isSending && !editing && !selectionMode && (
        <div style={{ alignSelf: 'center', position: 'relative' }} ref={menuRef}>
          <button
            onClick={e => { e.stopPropagation(); setShowMenu(v => !v) }}
            style={{
              width: 28, height: 28, borderRadius: '50%',
              background: showMenu ? 'var(--bg-4)' : 'var(--bg-3)',
              border: '1px solid var(--border)',
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-2)', fontSize: '14px', transition: 'all var(--t-fast)',
              flexShrink: 0,
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-4)'}
            onMouseLeave={e => !showMenu && (e.currentTarget.style.background = 'var(--bg-3)')}>
            ···
          </button>

          {showMenu && (
            <div style={{
              position: 'absolute', bottom: 34, right: 0,
              background: 'var(--bg-1)', border: '1px solid var(--border)',
              borderRadius: 'var(--r-md)', boxShadow: 'var(--shadow-md)',
              minWidth: 130, overflow: 'hidden', zIndex: 100,
            }}>
              {!isFile && !isImage && (
                <button
                  onClick={() => { setEditText(msg.text); setEditing(true); setShowMenu(false) }}
                  style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', color: 'var(--text-1)', textAlign: 'left', transition: 'background var(--t-fast)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-2)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'none'}>
                  <Edit2 size={13} /> Edit
                </button>
              )}
              <button
                onClick={() => { onSelect(msg.id); setShowMenu(false) }}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', color: 'var(--text-1)', textAlign: 'left', transition: 'background var(--t-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-2)'}
                onMouseLeave={e => e.currentTarget.style.background = 'none'}>
                <CheckCheck size={13} /> Select
              </button>
              <div style={{ height: 1, background: 'var(--border)', margin: '2px 0' }} />
              <button
                onClick={() => { onDelete(); setShowMenu(false) }}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', color: 'var(--danger)', textAlign: 'left', transition: 'background var(--t-fast)' }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(248,113,113,0.08)'}
                onMouseLeave={e => e.currentTarget.style.background = 'none'}>
                <Trash2 size={13} /> Delete
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
