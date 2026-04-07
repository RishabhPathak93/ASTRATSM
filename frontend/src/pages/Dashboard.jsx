import React from 'react'
import { useQueries } from '@tanstack/react-query'
import {
  Activity, AlertTriangle, Bell, BriefcaseBusiness, CheckCircle2, Clock3,
  FolderKanban, Gauge, ShieldCheck, Users,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { approvalsApi, authApi, clientsApi, notificationsApi, projectsApi, resourcesApi, timelinesApi } from '@/api/index.js'
import { Badge, Card, ProgressBar, StatCard } from '@/components/ui/index.jsx'
import { useAuthStore } from '@/stores/authStore.js'

const PIE_COLORS = ['#237227', '#3f7f58', '#6d8fa0', '#7f9498', '#d97706']
const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const STATUS_LABELS = {
  planning: 'Planning',
  in_progress: 'In Progress',
  review: 'Review',
  on_hold: 'On Hold',
  completed: 'Completed',
}

const safeList = (response) => response?.data?.results || response?.data || []
const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0)
const sumHours = (entries) => entries.reduce((sum, item) => sum + Number(item.hours || 0), 0)
const queryList = (fn) => async () => {
  try {
    return safeList(await fn())
  } catch {
    return []
  }
}

function hours(value) {
  return `${Number(value || 0).toFixed(0)}h`
}

function workingDaysBetween(startDate, endDate) {
  if (!startDate || !endDate) return 0
  const start = new Date(startDate)
  const end = new Date(endDate)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return 0

  let count = 0
  const cursor = new Date(start)
  while (cursor <= end) {
    const day = cursor.getDay()
    if (day !== 0 && day !== 6) count += 1
    cursor.setDate(cursor.getDate() + 1)
  }
  return count
}

function getProjectPlannedHours(project) {
  const workingDays = workingDaysBetween(project.start_date, project.end_date)
  const resourceCount = Math.max(Number(project.resource_count || 0), 1)
  const formulaHours = workingDays * 8 * resourceCount
  return formulaHours || Number(project.hours || project.estimated_hours || 0)
}

function weekdayIndex(dateValue) {
  const date = new Date(dateValue)
  if (Number.isNaN(date.getTime())) return null
  return (date.getDay() + 6) % 7
}

function buildWeeklySeries(timeEntries, activeProjects) {
  const base = WEEKDAY_LABELS.map((label) => ({ label, submitted: 0, approved: 0, pending: 0, target: 0 }))
  const submittedHours = sumHours(timeEntries)
  const baseTarget = Math.max(submittedHours, activeProjects.length * 8) / 5

  base.forEach((item, index) => {
    item.target = Number(index < 5 ? baseTarget.toFixed(1) : 0)
  })

  timeEntries.forEach((entry) => {
    const index = weekdayIndex(entry.date)
    if (index == null) return
    const hoursValue = Number(entry.hours || 0)
    base[index].submitted += hoursValue
    if (entry.approved) {
      base[index].approved += hoursValue
    } else {
      base[index].pending += hoursValue
    }
  })

  return base.map((item) => ({
    ...item,
    submitted: Number(item.submitted.toFixed(1)),
    approved: Number(item.approved.toFixed(1)),
    pending: Number(item.pending.toFixed(1)),
  }))
}

function buildProjectStatusMix(projects) {
  const counts = {
    planning: 0,
    in_progress: 0,
    review: 0,
    on_hold: 0,
    completed: 0,
  }
  projects.forEach((project) => {
    const key = project.status || 'planning'
    if (Object.prototype.hasOwnProperty.call(counts, key)) {
      counts[key] += 1
    }
  })
  return Object.entries(counts)
    .map(([key, value]) => ({ name: STATUS_LABELS[key], value }))
    .filter((item) => item.value > 0)
}

function buildCapacityMix(resources) {
  const overloaded = resources.filter((item) => Number(item.availability || 0) <= 20).length
  const allocated = resources.filter((item) => Number(item.active_project_count || 0) > 0 && Number(item.availability || 0) > 20).length
  const bench = resources.filter((item) => Number(item.active_project_count || 0) === 0).length
  return [
    { name: 'Overloaded', value: overloaded, fill: '#ef4444' },
    { name: 'Allocated', value: allocated, fill: '#237227' },
    { name: 'Bench', value: bench, fill: '#6d8fa0' },
  ].filter((item) => item.value > 0)
}

