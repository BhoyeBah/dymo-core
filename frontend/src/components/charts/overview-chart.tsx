"use client";

import { ResponsiveContainer, AreaChart, Area, CartesianGrid, Tooltip, XAxis, YAxis, BarChart, Bar } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const fallbackSeries = [
  { name: "Jan", value: 120 },
  { name: "Fév", value: 180 },
  { name: "Mar", value: 220 },
  { name: "Avr", value: 260 },
  { name: "Mai", value: 340 },
  { name: "Jun", value: 410 }
];

export function RevenueChart({ data = fallbackSeries }: { data?: { name: string; value: number }[] }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Revenus</CardTitle>
      </CardHeader>
      <CardContent className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="revenue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0f172a" stopOpacity={0.45} />
                <stop offset="95%" stopColor="#0f172a" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="name" stroke="#64748b" />
            <YAxis stroke="#64748b" />
            <Tooltip />
            <Area type="monotone" dataKey="value" stroke="#0f172a" fill="url(#revenue)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function UsageChart({ data = fallbackSeries }: { data?: { name: string; value: number }[] }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Usage</CardTitle>
      </CardHeader>
      <CardContent className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="name" stroke="#64748b" />
            <YAxis stroke="#64748b" />
            <Tooltip />
            <Bar dataKey="value" fill="#0f172a" radius={[10, 10, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

