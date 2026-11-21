import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity, Bell, ChartNoAxesCombined, ChevronRight, CircleAlert, DoorOpen, Gauge, LayoutDashboard,
  Leaf, Menu, ReceiptText, X, Zap,
} from 'lucide-react'
import '@fontsource-variable/inter'
import '@fontsource-variable/manrope'
import './styles.css'
import { useApi } from './api'
import {
  AlertList, AlertState, ChartKey, Empty, ErrorNotice, Metric, PageHeader, PanelHeading, PeriodSwitch,
  ReadingTrend, Recommendations, Result, RoomBarChart, RoomStatus, RoomTile, Select, Source, Trend,
} from './components'
import { fullTime, formatTime, hasRoomData, roomStyles, showCost, showNumber } from './format'

const pages = [
  ['overview', 'Overview', LayoutDashboard],
  ['analytics', 'Energy Analytics', ChartNoAxesCombined],
  ['rooms', 'Room Monitoring', DoorOpen],
  ['alerts', 'Alerts', Bell],
  ['carbon', 'Carbon Footprint', Leaf],
]
const recentDescription = 'Latest 60 saved readings from the past 24 hours · IST'

function readingsPath(room) {
  return `/readings?room_id=${encodeURIComponent(room.id)}&limit=60`
}

function getRoute() {
  const [view, room] = (location.hash.slice(1) || 'overview').split('/')
  return { view: pages.some(([id]) => id === view) ? view : 'overview', room }
}

function Sidebar({ view, config, alertCount, expanded, close }) {
  return <>
    {expanded && <button className="nav-overlay" onClick={close} aria-label="Close navigation" />}
    <aside id="sidebar" className={`sidebar ${expanded ? 'open' : ''}`}>
      <a className="brand" href="#overview" onClick={close}>
        <span className="brand-mark"><Leaf size={25} strokeWidth={2.4} /></span>
        <span><strong>EcoSync<span>.</span></strong><small>Campus energy monitor</small></span>
      </a>
      <div className="sidebar-divider" />
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">
        {pages.map(([id, label, Icon]) => <a key={id} href={`#${id}`} onClick={close}
          aria-current={view === id ? 'page' : undefined}>
          <Icon size={19} strokeWidth={1.8} /><span>{label}</span>
          {id === 'alerts' && alertCount > 0 && <small>{alertCount}</small>}
        </a>)}
      </nav>
      <div className="sidebar-bottom"><Source config={config} /></div>
    </aside>
  </>
}

function RoomBreakdown({ rooms, analytics }) {
  const entries = Object.fromEntries((analytics?.by_room || []).filter(room => hasRoomData(analytics, room))
    .map(room => [room.room_id, room.energy_kwh]))
  const total = analytics?.totals.energy_kwh
  return <section className="panel room-breakdown">
    <PanelHeading title="Room breakdown" description="Live load and share of today’s energy" />
    <div className="room-rows">{rooms.map(room => {
      const share = total > 0 && entries[room.id] != null ? entries[room.id] / total * 100 : null
      const live = !room.stale
      return <a key={room.id} href={`#rooms/${room.id}`} className="room-row">
        <RoomTile room={room} />
        <div className="room-row-center"><strong>{room.name}</strong>
          <small>{live ? room.location : room.latest ? 'Last reading is stale' : 'Waiting for readings'}</small></div>
        <div className="room-row-power"><strong>{showNumber(live ? room.latest?.power_kw : null)}{live && ' kW'}</strong>
          <small>{share != null ? `${showNumber(share, 0)}% of usage` : '—'}</small></div>
        <span className="room-progress" aria-hidden="true"><i style={{ width: `${share ?? 0}%`, background: roomStyles[room.id].color }} /></span>
      </a>
    })}</div>
    <a className="panel-link" href="#rooms">View room monitoring</a>
  </section>
}