function getRoleCopy(role, name) {
  const firstName = name?.split(' ')[0] || 'Team'
  const map = {
    admin: {
      title: `Executive control for ${firstName}`,
      text: 'Monitor planned effort, team utilization, overdue work, and approval queues across the workspace.',
    },
    manager: {
      title: `Delivery view for ${firstName}`,
      text: 'Track your portfolio, assigned team hours, approval backlog, and delivery pressure from one place.',
    },
    resource: {
      title: `Execution board for ${firstName}`,
      text: 'Review assigned effort, logged hours, pending approvals, and project momentum for the current cycle.',
    },
    client: {
      title: `Project visibility for ${firstName}`,
      text: 'Follow active work, delivery status, progress confidence, and recent activity on your projects.',
    },
  }
  return map[role] || map.resource
}

function DashboardSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
      <div className="skeleton" style={{ height: 220, borderRadius: 'var(--r-xl)' }} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 'var(--sp-4)' }}>
        {[1, 2, 3, 4].map((item) => <div key={item} className="skeleton" style={{ height: 150 }} />)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--sp-4)' }}>
        <div className="skeleton" style={{ height: 340 }} />
        <div className="skeleton" style={{ height: 340 }} />
      </div>
    </div>
  )
}

function PanelTitle({ title, sub, badge }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
      <div>
        <h3 style={{ fontSize: '1rem', fontWeight: 800 }}>{title}</h3>
        {sub && <p style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: 4 }}>{sub}</p>}
      </div>
      {badge}
    </div>
  )
}

