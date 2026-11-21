import { useId } from 'react'
import {
  Activity, AlertTriangle, CalendarDays, ChartNoAxesCombined, Check, ChevronDown, CircleAlert,
  Cloud, Database, Leaf, Lightbulb, Radio, RotateCw,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatTime, fullTime, hasRoomData, periods, roomStyles, shortTime, showNumber } from './format'

export function PageHeader({ title, description, date, children }) {
  return (
    <div className="page-header">
      <div><h1>{title}</h1><p>{description}</p></div>
      {children || (date && <div className="date-chip"><CalendarDays size={16} />{formatTime(date, {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
      })}</div>)}
    </div>
  )
}

export function Source({ config }) {
  const Icon = config?.mode === 'aws' ? Cloud : Database
  return (
    <div className="source-box">
      <div className="source-icon"><Icon size={17} /></div>
      <div><strong>{config?.mode === 'aws' ? 'AWS cloud mode' : config?.mode === 'local' ? 'Local demo mode' : 'Data source'}</strong>
        <small>{config?.mode === 'aws' ? 'Lambda · DynamoDB' : config?.mode === 'local' ? 'Python API · SQLite' : 'Connecting to API'}</small></div>
    </div>
  )
}

export function Metric({ icon: Icon, label, value, unit, detail, tone = 'green' }) {
  return (
    <section className="metric panel">
      <div className="metric-head"><span className={`tile ${tone}`}><Icon size={19} /></span><span>{label}</span></div>
      <div className="metric-value">{value}{unit && value !== '—' && <small>{unit}</small>}</div>
      <div className="metric-detail">{detail}</div>
    </section>
  )
}

export function Empty({ icon: Icon = ChartNoAxesCombined, title, detail, compact = false }) {
  return <div className={`empty-state ${compact ? 'compact' : ''}`}><span className="tile green"><Icon size={20} /></span>
    <strong>{title}</strong>{detail && <p>{detail}</p>}</div>
}

export function Loading({ label = 'Loading dashboard…' }) {
  return <div className="loading" role="status"><RotateCw size={18} className="motion-safe:animate-spin" />{label}</div>
}

export function ErrorNotice({ message, retry, cached }) {
  return <div className="error-notice" role="status"><CircleAlert size={19} />
    <div><strong>{cached ? 'Showing the last successful response' : 'Unable to load data'}</strong>
      <p>{message}</p></div><button className="soft-button" onClick={retry}><RotateCw size={15} />Retry</button>
  </div>
}

export function Result({ state, children, loading = 'Loading data…' }) {
  return <>
    {state.error && <ErrorNotice message={state.error} cached={!!state.data} retry={state.retry} />}
    {state.loading && <Loading label={loading} />}
    {state.data && children(state.data)}
  </>
}

export function PeriodSwitch({ value, onChange, includeRecent = false }) {
  const choices = includeRecent ? [['recent', 'Recent'], ...periods] : periods
  return <div className="segmented" role="group" aria-label="Date range">
    {choices.map(([id, label]) =>
      <button key={id} type="button" onClick={() => onChange(id)} aria-pressed={value === id}>{label}</button>)}
  </div>
}

export function PanelHeading({ title, description, action }) {
  return <div className="panel-heading">
    <div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}
  </div>
}

function ChartTooltip({ active, payload, label, unit, dateLabel, names }) {
  const valid = payload?.filter(item => item.value != null)
  if (!active || !valid?.length) return null
  return <div className="chart-tip"><strong>{dateLabel(label)}</strong>{valid.map(item =>
    <div key={item.dataKey}><i style={{ background: item.color }} />{names[item.dataKey] || item.name}
      <b>{showNumber(item.value, 3)} {unit}</b></div>)}</div>
}

