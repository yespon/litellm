"use client";

import { useLogin } from "@/app/(dashboard)/hooks/login/useLogin";
import { useUIConfig } from "@/app/(dashboard)/hooks/uiConfig/useUIConfig";
import LoadingScreen from "@/components/common_components/LoadingScreen";
import { getProxyBaseUrl } from "@/components/networking";
import { getCookie } from "@/utils/cookieUtils";
import { isJwtExpired } from "@/utils/jwtUtils";
import { InfoCircleOutlined, KeyOutlined, UserOutlined, LoginOutlined } from "@ant-design/icons";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

function LoginPageContent() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const { data: uiConfig, isLoading: isConfigLoading } = useUIConfig();
  const loginMutation = useLogin();
  const router = useRouter();

  useEffect(() => {
    if (isConfigLoading) {
      return;
    }

    // Check if admin UI is disabled
    if (uiConfig && uiConfig.admin_ui_disabled) {
      setIsLoading(false);
      return;
    }

    const rawToken = getCookie("token");
    if (rawToken && !isJwtExpired(rawToken)) {
      router.replace(`${getProxyBaseUrl()}/ui`);
      return;
    }

    if (uiConfig && uiConfig.auto_redirect_to_sso) {
      router.push(`${getProxyBaseUrl()}/sso/key/generate`);
      return;
    }

    setIsLoading(false);
  }, [isConfigLoading, router, uiConfig]);

  const handleSubmit = () => {
    loginMutation.mutate(
      { username, password },
      {
        onSuccess: (data) => {
          router.push(data.redirect_url);
        },
      },
    );
  };

  const handleSSOLogin = () => {
    window.location.href = `${getProxyBaseUrl()}/sso/key/generate`;
  };

  const error = loginMutation.error instanceof Error ? loginMutation.error.message : null;
  const isLoginLoading = loginMutation.isPending;

  const { Title, Text, Paragraph } = Typography;

  if (isConfigLoading || isLoading) {
    return <LoadingScreen />;
  }

  // Show disabled message if admin UI is disabled
  if (uiConfig && uiConfig.admin_ui_disabled) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="w-full max-w-lg shadow-md">
          <Space direction="vertical" size="middle" className="w-full">
            <div className="text-center">
              <Title level={2}>🚅 LiteLLM</Title>
            </div>

            <Alert
              message="Admin UI Disabled"
              description={
                <>
                  <Paragraph className="text-sm">
                    The Admin UI has been disabled by the administrator. To re-enable it, please update the following
                    environment variable:
                  </Paragraph>
                  <Paragraph className="text-sm">
                    <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">DISABLE_ADMIN_UI=False</code>
                  </Paragraph>
                </>
              }
              type="warning"
              showIcon
            />
          </Space>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-slate-50">
      {/* Subtle Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-indigo-900/5 rounded-full blur-3xl"></div>
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-slate-900/5 rounded-full blur-3xl"></div>
      </div>

      {/* Grid Pattern Overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:14px_24px] pointer-events-none"></div>

      <div className="w-full max-w-md px-6 relative z-10">
        {/* Main Login Card */}
        <div className="bg-white/90 backdrop-blur-2xl rounded-3xl shadow-2xl border border-white/60 overflow-hidden">
          {/* Header Section with Deep Gradient */}
          <div className="bg-[#0F172A] p-8 text-center relative overflow-hidden">
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS1vcGFjaXR5PSIwLjA1IiBzdHJva2Utd2lkdGg9IjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')] opacity-20"></div>
            <div className="flex justify-center mb-4 relative z-10">
              <div className="w-14 h-14 bg-white/10 rounded-xl flex items-center justify-center border border-white/10">
                <span className="text-2xl text-white font-bold">P</span>
              </div>
            </div>
            <h1 className="text-2xl font-bold text-white mb-1 tracking-tight relative z-10">Prism</h1>
            <p className="text-slate-400 text-[10px] font-bold uppercase tracking-[0.2em] relative z-10">
              Gateway Admin
            </p>
          </div>

          {/* Login Form Section */}
          <div className="p-8">
            <div className="space-y-6">
              {/* SSO Login Button */}
              <button
                onClick={handleSSOLogin}
                disabled={isLoginLoading}
                className="w-full group relative flex items-center justify-center gap-3 px-6 py-3.5 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 text-white font-semibold rounded-xl shadow-lg shadow-indigo-200 hover:shadow-xl hover:shadow-indigo-300 transition-all duration-300 transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 transform -skew-x-12 -translate-x-full group-hover:translate-x-full transition-transform duration-1000"></div>
                <svg className="w-5 h-5 relative z-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                <span className="relative z-10">Sign in with SSO</span>
                <svg className="w-4 h-4 relative z-10 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* Divider */}
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-white text-slate-400 font-medium">or use credentials</span>
                </div>
              </div>

              {/* Error Alert */}
              {error && (
                <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded-lg flex items-start gap-3 animate-shake">
                  <InfoCircleOutlined className="mt-0.5 text-lg" />
                  <div className="flex-1">
                    <p className="font-medium text-sm">{error}</p>
                  </div>
                </div>
              )}

              {/* Login Form */}
              <Form onFinish={handleSubmit} layout="vertical" requiredMark={false} className="space-y-5">
                <Form.Item
                  label={<span className="text-slate-700 font-semibold text-sm flex items-center gap-2"><UserOutlined className="text-indigo-600" />Username</span>}
                  name="username"
                  rules={[{ required: true, message: "Username is required" }]}
                  className="mb-0"
                >
                  <Input
                    prefix={<UserOutlined className="text-slate-400" />}
                    placeholder="Enter username (default: admin)"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={isLoginLoading}
                    size="large"
                    className="rounded-xl border-2 border-slate-200 hover:border-indigo-300 focus:border-indigo-500 transition-colors shadow-sm"
                  />
                </Form.Item>

                <Form.Item
                  label={<span className="text-slate-700 font-semibold text-sm flex items-center gap-2"><KeyOutlined className="text-indigo-600" />Password</span>}
                  name="password"
                  rules={[{ required: true, message: "Password is required" }]}
                  className="mb-0"
                >
                  <Input.Password
                    prefix={<KeyOutlined className="text-slate-400" />}
                    placeholder="Enter password (use MASTER_KEY)"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isLoginLoading}
                    size="large"
                    className="rounded-xl border-2 border-slate-200 hover:border-indigo-300 focus:border-indigo-500 transition-colors shadow-sm"
                  />
                </Form.Item>

                <Form.Item className="mb-0 pt-2">
                  <button
                    type="submit"
                    disabled={isLoginLoading}
                    className="w-full group relative flex items-center justify-center gap-2 px-6 py-3.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-xl shadow-lg shadow-slate-300 hover:shadow-xl hover:shadow-slate-400 transition-all duration-300 transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none overflow-hidden"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/10 to-white/0 transform -skew-x-12 -translate-x-full group-hover:translate-x-full transition-transform duration-1000"></div>
                    {isLoginLoading ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                        <span className="relative z-10">Signing in...</span>
                      </>
                    ) : (
                      <>
                        <LoginOutlined className="relative z-10" />
                        <span className="relative z-10">Sign in</span>
                      </>
                    )}
                  </button>
                </Form.Item>
              </Form>
            </div>

            {/* Helper Text */}
            <div className="mt-6 pt-6 border-t border-slate-100">
              <div className="bg-slate-50 rounded-xl p-4">
                <p className="text-xs text-slate-500 text-center leading-relaxed">
                  <span className="font-semibold text-slate-600">Default Credentials:</span>
                  <br />
                  Username: <code className="bg-white px-2 py-0.5 rounded text-slate-700 font-mono text-xs border border-slate-200">admin</code>
                  {" · "}
                  Password: <code className="bg-white px-2 py-0.5 rounded text-slate-700 font-mono text-xs border border-slate-200">MASTER_KEY</code>
                </p>
                <p className="text-xs text-slate-400 text-center mt-2">
                  Need help? {" "}
                  <a
                    href="https://docs.litellm.ai/docs/proxy/ui"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 hover:text-indigo-700 font-medium hover:underline"
                  >
                    Check the docs
                  </a>
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-6">
          <p className="text-xs text-slate-400">
            Powered by{" "}
            <a
              href="#"
              className="text-indigo-600 hover:text-indigo-700 font-semibold transition-colors"
            >
              Prism
            </a>
          </p>
        </div>
      </div>

      {/* Custom Styles for Animations */}
      <style jsx global>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          10%, 30%, 50%, 70%, 90% { transform: translateX(-2px); }
          20%, 40%, 60%, 80% { transform: translateX(2px); }
        }
        .animate-shake {
          animation: shake 0.5s ease-in-out;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
      `}</style>
    </div>
  );
}

export default function LoginPage() {
  const queryClient = new QueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <LoginPageContent />
    </QueryClientProvider>
  );
}
