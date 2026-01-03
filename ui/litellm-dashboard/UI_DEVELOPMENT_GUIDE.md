# LiteLLM Dashboard UI 开发指南

## 技术栈

- **框架**: Next.js 14.2.32 (React 18)
- **语言**: TypeScript 5.3.3
- **样式**: Tailwind CSS 3.4.1
- **UI 库**:
  - Tremor React (主要 UI 组件)
  - Ant Design
  - Headless UI
  - Lucide React (图标)
- **状态管理**: TanStack React Query 5.x
- **构建工具**: Next.js Turbopack

## 环境要求

- Node.js >= 18.17.0 (当前版本: v22.17.0 ✅)
- npm >= 8.3.0 (当前版本: 11.4.2 ✅)

## 快速开始

### 1. 安装依赖

```bash
cd ui/litellm-dashboard
npm install
```

### 2. 启动开发服务器（实时预览）

```bash
npm run dev
```

开发服务器将在 **http://localhost:3000** 启动，支持热重载（HMR）。

### 3. 其他开发命令

```bash
# 构建生产版本
npm run build

# 启动生产服务器
npm start

# 代码检查
npm run lint

# 代码格式化
npm run format

# 运行单元测试
npm run test

# 测试覆盖率
npm run test:coverage

# 运行 E2E 测试
npm run e2e

# E2E 测试 UI 模式
npm run e2e:ui
```

## 项目结构

```
ui/litellm-dashboard/
├── src/
│   ├── app/              # Next.js 应用路由
│   ├── components/       # React 组件
│   │   └── ui/          # 基础 UI 组件
│   ├── contexts/        # React Context
│   ├── hooks/           # 自定义 Hooks
│   ├── lib/            # 工具库
│   ├── utils/          # 工具函数
│   └── types.ts        # TypeScript 类型定义
├── public/             # 静态资源
├── tests/             # 测试文件
├── e2e_tests/         # E2E 测试
└── tailwind.config.ts # Tailwind 配置
```

## 开发工作流

### 实时预览

1. 启动开发服务器: `npm run dev`
2. 访问 http://localhost:3000
3. 修改文件后自动热重载
4. 在浏览器中实时查看更改

### 代码质量

在提交代码前，建议运行：

```bash
# 格式化代码
npm run format

# 检查代码规范
npm run lint

# 运行测试
npm run test
```

## 环境变量

### 开发环境 (.env.development)

```
NODE_ENV=development
NEXT_PUBLIC_BASE_URL=""
```

### 生产环境 (.env.production)

```
NODE_ENV=production
NEXT_PUBLIC_BASE_URL=""
```

## 配置说明

### Next.js 配置 (next.config.mjs)

- `output: "export"` - 静态导出模式
- `basePath: ""` - 基础路径
- `assetPrefix: "/litellm-asset-prefix"` - 资源前缀

### Tailwind 配置

使用自定义主题配置，详见 `tailwind.config.ts` 和 `ui_colors.json`。

## UI 美化建议

### 设计系统

- 使用 Tremor React 组件库作为基础
- 保持一致的颜色方案（参考 ui_colors.json）
- 遵循 Tailwind CSS 的设计原则

### 组件开发

1. 在 `src/components/` 创建新组件
2. 使用 TypeScript 编写类型安全的代码
3. 添加对应的测试文件
4. 使用 Tailwind CSS 类名进行样式设计

### 样式指南

- 使用 Tailwind 实用类优先
- 避免内联样式
- 使用语义化的组件命名
- 保持响应式设计

## 调试技巧

### 开发工具

- React Developer Tools
- Next.js DevTools (内置)
- Tailwind CSS IntelliSense (VS Code 扩展)

### 常见问题

1. **端口占用**: 如果 3000 端口被占用，Next.js 会自动使用下一个可用端口
2. **缓存问题**: 删除 `.next` 目录并重新启动
3. **依赖问题**: 删除 `node_modules` 和 `package-lock.json`，重新安装

## 构建和部署

### 本地构建

```bash
npm run build
```

构建产物将输出到 `out/` 目录（静态导出）。

### 与后端集成

UI 构建后会被复制到 `litellm/proxy/_experimental/out/` 供 Python 后端服务使用。

## 测试

### 单元测试 (Vitest)

```bash
npm run test        # 运行测试
npm run test:watch  # 监听模式
npm run test:coverage  # 覆盖率报告
```

### E2E 测试 (Playwright)

```bash
npm run e2e      # 运行 E2E 测试
npm run e2e:ui   # UI 模式运行
```

## 相关资源

- [Next.js 文档](https://nextjs.org/docs)
- [Tailwind CSS 文档](https://tailwindcss.com/docs)
- [Tremor React 文档](https://www.tremor.so/docs)
- [TanStack Query 文档](https://tanstack.com/query/latest)

---

开始美化 UI 吧！🎨