function DashboardMetrics({ rooms, today, config }) {
  const totals = today?.has_data ? today.totals : null
  const tariff = today?.tariff_inr_per_kwh ?? config?.tariff_inr_per_kwh
  return <div className="metric-grid">
    <Metric icon={Zap} label="Current power" value={showNumber(rooms.current_power_kw, 2, 2)} unit="kW"
      detail={`${rooms.reporting_rooms} of ${rooms.rooms.length} rooms reporting`} />
    <Metric icon={Activity} label="Energy today" value={showNumber(totals?.energy_kwh, 3, 2)} unit="kWh"
      detail="Since midnight IST" tone="blue" />
    <Metric icon={ReceiptText} label="Estimated bill" value={showCost(totals?.cost_inr)}
      detail={tariff != null ? `₹${showNumber(tariff)} per kWh · today` : 'Today’s energy charge'} tone="violet" />
    <Metric icon={Leaf} label="Estimated emissions" value={showNumber(totals?.carbon_kg, 3, 2)} unit="kg CO₂"
      detail="From today’s recorded energy" tone="mint" />
  </div>
}

function Overview({ rooms, config, alerts, names }) {
  const [period, setPeriod] = useState('recent')
  const [roomId, setRoomId] = useState('')
  const recent = period === 'recent'
  const room = rooms.rooms.find(item => item.id === roomId) ||
    rooms.rooms.find(item => item.latest) || rooms.rooms[0]
  const readings = useApi(recent ? readingsPath(room) : null)
  const today = useApi('/analytics?period=today')
  const otherPeriod = useApi(recent || period === 'today' ? null : `/analytics?period=${period}`)
  const selected = period === 'today' ? today : otherPeriod
  return <>
    <PageHeader title="Energy overview" description="Track campus electricity use, costs, and carbon emissions." date={rooms.as_of} />
    {period !== 'today' && today.error && <ErrorNotice message={today.error} cached={!!today.data} retry={today.retry} />}
    <DashboardMetrics rooms={rooms} today={today.data} config={config} />
    <div className="dashboard-grid">
      <section className="panel usage-panel">
        <PanelHeading title="Energy consumption" description={recent ? recentDescription :
          period === 'today' ? 'Sum of room averages per 30-minute interval · IST' : 'Recorded energy by calendar day · IST'}
          action={<PeriodSwitch value={period} onChange={setPeriod} includeRecent />} />
        {recent ? <>
          <div className="chart-controls">
            <Select label="Choose a room for recent readings" value={room.id} onChange={setRoomId}
              options={rooms.rooms.map(item => [item.id, item.name])} />
            <span>Power · kW</span>
          </div>
          <Result state={readings}>{data =>
            <ReadingTrend readings={data.readings} room={room} maxGapSeconds={config?.max_integration_gap_seconds} />
          }</Result>
        </> : <Result state={selected}>{data => <>
          <ChartKey unit={data.series_unit} name={period === 'today' ? 'Campus power' : 'Campus energy'} />
          <Trend analytics={data} />
        </>}</Result>}
      </section>
      <RoomBreakdown rooms={rooms.rooms} analytics={today.data} />
    </div>
    <div className="dashboard-grid lower-grid">
      <section className="panel">
        <PanelHeading title="Recent alerts" description={alerts.data && `${alerts.data.active.length} active across campus`}
          action={<a className="text-link" href="#alerts">View all</a>} />
        <Result state={alerts}>{data => <AlertList alerts={data.history.slice(0, 3)} names={names} />}</Result>
      </section>
      <section className="panel"><PanelHeading title="Recommendations" description="Actions based on room readings" />
        <Recommendations items={rooms.recommendations} names={names} />
      </section>
    </div>
  </>
}

function DailyTable({ analytics }) {
  return <div className="table-scroll"><table>
    <thead><tr><th scope="col">Date · IST</th><th scope="col">Energy</th><th scope="col">Est. bill</th><th scope="col">Est. emissions</th></tr></thead>
    <tbody>{[...analytics.daily].reverse().map(row => <tr key={row.at}>
      <td>{formatTime(row.at, { weekday: 'short', day: 'numeric', month: 'short' })}</td>
      <td>{row.value == null ? '—' : `${showNumber(row.energy_kwh, 3)} kWh`}</td>
      <td>{row.value == null ? '—' : showCost(row.cost_inr)}</td>
      <td>{row.value == null ? '—' : `${showNumber(row.carbon_kg, 3)} kg CO₂`}</td>
    </tr>)}</tbody>
  </table></div>
}

