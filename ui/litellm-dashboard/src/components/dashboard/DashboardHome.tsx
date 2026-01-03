"use client";

import React from "react";
import {
    KeyOutlined,
    BlockOutlined,
    BarChartOutlined,
    RobotOutlined,
    PlayCircleOutlined,
    FileTextOutlined,
    ArrowRightOutlined,
    ThunderboltOutlined,
} from "@ant-design/icons";

interface DashboardHomeProps {
    userEmail: string | null;
    userRole: string;
    keysCount: number;
    teamsCount: number;
    modelsCount: number;
    setPage: (page: string) => void;
}

interface QuickLinkProps {
    icon: React.ReactNode;
    title: string;
    description: string;
    page: string;
    onClick: () => void;
}

const QuickLink: React.FC<QuickLinkProps> = ({ icon, title, description, onClick }) => (
    <button
        onClick={onClick}
        className="group flex items-start gap-4 p-4 bg-white hover:bg-slate-50 rounded-xl border border-slate-200 hover:border-indigo-200 transition-all duration-200 text-left w-full"
    >
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center group-hover:bg-indigo-100 transition-colors">
            {icon}
        </div>
        <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                {title}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5 truncate">{description}</p>
        </div>
        <ArrowRightOutlined className="text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-1 transition-all mt-1" />
    </button>
);

interface StatCardProps {
    icon: React.ReactNode;
    label: string;
    value: string | number;
    subtext?: string;
    color: "indigo" | "emerald" | "amber" | "rose";
}

const StatCard: React.FC<StatCardProps> = ({ icon, label, value, subtext, color }) => {
    const colorClasses = {
        indigo: "bg-indigo-50 text-indigo-600 border-indigo-100",
        emerald: "bg-emerald-50 text-emerald-600 border-emerald-100",
        amber: "bg-amber-50 text-amber-600 border-amber-100",
        rose: "bg-rose-50 text-rose-600 border-rose-100",
    };

    const iconBgClasses = {
        indigo: "bg-indigo-100/50",
        emerald: "bg-emerald-100/50",
        amber: "bg-amber-100/50",
        rose: "bg-rose-100/50",
    };

    return (
        <div className={`rounded-xl border p-5 ${colorClasses[color]}`}>
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs font-medium opacity-80 uppercase tracking-wide">{label}</p>
                    <p className="text-2xl font-bold mt-1">{value}</p>
                    {subtext && <p className="text-xs opacity-70 mt-0.5">{subtext}</p>}
                </div>
                <div className={`w-12 h-12 rounded-xl ${iconBgClasses[color]} flex items-center justify-center text-xl`}>
                    {icon}
                </div>
            </div>
        </div>
    );
};

const DashboardHome: React.FC<DashboardHomeProps> = ({
    userEmail,
    userRole,
    keysCount,
    teamsCount,
    modelsCount,
    setPage,
}) => {
    const firstName = userEmail?.split("@")[0] || "Admin";
    const capitalizedName = firstName.charAt(0).toUpperCase() + firstName.slice(1);

    const quickLinks = [
        {
            icon: <KeyOutlined className="text-lg" />,
            title: "Create Virtual Key",
            description: "Generate a new API key for your application",
            page: "api-keys",
        },
        {
            icon: <BlockOutlined className="text-lg" />,
            title: "Manage Models",
            description: "Configure LLM models and endpoints",
            page: "models",
        },
        {
            icon: <PlayCircleOutlined className="text-lg" />,
            title: "Try Playground",
            description: "Test your models interactively",
            page: "llm-playground",
        },
        {
            icon: <BarChartOutlined className="text-lg" />,
            title: "View Usage",
            description: "Monitor spend and API usage",
            page: "new_usage",
        },
        {
            icon: <RobotOutlined className="text-lg" />,
            title: "Configure Agents",
            description: "Set up and manage AI agents",
            page: "agents",
        },
        {
            icon: <FileTextOutlined className="text-lg" />,
            title: "View Logs",
            description: "Explore request and response logs",
            page: "logs",
        },
    ];

    return (
        <div className="p-6 space-y-8">
            {/* Welcome Header */}
            <div className="bg-[#0F172A] rounded-2xl p-8 text-white shadow-xl shadow-slate-200/50 relative overflow-hidden">
                <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS1vcGFjaXR5PSIwLjA1IiBzdHJva2Utd2lkdGg9IjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')] opacity-20"></div>
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-2">
                        <ThunderboltOutlined className="text-xl text-slate-400" />
                        <span className="text-slate-400 text-[10px] font-bold uppercase tracking-[0.2em]">AI Gateway</span>
                    </div>
                    <h1 className="text-3xl font-bold mb-2 tracking-tight">Welcome back, {capitalizedName}!</h1>
                    <p className="text-slate-400 text-sm max-w-2xl font-medium">
                        You're logged in as <span className="text-indigo-400">{userRole}</span>. Manage your LLM infrastructure from this centralized dashboard.
                    </p>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    icon={<KeyOutlined />}
                    label="Virtual Keys"
                    value={keysCount}
                    subtext="Active"
                    color="indigo"
                />
                <StatCard
                    icon={<BlockOutlined />}
                    label="Models"
                    value={modelsCount}
                    subtext="Configured"
                    color="emerald"
                />
                <StatCard
                    icon={<BarChartOutlined />}
                    label="Teams"
                    value={teamsCount}
                    subtext="Active"
                    color="amber"
                />
                <StatCard
                    icon={<RobotOutlined />}
                    label="Agents"
                    value="–"
                    subtext="Available"
                    color="rose"
                />
            </div>

            {/* Quick Links */}
            <div>
                <h2 className="text-lg font-semibold text-slate-900 mb-4">Quick Actions</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {quickLinks.map((link) => (
                        <QuickLink
                            key={link.page}
                            icon={link.icon}
                            title={link.title}
                            description={link.description}
                            page={link.page}
                            onClick={() => setPage(link.page)}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
};

export default DashboardHome;
