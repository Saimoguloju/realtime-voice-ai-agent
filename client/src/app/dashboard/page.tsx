'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';

interface Session {
  session_id: string;
  started_at: string;
  ended_at: string | null;
  message_count: number;
}

interface TranscriptMessage {
  role: string;
  content: string;
  created_at: string;
}

interface MetricRow {
  processor: string;
  metric_type: string;
  count: number;
  avg_secs: number;
  p50_secs: number;
  p95_secs: number;
}

const shortId = (id: string) => `${id.slice(0, 8)}…`;

const formatTime = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString() : '—';

const ms = (secs: number) => `${Math.round(secs * 1000)} ms`;

export default function Dashboard() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [sessionMetrics, setSessionMetrics] = useState<MetricRow[]>([]);
  const [globalMetrics, setGlobalMetrics] = useState<MetricRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [sessionsRes, metricsRes] = await Promise.all([
        fetch('/api/dashboard/sessions'),
        fetch('/api/dashboard/metrics'),
      ]);
      const sessionsData = await sessionsRes.json();
      const metricsData = await metricsRes.json();
      if (sessionsData.error) throw new Error(sessionsData.error);
      setSessions(sessionsData.sessions ?? []);
      setGlobalMetrics(metricsData.metrics ?? []);
      setError(null);
    } catch (e) {
      setError(`${e}`);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectSession = useCallback(async (sessionId: string) => {
    setSelected(sessionId);
    const res = await fetch(
      `/api/dashboard/sessions/${sessionId}/transcript`
    );
    const data = await res.json();
    setTranscript(data.transcript ?? []);
    setSessionMetrics(data.metrics ?? []);
  }, []);

  const metrics = selected ? sessionMetrics : globalMetrics;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-6 font-mono">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Call Dashboard</h1>
        <div className="flex gap-4 items-center">
          <button
            onClick={refresh}
            className="border border-neutral-700 px-3 py-1 rounded hover:bg-neutral-800">
            Refresh
          </button>
          <Link href="/" className="text-emerald-400 hover:underline">
            ← Back to call
          </Link>
        </div>
      </div>

      {error && (
        <div className="border border-red-700 text-red-400 rounded p-3 mb-6">
          {error} — is the bot server running on port 7860?
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sessions */}
        <div className="border border-neutral-800 rounded p-4">
          <h2 className="font-bold mb-3 text-neutral-400">
            Sessions ({sessions.length})
          </h2>
          <ul className="space-y-2 max-h-[70vh] overflow-y-auto">
            {sessions.length === 0 && (
              <li className="text-neutral-500">No calls recorded yet.</li>
            )}
            {sessions.map((s) => (
              <li key={s.session_id}>
                <button
                  onClick={() => selectSession(s.session_id)}
                  className={`w-full text-left p-2 rounded border ${
                    selected === s.session_id
                      ? 'border-emerald-500 bg-neutral-900'
                      : 'border-neutral-800 hover:bg-neutral-900'
                  }`}>
                  <div className="text-sm">{shortId(s.session_id)}</div>
                  <div className="text-xs text-neutral-500">
                    {formatTime(s.started_at)} · {s.message_count} messages
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Transcript */}
        <div className="border border-neutral-800 rounded p-4">
          <h2 className="font-bold mb-3 text-neutral-400">Transcript</h2>
          <div className="space-y-3 max-h-[70vh] overflow-y-auto">
            {!selected && (
              <p className="text-neutral-500">Select a session to view it.</p>
            )}
            {selected && transcript.length === 0 && (
              <p className="text-neutral-500">No messages in this session.</p>
            )}
            {transcript.map((m, i) => (
              <div key={i}>
                <span
                  className={
                    m.role === 'user' ? 'text-sky-400' : 'text-emerald-400'
                  }>
                  {m.role}:
                </span>{' '}
                <span className="text-sm">{m.content}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Latency metrics */}
        <div className="border border-neutral-800 rounded p-4">
          <h2 className="font-bold mb-3 text-neutral-400">
            Latency {selected ? `(session ${shortId(selected)})` : '(all calls)'}
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-neutral-500">
                <tr>
                  <th className="text-left py-1 pr-2">Service</th>
                  <th className="text-left py-1 pr-2">Type</th>
                  <th className="text-right py-1 pr-2">n</th>
                  <th className="text-right py-1 pr-2">avg</th>
                  <th className="text-right py-1 pr-2">p50</th>
                  <th className="text-right py-1">p95</th>
                </tr>
              </thead>
              <tbody>
                {metrics.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-neutral-500 py-2">
                      No metrics yet — make a call first.
                    </td>
                  </tr>
                )}
                {metrics.map((m, i) => (
                  <tr key={i} className="border-t border-neutral-900">
                    <td className="py-1 pr-2">
                      {m.processor.replace(/Service#\d+$/, '')}
                    </td>
                    <td className="py-1 pr-2 text-neutral-400">
                      {m.metric_type}
                    </td>
                    <td className="py-1 pr-2 text-right">{m.count}</td>
                    <td className="py-1 pr-2 text-right">{ms(m.avg_secs)}</td>
                    <td className="py-1 pr-2 text-right">{ms(m.p50_secs)}</td>
                    <td className="py-1 text-right text-amber-400">
                      {ms(m.p95_secs)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