function Analytics({ rooms }) {
  const [period, setPeriod] = useState('7d')
  const analytics = useApi(`/analytics?period=${period}`)
  return <>
    <PageHeader title="Energy analytics" description="Compare electricity usage across rooms and track daily consumption.">
      <PeriodSwitch value={period} onChange={setPeriod} />
    </PageHeader>
    <Result state={analytics}>{data => <>
      <div className="dashboard-grid">
        <section className="panel"><PanelHeading title="Consumption by room"
          description={period === 'today' ? 'Average power per 30-minute interval · IST' : 'Recorded energy by calendar day · IST'} />
          <ChartKey rooms={rooms} unit={data.series_unit} /><Trend analytics={data} rooms={rooms} multi />
        </section>
        <section className="panel"><PanelHeading title="Room comparison" description="Total energy in the selected period · kWh" />
          <RoomBarChart analytics={data} rooms={rooms} />
        </section>
      </div>
      <section className="panel"><PanelHeading title="Daily statistics" /><DailyTable analytics={data} /></section>
    </>}</Result>
  </>
}

function Rooms({ rooms, selectedId, config }) {
  const room = rooms.find(item => item.id === selectedId) || rooms[0]
  const [period, setPeriod] = useState('recent')
  const recent = period === 'recent'
  const analytics = useApi(`/analytics?period=${recent ? 'today' : period}&room_id=${room.id}`)
  const readings = useApi(readingsPath(room))
  return <>
    <PageHeader title="Room monitoring" description="Inspect live power, anomaly thresholds, and recent sensor readings." />
    <nav className="room-select-grid" aria-label="Choose a room">{rooms.map(item => (
      <a key={item.id} className="panel room-select" aria-current={item.id === room.id ? 'page' : undefined} href={`#rooms/${item.id}`}>
        <RoomTile room={item} /><div><strong>{item.name}</strong><small>{item.location}</small></div><RoomStatus room={item} />
      </a>
    ))}</nav>
    <div className="room-stat-grid">
      <Metric icon={Zap} label="Current power" value={showNumber(room.stale ? null : room.latest?.power_kw, 2, 2)}
        unit="kW" detail={room.latest ? `Last reading · ${fullTime(room.latest.timestamp)} IST` : 'Awaiting the first reading'} />
      <Metric icon={Gauge} label="Anomaly threshold" value={showNumber(room.threshold_kw)} unit="kW"
        detail="Configured alert limit" tone="amber" />
      <Metric icon={Activity} label={recent || period === 'today' ? 'Energy today' : 'Energy in selected period'}
        value={showNumber(analytics.data?.has_data ? analytics.data.totals.energy_kwh : null, 3)}
        unit="kWh" detail="Integrated from timestamped readings" tone="blue" />
    </div>
    {recent && analytics.error && <ErrorNotice message={analytics.error} cached={!!analytics.data} retry={analytics.retry} />}
    <section className="panel"><PanelHeading title={`${room.name} usage`}
      description={recent ? recentDescription :
        period === 'today' ? 'Average power per 30-minute interval · IST' : 'Recorded energy by calendar day · IST'}
      action={<PeriodSwitch value={period} onChange={setPeriod} includeRecent />} />
      {recent ? <Result state={readings}>{data => <>
        <ChartKey unit="kW" name={room.name} color={roomStyles[room.id].color} />
        <ReadingTrend readings={data.readings} room={room} maxGapSeconds={config?.max_integration_gap_seconds} />
      </>}</Result> : <Result state={analytics}>{data => <>
        <ChartKey unit={data.series_unit} name={room.name} color={roomStyles[room.id].color} />
        <Trend analytics={data} color={roomStyles[room.id].color} />
      </>}</Result>}
    </section>
    <section className="panel"><PanelHeading title="Recent readings" description="Latest 12 readings in the past 24 hours" />
      <Result state={readings}>{data => data.readings.length ? <div className="table-scroll"><table>
        <thead><tr><th scope="col">Timestamp · IST</th><th scope="col">Power draw</th><th scope="col">Current threshold check</th></tr></thead>
        <tbody>{data.readings.slice(0, 12).map(item => <tr key={item.timestamp}><td>{fullTime(item.timestamp)}</td>
          <td>{showNumber(item.power_kw, 3)} kW</td>
          <td>{item.power_kw > room.threshold_kw ? <span className="status warning">Above limit</span> : 'Within limit'}</td>
        </tr>)}</tbody>
      </table></div> : <Empty icon={Activity} title="No recent readings" detail="Start the simulator to see readings for this room." compact />}</Result>
    </section>
  </>
}

