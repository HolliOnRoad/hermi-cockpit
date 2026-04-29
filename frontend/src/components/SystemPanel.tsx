import { useEffect, useState } from 'react'

type SystemMetrics = {
  cpu_percent: number
  ram_percent: number
  ram_used_gb: number
  ram_total_gb: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
  network_kb_s: number
}

type MetricsState = SystemMetrics | null

export function SystemPanel() {
  const [metrics, setMetrics] = useState<MetricsState>(null)

  useEffect(() => {
    const fetchMetrics = () => {
      fetch('http://127.0.0.1:8000/api/system')
        .then((r) => r.json())
        .then((data) => setMetrics(data))
        .catch(() => {})
    }

    fetchMetrics()
    const interval = setInterval(fetchMetrics, 2000)
    return () => clearInterval(interval)
  }, [])

  const items = [
    {
      label: 'CPU',
      value: metrics ? `${metrics.cpu_percent}%` : '--',
    },
    {
      label: 'RAM',
      value: metrics
        ? `${metrics.ram_percent}% (${metrics.ram_used_gb}/${metrics.ram_total_gb} GB)`
        : '--',
    },
    {
      label: 'Disk',
      value: metrics
        ? `${metrics.disk_percent}% (${metrics.disk_used_gb}/${metrics.disk_total_gb} GB)`
        : '--',
    },
    {
      label: 'Network',
      value: metrics ? `${metrics.network_kb_s} KB/s` : '--',
    },
  ]

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">System</span>
        <span className="pill pill-active">Live</span>
      </div>
      <div className="panel-body">
        <div className="system-list">
          {items.map((m) => (
            <div key={m.label} className="system-row">
              <span className="system-key">{m.label}</span>
              <span className="system-value">{m.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
