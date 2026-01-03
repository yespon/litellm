import { useOrganizations } from "@/app/(dashboard)/hooks/organizations/useOrganizations";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import {
  ApiOutlined,
  AppstoreOutlined,
  BankOutlined,
  BarChartOutlined,
  BgColorsOutlined,
  BlockOutlined,
  CreditCardOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  KeyOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  RobotOutlined,
  SafetyOutlined,
  SearchOutlined,
  SettingOutlined,
  TagsOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import { ConfigProvider, Layout, Menu } from "antd";
import { useMemo } from "react";
import { all_admin_roles, internalUserRoles, isAdminRole, rolesWithWriteAccess } from "../utils/roles";
import type { Organization } from "./networking";
import UsageIndicator from "./usage_indicator";
import NewBadge from "./common_components/NewBadge";
import Link from "next/link";
import { getProxyBaseUrl } from "./networking";

const { Sider } = Layout;

interface SidebarProps {
  setPage: (page: string) => void;
  defaultSelectedKey: string;
  collapsed?: boolean;
}

interface MenuItem {
  key: string;
  page: string;
  label: string | React.ReactNode;
  roles?: string[];
  children?: MenuItem[];
  icon?: React.ReactNode;
}

interface MenuGroup {
  groupLabel: string;
  items: MenuItem[];
  roles?: string[];
}

const Sidebar: React.FC<SidebarProps> = ({ setPage, defaultSelectedKey, collapsed = false }) => {
  const { userId, accessToken, userRole } = useAuthorized();
  const { data: organizations } = useOrganizations();
  const baseUrl = getProxyBaseUrl();

  const isOrgAdmin = useMemo(() => {
    if (!userId || !organizations) return false;
    return organizations.some((org: Organization) =>
      org.members?.some((member) => member.user_id === userId && member.user_role === "org_admin"),
    );
  }, [userId, organizations]);

  const navigateToPage = (page: string) => {
    const newSearchParams = new URLSearchParams(window.location.search);
    newSearchParams.set("page", page);
    window.history.pushState(null, "", `?${newSearchParams.toString()}`);
    setPage(page);
  };

  const menuGroups: MenuGroup[] = [
    {
      groupLabel: "AI GATEWAY",
      items: [
        {
          key: "dashboard",
          page: "dashboard",
          label: "Dashboard",
          icon: <AppstoreOutlined />,
        },
        {
          key: "api-keys",
          page: "api-keys",
          label: "Virtual Keys",
          icon: <KeyOutlined />,
        },
        {
          key: "llm-playground",
          page: "llm-playground",
          label: "Playground",
          icon: <PlayCircleOutlined />,
          roles: rolesWithWriteAccess,
        },
        {
          key: "models",
          page: "models",
          label: "Models + Endpoints",
          icon: <BlockOutlined />,
          roles: rolesWithWriteAccess,
        },
        {
          key: "agents",
          page: "agents",
          label: "Agents",
          icon: <RobotOutlined />,
          roles: rolesWithWriteAccess,
        },
        {
          key: "mcp-servers",
          page: "mcp-servers",
          label: "MCP Servers",
          icon: <ToolOutlined />,
        },
        {
          key: "guardrails",
          page: "guardrails",
          label: "Guardrails",
          icon: <SafetyOutlined />,
          roles: all_admin_roles,
        },
      ],
    },
    {
      groupLabel: "OBSERVABILITY",
      items: [
        {
          key: "new_usage",
          page: "new_usage",
          icon: <BarChartOutlined />,
          roles: [...all_admin_roles, ...internalUserRoles],
          label: "Usage",
        },
        {
          key: "logs",
          page: "logs",
          label: "Logs",
          icon: <LineChartOutlined />,
        },
      ],
    },
    {
      groupLabel: "ACCESS CONTROL",
      items: [
        {
          key: "users",
          page: "users",
          label: "Internal Users",
          icon: <UserOutlined />,
          roles: all_admin_roles,
        },
        {
          key: "teams",
          page: "teams",
          label: "Teams",
          icon: <TeamOutlined />,
        },
        {
          key: "organizations",
          page: "organizations",
          label: "Organizations",
          icon: <BankOutlined />,
          roles: all_admin_roles,
        },
        {
          key: "budgets",
          page: "budgets",
          label: "Budgets",
          icon: <CreditCardOutlined />,
          roles: all_admin_roles,
        },
      ],
    },
    {
      groupLabel: "DEVELOPER TOOLS",
      items: [
        {
          key: "api_ref",
          page: "api_ref",
          label: "API Reference",
          icon: <ApiOutlined />,
        },
        {
          key: "model-hub-table",
          page: "model-hub-table",
          label: "AI Hub",
          icon: <AppstoreOutlined />,
        },
        {
          key: "experimental",
          page: "experimental",
          label: "Experimental",
          icon: <ExperimentOutlined />,
          children: [
            {
              key: "tools",
              page: "tools",
              label: "Tools",
              icon: <ToolOutlined />,
              children: [
                {
                  key: "search-tools",
                  page: "search-tools",
                  label: "Search Tools",
                  icon: <SearchOutlined />,
                },
                {
                  key: "vector-stores",
                  page: "vector-stores",
                  label: "Vector Stores",
                  icon: <DatabaseOutlined />,
                  roles: all_admin_roles,
                },
              ],
            },
            {
              key: "caching",
              page: "caching",
              label: "Caching",
              icon: <DatabaseOutlined />,
              roles: all_admin_roles,
            },
            {
              key: "prompts",
              page: "prompts",
              label: "Prompts",
              icon: <FileTextOutlined />,
              roles: all_admin_roles,
            },
            {
              key: "transform-request",
              page: "transform-request",
              label: "API Playground",
              icon: <ApiOutlined />,
              roles: [...all_admin_roles, ...internalUserRoles],
            },
            {
              key: "tag-management",
              page: "tag-management",
              label: "Tag Management",
              icon: <TagsOutlined />,
              roles: all_admin_roles,
            },
          ],
        },
      ],
    },
    {
      groupLabel: "SETTINGS",
      roles: all_admin_roles,
      items: [
        {
          key: "settings",
          page: "settings",
          label: (
            <span className="flex items-center gap-2">
              Settings <NewBadge />
            </span>
          ),
          icon: <SettingOutlined />,
          roles: all_admin_roles,
          children: [
            {
              key: "router-settings",
              page: "router-settings",
              label: "Router Settings",
              icon: <SettingOutlined />,
              roles: all_admin_roles,
            },
            {
              key: "logging-and-alerts",
              page: "logging-and-alerts",
              label: "Logging & Alerts",
              icon: <SettingOutlined />,
              roles: all_admin_roles,
            },
            {
              key: "admin-panel",
              page: "admin-panel",
              label: "Admin Settings",
              icon: <SettingOutlined />,
              roles: all_admin_roles,
            },
            {
              key: "cost-tracking",
              page: "cost-tracking",
              label: "Cost Tracking",
              icon: <BarChartOutlined />,
              roles: all_admin_roles,
            },
            {
              key: "ui-theme",
              page: "ui-theme",
              label: "UI Theme",
              icon: <BgColorsOutlined />,
              roles: all_admin_roles,
            },
          ],
        },
      ],
    },
  ];

  const filterItemsByRole = (items: MenuItem[]): MenuItem[] => {
    return items
      .filter((item) => {
        if (item.key === "organizations") {
          return !item.roles || item.roles.includes(userRole) || isOrgAdmin;
        }
        return !item.roles || item.roles.includes(userRole);
      })
      .map((item) => ({
        ...item,
        children: item.children ? filterItemsByRole(item.children) : undefined,
      }));
  };

  const buildMenuItems = (): MenuProps["items"] => {
    const items: MenuProps["items"] = [];

    menuGroups.forEach((group) => {
      if (group.roles && !group.roles.includes(userRole)) {
        return;
      }

      const filteredItems = filterItemsByRole(group.items);
      if (filteredItems.length === 0) return;

      items.push({
        type: "group",
        label: collapsed ? null : (
          <span className="text-[11px] font-bold text-slate-400 tracking-wider px-3 uppercase mb-2 mt-4 block">
            {group.groupLabel}
          </span>
        ),
        children: filteredItems.map((item) => ({
          key: item.key,
          icon: item.icon,
          label: item.label,
          className: "my-1",
          children: item.children?.map((child) => ({
            key: child.key,
            icon: child.icon,
            label: child.label,
            onClick: () => navigateToPage(child.page),
          })),
          onClick: !item.children ? () => navigateToPage(item.page) : undefined,
        })),
      });
    });

    return items;
  };

  const findMenuItemKey = (page: string): string => {
    for (const group of menuGroups) {
      for (const item of group.items) {
        if (item.page === page) return item.key;
        if (item.children) {
          const child = item.children.find((c) => c.page === page);
          if (child) return child.key;
        }
      }
    }
    return "api-keys";
  };

  const selectedMenuKey = findMenuItemKey(defaultSelectedKey);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Brand Area */}
      <div className="h-16 flex items-center px-6 border-b border-slate-100 flex-shrink-0">
        <Link href={baseUrl ? baseUrl : "/"} className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-lg">
            P
          </div>
          {!collapsed && (
            <span className="font-bold text-lg text-slate-800 tracking-tight">Prism</span>
          )}
        </Link>
      </div>

      {/* Menu Area */}
      <div className="flex-1 overflow-y-auto py-4 scrollbar-hide">
        <ConfigProvider
          theme={{
            components: {
              Menu: {
                itemSelectedBg: "#eff6ff", // brand-faint
                itemSelectedColor: "#4f46e5", // brand-DEFAULT
                itemHoverBg: "#f8fafc", // slate-50
                itemColor: "#64748b", // slate-500
                iconSize: 16,
                fontSize: 14,
                itemBorderRadius: 8,
                itemMarginInline: 12,
                itemHeight: 36,
              },
            },
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[selectedMenuKey]}
            defaultOpenKeys={[]}
            inlineCollapsed={collapsed}
            items={buildMenuItems()}
            style={{ borderRight: 0 }}
            className="custom-sidebar"
          />
        </ConfigProvider>
      </div>

      {/* User / Usage Area */}
      {isAdminRole(userRole) && !collapsed && (
        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <div className="mb-2 text-xs font-medium text-slate-500 uppercase tracking-wider">Usage</div>
          <UsageIndicator accessToken={accessToken} width={180} />
        </div>
      )}
    </div>
  );
};

export default Sidebar;