function Alerts({ state, rooms, names }) {
  const [filter, setFilter] = useState('all')
  const [room, setRoom] = useState('')
  const filtered = data => (filter === 'active' ? data.active : data.history)
    .filter(item => (!room || item.room_id === room) && (filter !== 'resolved' || item.status === 'resolved'))
  return <>
    <PageHeader title="Anomaly alerts" description="Track abnormal power draw and review when each event recovered." />
    <Result state={state}>{data => <>
      <div className="room-stat-grid">
        <Metric icon={CircleAlert} label="Active alerts" value={showNumber(data.active.length)} tone="amber" detail="Awaiting a normal reading" />
        <Metric icon={Bell} label="Recent events" value={showNumber(data.history.length)} tone="violet" detail="Most recent 50 alert records" />
        <Metric icon={Activity} label="Resolved in history" value={showNumber(data.history.filter(item => item.status === 'resolved').length)}
          detail="Returned to the normal range" />
      </div>
      <section className="panel"><PanelHeading title="Alert history" description="Latest detection events across monitored rooms"
        action={<div className="filters">
          <Select label="Filter by status" value={filter} onChange={setFilter}
            options={ [['all', 'All statuses'], ['active', 'Active'], ['resolved', 'Resolved']] } />
          <Select label="Filter by room" value={room} onChange={setRoom}
            options={ [['', 'All rooms'], ...rooms.map(item => [item.id, item.name])] } />
        </div>} />
        {filtered(data).length ? <div className="table-scroll"><table>
          <thead><tr><th scope="col">Room</th><th scope="col">Detection</th><th scope="col">Peak</th><th scope="col">Started · IST</th>
            <th scope="col">Resolved · IST</th><th scope="col">Status</th></tr></thead>
          <tbody>{filtered(data).map(alert => <tr key={alert.id}>
            <td>{names[alert.room_id]}</td><td>{alert.reasons.map(reason => reason === 'spike' ? 'Spike' : 'Threshold').join(' + ')}</td>
            <td>{showNumber(alert.peak_kw, 3)} kW</td><td>{fullTime(alert.started_at)}</td><td>{fullTime(alert.resolved_at)}</td>
            <td><AlertState alert={alert} /></td>
          </tr>)}</tbody>
        </table></div> : <Empty icon={Bell} title="No matching alerts" detail="New events appear here as readings are processed." />}
      </section>
    </>}</Result>
  </>
}

function Carbon({ rooms, config }) {
  const [period, setPeriod] = useState('7d')
  const analytics = useApi(`/analytics?period=${period}`)
  return <>
    <PageHeader title="Carbon footprint" description="Estimate emissions from recorded campus electricity consumption.">
      <PeriodSwitch value={period} onChange={setPeriod} />
    </PageHeader>
    <Result state={analytics}>{data => <>
      <div className="room-stat-grid">
        <Metric icon={Leaf} label="Estimated emissions" value={showNumber(data.has_data ? data.totals.carbon_kg : null, 3, 2)} unit="kg CO₂"
          detail="For the selected period" />
        <Metric icon={Zap} label="Electricity used" value={showNumber(data.has_data ? data.totals.energy_kwh : null, 3, 2)} unit="kWh"
          detail="Recorded energy in the selected period" tone="blue" />
        <Metric icon={Gauge} label="Emission factor" value={showNumber(data.emission_kg_per_kwh ?? config?.emission_kg_per_kwh, 3)} unit="kg CO₂/kWh"
          detail="Configured electricity intensity" tone="violet" />
      </div>
      <div className="dashboard-grid">
        <section className="panel"><PanelHeading title="Estimated emissions over time" description="Daily emissions from recorded electricity" />
          <ChartKey unit="kg CO₂" name="Estimated emissions" /><Trend analytics={data} metric="carbon" />
        </section>
        <section className="panel"><PanelHeading title="Emissions by room" description="Estimated carbon emissions · kg CO₂" />
          <RoomBarChart analytics={data} rooms={rooms} metric="carbon_kg" unit="kg CO₂" />
        </section>
      </div>
      <section className="panel"><PanelHeading title="How emissions are estimated" />
        <p className="formula">Electricity used (kWh) × emission factor (kg CO₂/kWh) = estimated emissions (kg CO₂)</p>
        <p className="muted-copy">The dashboard applies the configured emission factor to the measured energy for each period.</p>
      </section>
    </>}</Result>
  </>
}