function InsightRow({ label, value, hint, tone = 'var(--accent)' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--sp-3)', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
      <div>
        <div style={{ fontSize: '13px', fontWeight: 700 }}>{label}</div>
        <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: 3 }}>{hint}</div>
      </div>
      <div style={{ fontSize: '13px', fontWeight: 800, color: tone }}>{value}</div>
    </div>
  )
}

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user)
  const role = user?.role || 'resource'
  const userReady = !!user

  const dashboardQueryOptions = { staleTime: 60_000, refetchOnWindowFocus: false, refetchOnReconnect: false }

  const results = useQueries({
    queries: [
      { queryKey: ['dashboard-projects', role], queryFn: queryList(() => projectsApi.list({ page_size: 500 })), enabled: userReady, ...dashboardQueryOptions },
      { queryKey: ['dashboard-timelines', role], queryFn: queryList(() => timelinesApi.list({ page_size: 500 })), enabled: userReady, ...dashboardQueryOptions },
      { queryKey: ['dashboard-resources', role], queryFn: queryList(() => resourcesApi.list({ page_size: 500 })), enabled: userReady && role !== 'client', ...dashboardQueryOptions },
      { queryKey: ['dashboard-clients', role], queryFn: queryList(() => clientsApi.list({ page_size: 500 })), enabled: userReady && role !== 'resource', ...dashboardQueryOptions },
      { queryKey: ['dashboard-notifications', role], queryFn: queryList(() => notificationsApi.list()), enabled: userReady, ...dashboardQueryOptions },
      { queryKey: ['dashboard-approvals', role], queryFn: queryList(() => approvalsApi.list({ page_size: 50, status: 'pending' })), enabled: userReady && (role === 'admin' || role === 'manager'), ...dashboardQueryOptions },
      { queryKey: ['dashboard-users', role], queryFn: queryList(() => authApi.users({ page_size: 500 })), enabled: userReady && role === 'admin', ...dashboardQueryOptions },
      { queryKey: ['dashboard-time-entries', role], queryFn: queryList(() => resourcesApi.timeEntries({ page_size: 500 })), enabled: userReady && role !== 'client', ...dashboardQueryOptions },
    ],
  })

  const isLoading = !userReady || results.some((item) => item.isLoading)
  if (isLoading) return <DashboardSkeleton />

  const [
    projectsResult,
    timelinesResult,
    resourcesResult,
    clientsResult,
    notificationsResult,
    approvalsResult,
    usersResult,
    timeEntriesResult,
  ] = results

  const projects = projectsResult.data || []
  const timelines = timelinesResult.data || []
  const resources = resourcesResult.data || []
  const clients = clientsResult.data || []
  const notifications = notificationsResult.data || []
  const approvals = approvalsResult.data || []
  const users = usersResult.data || []
  const timeEntries = timeEntriesResult.data || []

  const plannedHours = projects.reduce((sum, item) => sum + getProjectPlannedHours(item), 0)
  const approvedEntries = timeEntries.filter((item) => item.approved)
  const pendingEntries = timeEntries.filter((item) => !item.approved)
  const consumedHours = sumHours(timeEntries)
  const approvedHours = sumHours(approvedEntries)
  const pendingHours = sumHours(pendingEntries)
  const myEntries = timeEntries.filter((item) => item.resource_user === user?.id || item.user === user?.id || item.resource?.user === user?.id)
  const myHours = sumHours(myEntries)
  const myApprovedHours = sumHours(myEntries.filter((item) => item.approved))
  const activeProjects = projects.filter((item) => item.status !== 'completed')
  const delayedProjects = projects.filter((item) => item.is_delayed || item.status === 'on_hold' || Number(item.progress || 0) < 40)
  const overdueTimelines = timelines.filter((item) => item.is_delayed || (item.status !== 'completed' && Number(item.progress || 0) < 100))
  const completedProjects = projects.filter((item) => item.status === 'completed' || Number(item.progress || 0) >= 100)
  const unreadCount = notifications.filter((item) => !item.is_read).length
  const activeResources = resources.filter((item) => Number(item.active_project_count || 0) > 0)
  const visibleHours = role === 'admin' ? approvedHours : role === 'resource' ? myHours : consumedHours
  const utilization = pct(visibleHours, plannedHours || 1)
  const approvalRate = pct(approvedHours, consumedHours || 1)
  const deliveryScore = clamp(100 - delayedProjects.length * 12 + completedProjects.length * 5, 28, 98)
  const weeklySeries = buildWeeklySeries(timeEntries, activeProjects)
  const healthMix = buildProjectStatusMix(projects)
  const capacityMix = buildCapacityMix(resources)
  const roleCopy = getRoleCopy(role, user?.name)

  const statsByRole = {
    admin: [
      { label: 'Planned Hours', value: hours(plannedHours), sub: `${projects.length} total projects`, icon: Clock3, accent: 'var(--accent)' },
      { label: 'Approved Hours', value: hours(approvedHours), sub: `${approvalRate}% of submitted time approved`, icon: ShieldCheck, accent: 'var(--info)' },
      { label: 'Delayed Work', value: delayedProjects.length, sub: `${overdueTimelines.length} timelines need action`, icon: AlertTriangle, accent: 'var(--danger)' },
      { label: 'Workspace Users', value: users.length || resources.length, sub: `${activeResources.length} currently allocated`, icon: Users, accent: 'var(--success)' },
    ],
    manager: [
      { label: 'Portfolio Projects', value: activeProjects.length, sub: `${completedProjects.length} completed`, icon: BriefcaseBusiness, accent: 'var(--accent)' },
      { label: 'Submitted Hours', value: hours(consumedHours), sub: `${hours(pendingHours)} waiting approval`, icon: Clock3, accent: 'var(--info)' },
      { label: 'Approval Queue', value: approvals.length, sub: `${approvalRate}% timesheet approval rate`, icon: CheckCircle2, accent: 'var(--success)' },
      { label: 'Delivery Risk', value: delayedProjects.length, sub: `${deliveryScore}% health score`, icon: Gauge, accent: 'var(--danger)' },
    ],
    resource: [
      { label: 'Assigned Hours', value: hours(plannedHours), sub: `${activeProjects.length} active assignments`, icon: FolderKanban, accent: 'var(--accent)' },
      { label: 'Logged Hours', value: hours(myHours || consumedHours), sub: `${hours(myApprovedHours)} approved by manager`, icon: Clock3, accent: 'var(--info)' },
      { label: 'Unread Updates', value: unreadCount, sub: `${hours(Math.max(myHours - myApprovedHours, 0))} still pending approval`, icon: Bell, accent: 'var(--success)' },
      { label: 'At-Risk Items', value: delayedProjects.length, sub: 'Delays or low progress projects', icon: AlertTriangle, accent: 'var(--danger)' },
    ],
    client: [
      { label: 'Visible Projects', value: projects.length, sub: `${clients.length} linked client account(s)`, icon: FolderKanban, accent: 'var(--accent)' },
      { label: 'Delivery Health', value: `${deliveryScore}%`, sub: `${completedProjects.length} completed initiatives`, icon: Gauge, accent: 'var(--success)' },
      { label: 'Recent Alerts', value: unreadCount, sub: 'Unread updates from delivery team', icon: Bell, accent: 'var(--info)' },
      { label: 'Delayed Work', value: delayedProjects.length, sub: 'Projects needing attention', icon: AlertTriangle, accent: 'var(--danger)' },
    ],
  }

  const queueItems = [
    { label: 'Approval queue', value: approvals.length, hint: 'Pending changes that need review.', tone: 'var(--accent)' },
    { label: 'Unread notifications', value: unreadCount, hint: 'Operational updates waiting for attention.', tone: 'var(--info)' },
    { label: 'Delayed projects', value: delayedProjects.length, hint: 'Projects showing risk or stalled progress.', tone: 'var(--danger)' },
    { label: 'Utilization', value: `${utilization}%`, hint: 'Planned hours versus visible delivered effort.', tone: 'var(--success)' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)', maxWidth: 1440, margin: '0 auto' }}>
      <Card className="animate-rise-in card-hover mobile-center-card" style={{ padding: 'var(--sp-8)', borderRadius: 'var(--r-xl)', background: 'linear-gradient(135deg, rgba(35,114,39,0.16), rgba(19,36,64,0.95) 58%, rgba(59,73,83,0.96))' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--sp-6)', alignItems: 'stretch' }}>
          <div className="mobile-center-stack" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
            <Badge color="var(--accent)">Enterprise Timesheet Workspace</Badge>
            <div>
              <h1 style={{ fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.03em' }}>{roleCopy.title}</h1>
              <p style={{ fontSize: '14px', color: 'var(--text-1)', marginTop: 10, maxWidth: 760 }}>{roleCopy.text}</p>
            </div>
            <div className="mobile-center-actions" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-3)' }}>
              <Badge color="var(--success)">{activeProjects.length} active projects</Badge>
              <Badge color="var(--info)">{hours(visibleHours)} visible hours</Badge>
              <Badge color="var(--danger)">{delayedProjects.length} at risk</Badge>
            </div>
          </div>
          <div style={{ display: 'grid', gap: 'var(--sp-3)', alignContent: 'start' }}>
            <div style={{ padding: '18px 20px', borderRadius: 'var(--r-lg)', background: 'rgba(0,0,0,0.22)', border: '1px solid rgba(191,198,196,0.12)' }}>
              <div style={{ fontSize: '11px', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-2)' }}>Delivery Score</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: 8 }}>{deliveryScore}%</div>
              <div style={{ marginTop: 12 }}><ProgressBar value={deliveryScore} color="var(--accent)" showLabel /></div>
            </div>
            <div style={{ padding: '18px 20px', borderRadius: 'var(--r-lg)', background: 'rgba(0,0,0,0.22)', border: '1px solid rgba(191,198,196,0.12)' }}>
              <div style={{ fontSize: '11px', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-2)' }}>{role === 'admin' ? 'Approved Utilization' : 'Resource Utilization'}</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: 8 }}>{utilization}%</div>
              <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: 6 }}>{hours(visibleHours)} of {hours(plannedHours || visibleHours)}</div>
            </div>
          </div>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--sp-4)' }}>
        {(statsByRole[role] || statsByRole.resource).map((item, index) => (
          <div key={item.label} style={{ animationDelay: `${index * 50}ms` }} className="animate-rise-in">
            <StatCard {...item} />
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--sp-4)', alignItems: 'start' }}>
        <Card className="card-hover animate-rise-in" style={{ minHeight: 360 }}>
          <PanelTitle
            title="Worklog Flow Through The Week"
            sub="Real submitted, approved, and pending hours grouped by weekday from your visible entries."
            badge={<Badge color="var(--info)">Live data</Badge>}
          />
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeklySeries}>
                <CartesianGrid stroke="rgba(191,198,196,0.08)" vertical={false} />
                <XAxis dataKey="label" stroke="var(--text-3)" tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-3)" tickLine={false} axisLine={false} width={34} />
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid rgba(191,198,196,0.14)', background: '#1a2c43', color: '#f6faf8' }} />
                <Legend />
                <Bar dataKey="approved" name="Approved" stackId="hours" fill="#237227" radius={[8, 8, 0, 0]} />
                <Bar dataKey="pending" name="Pending" stackId="hours" fill="#d97706" radius={[8, 8, 0, 0]} />
                <Area type="monotone" dataKey="target" name="Target" stroke="#6d8fa0" fillOpacity={0} strokeWidth={3} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <div style={{ display: 'grid', gap: 'var(--sp-4)' }}>
          <Card className="card-hover animate-rise-in">
            <PanelTitle title="Project Status Mix" sub="How the visible portfolio is distributed right now." badge={<Badge color="var(--accent)">Portfolio</Badge>} />
            <div style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={healthMix} dataKey="value" nameKey="name" innerRadius={58} outerRadius={86} paddingAngle={5}>
                    {healthMix.map((entry, index) => <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid rgba(191,198,196,0.14)', background: '#1a2c43', color: '#f6faf8' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {role !== 'client' && (
            <Card className="card-hover animate-rise-in">
              <PanelTitle title="Resource Capacity" sub="A clearer view of overloaded, allocated, and bench capacity across visible resources." badge={<Badge color="var(--success)">Resources</Badge>} />
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={capacityMix} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
                    <CartesianGrid stroke="rgba(191,198,196,0.08)" horizontal={false} />
                    <XAxis type="number" stroke="var(--text-3)" tickLine={false} axisLine={false} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" stroke="var(--text-3)" tickLine={false} axisLine={false} width={80} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid rgba(191,198,196,0.14)', background: '#1a2c43', color: '#f6faf8' }} />
                    <Bar dataKey="value" name="Resources" radius={[0, 10, 10, 0]}>
                      {capacityMix.map((item) => <Cell key={item.name} fill={item.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--sp-4)', alignItems: 'start' }}>
        <Card className="card-hover animate-rise-in">
          <PanelTitle title="Operational Focus" sub="The most important queues and effort indicators for this cycle." badge={<Badge color="var(--danger)">Priority</Badge>} />
          <div>
            {queueItems.map((item) => (
              <InsightRow key={item.label} {...item} />
            ))}
          </div>
        </Card>

        <Card className="card-hover animate-rise-in">
          <PanelTitle title="Recent Notifications" sub="Unread signals and communication pressure across the workspace." badge={<Badge color="var(--info)">Live</Badge>} />
          <div style={{ display: 'grid', gap: 'var(--sp-3)' }}>
            {notifications.slice(0, 5).map((item, index) => (
              <div key={item.id || index} style={{ padding: '14px 16px', borderRadius: 'var(--r-lg)', background: 'var(--surface-1)', border: '1px solid var(--border)' }} className="animate-fade-in">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--sp-3)' }}>
                  <div style={{ fontSize: '13px', fontWeight: 700 }}>{item.title || 'Workspace update'}</div>
                  {!item.is_read && <span className="badge-pulse" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0 }} />}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: 6, lineHeight: 1.55 }}>{item.message || 'No message body available.'}</div>
              </div>
            ))}
            {notifications.length === 0 && (
              <div style={{ padding: '26px 18px', borderRadius: 'var(--r-lg)', border: '1px dashed var(--border-light)', textAlign: 'center', color: 'var(--text-2)' }}>
                <Activity size={18} style={{ marginBottom: 8 }} />
                No alerts are waiting right now.
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
