import React from "react";

interface MainLayoutProps {
    sidebar: React.ReactNode;
    header?: React.ReactNode;
    children: React.ReactNode;
}

export default function MainLayout({ sidebar, header, children }: MainLayoutProps) {
    return (
        <div className="flex h-screen bg-slate-50 overflow-hidden">
            {/* Sidebar Area */}
            <aside className="w-64 h-full bg-white border-r border-slate-200 flex-shrink-0 z-20">
                {sidebar}
            </aside>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Header Area */}
                {header && (
                    <header className="h-16 bg-white border-b border-slate-200 flex items-center px-6 justify-between flex-shrink-0 z-10">
                        {header}
                    </header>
                )}

                {/* Scrollable Content */}
                <main className="flex-1 overflow-y-auto p-6 scroll-smooth">
                    <div className="max-w-7xl mx-auto h-full">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