export function Trend({ analytics, rooms = [], metric = 'energy', multi = false, color = '#0d946a' }) {
  const fill = useId().replace(/[^a-z0-9]/gi, '')
  const carbon = metric === 'carbon'
  const daily = carbon || analytics.period !== 'today'
  const unit = carbon ? 'kg CO₂' : analytics.series_unit
  const input = carbon ? analytics.daily : analytics.series
  const points = input.map(point => ({
    at: point.at,
    total: carbon ? (point.value != null ? point.carbon_kg : null) : point.value,
    ...point.rooms,
  }))
  const names = { total: carbon ? 'Estimated emissions' : daily ? 'Energy used' : 'Average power',
    ...Object.fromEntries(rooms.map(room => [room.id, room.name])) }
  const lines = multi ? rooms.map(room => ({ id: room.id, color: roomStyles[room.id].color })) : [{ id: 'total', color }]
  const label = at => daily ? formatTime(at, { day: 'numeric', month: 'short' }) : shortTime(at)
  if (!analytics.has_data || !points.some(point => point.total != null)) {
    return <Empty icon={Activity} title="Waiting for readings" detail="Chart data appears after two readings arrive for a room." />
  }
  return <div className="chart-frame" aria-label={carbon ? 'Estimated daily carbon emissions chart' : `Electricity usage chart in ${unit}`}>
    <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
      <AreaChart data={points} margin={{ top: 12, right: 10, bottom: 0, left: 0 }}>
        <defs><linearGradient id={fill} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.24} />
          <stop offset="100%" stopColor={color} stopOpacity={0.015} />
        </linearGradient></defs>
        <CartesianGrid vertical={false} stroke="#e8eeeb" strokeDasharray="4 4" />
        <XAxis dataKey="at" tickFormatter={label} axisLine={false} tickLine={false}
          tick={{ fill: '#63766e', fontSize: 12 }} tickMargin={12} minTickGap={22} />
        <YAxis axisLine={false} tickLine={false} width={52} tickMargin={8}
          tick={{ fill: '#63766e', fontSize: 12 }} tickFormatter={v => showNumber(v, 2)} domain={[0, 'auto']} />
        <Tooltip content={<ChartTooltip unit={unit} dateLabel={label} names={names} />} />
        {lines.map(line => <Area key={line.id} type="monotone" dataKey={line.id}
          name={names[line.id]} stroke={line.color} strokeWidth={2.5} fill={multi ? 'none' : `url(#${fill})`}
          dot={props => {
            const { cx, cy, value, index } = props
            const adjacent = points[index - 1]?.[line.id] != null || points[index + 1]?.[line.id] != null
            return value != null && !adjacent && Number.isFinite(cx) && Number.isFinite(cy)
              ? <circle key={index} cx={cx} cy={cy} r={4} fill={line.color} /> : null
          }}
          activeDot={{ r: 5 }} isAnimationActive={false} />)}
      </AreaChart>
    </ResponsiveContainer>
  </div>
}

export function ChartKey({ rooms, unit, color = '#0d946a', name }) {
  return <div className="chart-key">
    {rooms ? rooms.map(room => <span key={room.id}><i style={{ background: roomStyles[room.id].color }} />{room.name}</span>)
      : <span><i style={{ background: color }} />{name}</span>}
    <small>{unit}</small>
  </div>
}

