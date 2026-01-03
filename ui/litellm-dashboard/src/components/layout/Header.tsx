import { useHealthReadiness } from "@/app/(dashboard)/hooks/healthReadiness/useHealthReadiness";
import { clearTokenCookies } from "@/utils/cookieUtils";
import {
    emitLocalStorageChange,
    getLocalStorageItem,
    removeLocalStorageItem,
    setLocalStorageItem,
} from "@/utils/localStorageUtils";
import { fetchProxySettings } from "@/utils/proxyUtils";
import {
    CrownOutlined,
    LogoutOutlined,
    MailOutlined,
    SafetyOutlined,
    UserOutlined,
    GithubOutlined,
    ReadOutlined
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import { Dropdown, Switch, Tooltip, Breadcrumb } from "antd";
import React, { useEffect, useState } from "react";
import Link from "next/link";

interface HeaderProps {
    userID: string | null;
    userEmail: string | null;
    userRole: string | null;
    premiumUser: boolean;
    proxySettings: any;
    setProxySettings: React.Dispatch<React.SetStateAction<any>>;
    accessToken: string | null;
    isPublicPage: boolean;
    page: string;
}

const Header: React.FC<HeaderProps> = ({
    userID,
    userEmail,
    userRole,
    premiumUser,
    proxySettings,
    setProxySettings,
    accessToken,
    isPublicPage = false,
    page,
}) => {
    const [logoutUrl, setLogoutUrl] = useState("");
    const [disableShowNewBadge, setDisableShowNewBadge] = useState(false);
    const { data: healthData } = useHealthReadiness();
    const version = healthData?.litellm_version;

    // Format page name for breadcrumbs
    const formatPageName = (p: string) => {
        return p.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    };

    useEffect(() => {
        const initializeProxySettings = async () => {
            if (accessToken) {
                const settings = await fetchProxySettings(accessToken);
                if (settings) {
                    setProxySettings(settings);
                }
            }
        };

        initializeProxySettings();
    }, [accessToken]);

    useEffect(() => {
        const storedValue = getLocalStorageItem("disableShowNewBadge");
        setDisableShowNewBadge(storedValue === "true");
    }, []);

    useEffect(() => {
        setLogoutUrl(proxySettings?.PROXY_LOGOUT_URL || "");
    }, [proxySettings]);

    const handleLogout = () => {
        clearTokenCookies();
        window.location.href = logoutUrl;
    };

    const userItems: MenuProps["items"] = [
        {
            key: "user-info",
            onClick: (info) => info.domEvent?.stopPropagation(),
            label: (
                <div className="px-3 py-3 border-b border-slate-100">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center">
                            <UserOutlined className="mr-2 text-slate-500" />
                            <span className="text-sm font-semibold text-slate-900">{userID}</span>
                        </div>
                        {premiumUser ? (
                            <Tooltip title="Premium User" placement="left">
                                <div className="flex items-center bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full cursor-help">
                                    <CrownOutlined className="mr-1 text-xs" />
                                    <span className="text-xs font-medium">Pro</span>
                                </div>
                            </Tooltip>
                        ) : (
                            <Tooltip title="Upgrade to Premium" placement="left">
                                <div className="flex items-center bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full cursor-help">
                                    <CrownOutlined className="mr-1 text-xs" />
                                    <span className="text-xs font-medium">Free</span>
                                </div>
                            </Tooltip>
                        )}
                    </div>
                    <div className="space-y-2">
                        <div className="flex items-center text-sm">
                            <SafetyOutlined className="mr-2 text-slate-400 text-xs" />
                            <span className="text-slate-500 text-xs">Role</span>
                            <span className="ml-auto text-slate-700 font-medium">{userRole}</span>
                        </div>
                        <div className="flex items-center text-sm">
                            <MailOutlined className="mr-2 text-slate-400 text-xs" />
                            <span className="text-slate-500 text-xs">Email</span>
                            <span className="ml-auto text-slate-700 font-medium truncate max-w-[150px]" title={userEmail || "Unknown"}>
                                {userEmail || "Unknown"}
                            </span>
                        </div>
                    </div>
                </div>
            ),
        },
        {
            key: "logout",
            label: (
                <div className="flex items-center py-2 px-3 hover:bg-red-50 hover:text-red-600 rounded-md mx-1 my-1 transition-colors" onClick={handleLogout}>
                    <LogoutOutlined className="mr-3" />
                    <span>Logout</span>
                </div>
            ),
        },
    ];

    return (
        <div className="w-full h-full flex items-center justify-between">
            {/* Left side: Breadcrumbs / Title */}
            <div className="flex items-center gap-4">
                <Breadcrumb
                    items={[
                        { title: <span className="text-slate-400">Dashboard</span> },
                        { title: <span className="text-slate-800 font-medium">{formatPageName(page)}</span> },
                    ]}
                />
                {version && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200">
                        v{version}
                    </span>
                )}
            </div>

            {/* Right side nav items */}
            <div className="flex items-center space-x-6">
                <a
                    href="https://docs.litellm.ai/docs/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center text-sm text-slate-500 hover:text-indigo-600 transition-colors gap-2"
                >
                    <ReadOutlined />
                    <span className="hidden sm:inline">Documentation</span>
                </a>

                <a
                    href="https://github.com/BerriAI/litellm"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center text-sm text-slate-500 hover:text-slate-900 transition-colors"
                >
                    <GithubOutlined className="text-lg" />
                </a>

                {!isPublicPage && (
                    <Dropdown
                        menu={{
                            items: userItems,
                            className: "min-w-[240px]",
                            style: {
                                padding: "4px",
                                borderRadius: "12px",
                                boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
                            },
                        }}
                        trigger={['click']}
                        placement="bottomRight"
                    >
                        <button className="flex items-center gap-2 pl-2 pr-1 py-1 rounded-full hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-200 focus:outline-none">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-medium text-xs shadow-sm">
                                {userID?.substring(0, 2).toUpperCase()}
                            </div>
                            <div className="hidden md:block text-left mr-1">
                                <div className="text-xs font-semibold text-slate-700 max-w-[100px] truncate leading-tight">{userID}</div>
                                <div className="text-[10px] text-slate-500 leading-tight">{userRole}</div>
                            </div>
                        </button>
                    </Dropdown>
                )}
            </div>
        </div>
    );
};

export default Header;