function App() {
  const [route, setRoute] = useState(getRoute)
  const [navOpen, setNavOpen] = useState(false)
  const rooms = useApi('/rooms')
  const config = useApi('/config')
  const alerts = useApi('/alerts')
  useEffect(() => {
    const onHash = () => {
      setRoute(getRoute())
      setNavOpen(false)
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    const dismiss = event => { if (event.key === 'Escape') setNavOpen(false) }
    window.addEventListener('keydown', dismiss)
    return () => window.removeEventListener('keydown', dismiss)
  }, [])

  const label = pages.find(([id]) => id === route.view)[1]
  const count = alerts.data?.active.length
  const online = !rooms.error && rooms.data?.reporting_rooms > 0
  return <div className="shell">
    <a className="skip-link" href="#content" onClick={event => {
      event.preventDefault()
      document.getElementById('content').focus()
    }}>Skip to content</a>
    <Sidebar view={route.view} config={config.data} alertCount={count} expanded={navOpen} close={() => setNavOpen(false)} />
    <div className="workspace">
      <header className="topbar">
        <div className="breadcrumbs">
          <button className="menu-button icon-button" aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
            aria-controls="sidebar" aria-expanded={navOpen} onClick={() => setNavOpen(value => !value)}>{navOpen ? <X size={22} /> : <Menu size={22} />}</button>
          <span className="breadcrumb-parent">Dashboard</span><ChevronRight className="breadcrumb-parent" size={15} /><strong>{label}</strong>
        </div>
        <div className="top-actions">
          <span className={`live-chip ${online ? 'live' : ''}`}><span className="dot" />{online ? 'Live readings' : rooms.error ? 'Connection issue' : rooms.data ? 'Awaiting readings' : 'Connecting'}</span>
          <a href="#alerts" className="icon-button bell-button" aria-label={count ? `Alerts, ${count} active` : 'Alerts'}><Bell size={19} />
            {count > 0 && <i />}</a>
        </div>
      </header>
      <main id="content" className="content" tabIndex={-1}>
        {config.error && <ErrorNotice message={config.error} retry={config.retry} cached={!!config.data} />}
        <Result state={rooms} loading="Connecting to the EcoSync API…">{data => {
          const names = Object.fromEntries(data.rooms.map(room => [room.id, room.name]))
          switch (route.view) {
            case 'analytics': return <Analytics rooms={data.rooms} />
            case 'rooms': return <Rooms rooms={data.rooms} selectedId={route.room} config={config.data} />
            case 'alerts': return <Alerts state={alerts} rooms={data.rooms} names={names} />
            case 'carbon': return <Carbon rooms={data.rooms} config={config.data} />
            default: return <Overview rooms={data} alerts={alerts} names={names} config={config.data} />
          }
        }}</Result>
        {rooms.data && <footer className="footer">
          <span>{config.data?.mode === 'local' ? 'Local demonstration' : config.data?.mode === 'aws' ? 'AWS cloud' : 'EcoSync'} · Simulated readings</span>
          <span>Updates every 5 seconds <i /> Times shown in IST</span>
        </footer>}
      </main>
    </div>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