export function ReadingTrend({ readings, room, maxGapSeconds }) {
  if (!readings.length) return <Empty icon={Activity} title="No recent readings"
    detail="The chart shows readings saved in the past 24 hours." />

  const points = []
  for (const reading of [...readings].reverse()) {
    const at = Date.parse(reading.timestamp)
    const previous = points.at(-1)
    if (previous && maxGapSeconds != null && at - previous.at > maxGapSeconds * 1000) {
      points.push({ at: previous.at + (at - previous.at) / 2, power: null })
    }
    points.push({ at, power: reading.power_kw })
  }
  const first = points[0].at
  const last = points.at(-1).at
  const domain = first === last ? [first - 5000, last + 5000] : ['dataMin', 'dataMax']
  const tickTime = at => formatTime(at, {
    hour: 'numeric', minute: '2-digit', ...(last - first < 5 * 60_000 ? { second: '2-digit' } : {}),
  })
  const color = roomStyles[room.id].color

  return <div className="chart-frame" role="group" aria-label={`${room.name} saved power readings chart`}>
    <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
      <LineChart data={points} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="#e8eeeb" strokeDasharray="4 4" />
        <XAxis dataKey="at" type="number" scale="time" domain={domain} tickCount={5}
          axisLine={false} tickLine={false} tickMargin={12} minTickGap={14}
          tickFormatter={tickTime} tick={{ fill: '#63766e', fontSize: 12 }} />
        <YAxis domain={[0, 'auto']} width={52} axisLine={false} tickLine={false}
          tickMargin={8} tick={{ fill: '#63766e', fontSize: 12 }} tickFormatter={v => showNumber(v, 2)} />
        <Tooltip content={<ChartTooltip unit="kW" dateLabel={fullTime} names={{ power: room.name }} />} />
        <Line dataKey="power" name={room.name} stroke={color} strokeWidth={2}
          type="linear" connectNulls={false} dot={{ r: 2.5, strokeWidth: 0, fill: color }}
          activeDot={{ r: 5 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  </div>
}

export function RoomBarChart({ analytics, rooms, metric = 'energy_kwh', unit = 'kWh' }) {
  const points = analytics.by_room.filter(entry => hasRoomData(analytics, entry)).map(entry => ({
    room: rooms.find(room => room.id === entry.room_id)?.name || entry.room_id,
    roomId: entry.room_id, value: entry[metric] }))
  if (!points.length) return <Empty title="No consumption recorded" compact />
  if (points.every(point => point.value === 0)) {
    return <Empty title={`Total is 0 ${unit}`}
      detail={points.map(point => point.room).join(', ')} compact />
  }
  return <div className="bar-frame"><ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
    <BarChart data={points} layout="vertical" margin={{ top: 6, right: 12, left: 0, bottom: 6 }}>
      <CartesianGrid horizontal={false} stroke="#e8eeeb" strokeDasharray="4 4" />
      <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: '#63766e', fontSize: 12 }} />
      <YAxis dataKey="room" type="category" width={103} axisLine={false} tickLine={false}
        tick={{ fill: '#42564f', fontSize: 12 }} />
      <Tooltip cursor={{ fill: '#f3f7f5' }} formatter={value => [`${showNumber(value, 3)} ${unit}`, 'Total']} />
      <Bar dataKey="value" barSize={18} radius={[0, 7, 7, 0]} isAnimationActive={false}>
        {points.map(point => <Cell key={point.roomId} fill={roomStyles[point.roomId].color} />)}
      </Bar>
    </BarChart>
  </ResponsiveContainer></div>
}

export function RoomTile({ room }) {
  const style = roomStyles[room.id]
  const Icon = style.icon
  return <span className={`tile ${style.tone}`}><Icon size={20} /></span>
}

export function RoomStatus({ room }) {
  if (room.stale) return <span className="status muted"><Radio size={13} />{room.latest ? 'Stale' : 'Waiting'}</span>
  if (room.active_alert) return <span className="status warning"><AlertTriangle size={13} />Anomaly</span>
  return <span className="status good"><span className="dot" />Reporting</span>
}

export function AlertState({ alert }) {
  return <span className={`status ${alert.status === 'active' ? 'warning' : 'good'}`}>
    {alert.status === 'active' ? <CircleAlert size={13} /> : <Check size={13} />}
    {alert.status === 'active' ? 'Active' : 'Resolved'}
  </span>
}

export function AlertList({ alerts, names }) {
  if (!alerts.length) return <Empty icon={Check} title="No alerts to display" detail="Anomalies will appear here when detected." compact />
  return <ul className="event-list">{alerts.map(alert => <li key={alert.id}>
    <span className={`tile ${alert.status === 'active' ? 'amber' : 'green'}`}>
      {alert.status === 'active' ? <AlertTriangle size={17} /> : <Check size={17} />}
    </span><div><strong>{names[alert.room_id]}</strong>
      <p>{alert.reasons.includes('spike') ? 'Power spike' : 'Threshold exceeded'} · {showNumber(alert.peak_kw)} kW peak</p>
      <time dateTime={alert.started_at}>{fullTime(alert.started_at)}</time></div>
    <AlertState alert={alert} />
  </li>)}</ul>
}

export function Recommendations({ items, names }) {
  if (!items.length) return <Empty icon={Leaf} title="No recommendations right now"
    detail="Suggestions appear when the API detects elevated or after-hours usage." compact />
  return <ul className="event-list">{items.map(item => <li key={`${item.room_id}/${item.type}`}>
    <span className="tile green"><Lightbulb size={17} /></span>
    <div><strong>{item.title}</strong><small>{names[item.room_id]}</small><p>{item.message}</p></div>
  </li>)}</ul>
}

export function Select({ label, value, onChange, options }) {
  return <div className="select-wrap">
    <select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
      {options.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
    </select>
    <ChevronDown size={15} aria-hidden="true" />
  </div>
}
