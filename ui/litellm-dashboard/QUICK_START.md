# LiteLLM UI - 快速启动指南

## ✅ 环境已就绪

### 后端服务 (已运行)
- **端口**: 4001
- **地址**: http://localhost:4001
- **MASTER_KEY**: `sk-1234`
- **配置文件**: `proxy_server_config.yaml`
- **状态**: ✅ 运行中

### 前端 UI (已运行)
- **端口**: 3000
- **地址**: http://localhost:3000
- **后端连接**: http://localhost:4001 (已配置)
- **热重载**: ✅ 已启用
- **状态**: ✅ 运行中

---

## 🚀 快速开始

### 1. 访问 UI
打开浏览器访问：**http://localhost:3000**

### 2. 登录认证

#### 方式一：使用 MASTER_KEY
- **API Key**: `sk-1234`

#### 方式二：使用已有的测试 Key
后端已有一个测试 key（从 `/user/info` 接口可见）：
- **Alias**: `t1`
- **User ID**: `default_user_id`

### 3. 测试后端连接

```bash
# 测试服务存活
curl http://localhost:4001/health/liveliness

# 测试认证（使用 MASTER_KEY）
curl -H "Authorization: Bearer sk-1234" http://localhost:4001/health

# 获取用户信息
curl -H "Authorization: Bearer sk-1234" http://localhost:4001/user/info
```

---

## 📁 项目结构

```
litellm-dashboard/
├── src/
│   ├── app/              # Next.js 页面和路由
│   │   ├── layout.tsx    # 根布局
│   │   ├── page.tsx      # 首页
│   │   └── ...
│   ├── components/       # React 组件
│   │   ├── ui/          # 基础 UI 组件（按钮、卡片等）
│   │   └── ...          # 业务组件（表格、表单等）
│   ├── hooks/           # 自定义 React Hooks
│   ├── utils/           # 工具函数
│   ├── contexts/        # React Context
│   └── types.ts         # TypeScript 类型
├── public/             # 静态资源
├── .env.development    # 开发环境变量
└── package.json        # 依赖和脚本
```

---

## 🎨 开始美化 UI

### 1. 找到要修改的组件
```bash
# 查找所有组件
ls src/components/

# 查找基础 UI 组件
ls src/components/ui/

# 查找页面
ls src/app/
```

### 2. 实时预览工作流

1. **在编辑器中打开文件** (如 VS Code)
2. **修改代码** (组件、样式等)
3. **保存文件** (Cmd+S / Ctrl+S)
4. **浏览器自动刷新** - 立即看到更改！

### 3. 使用的技术栈

#### UI 库
- **Tremor React**: 主要 UI 组件库（图表、卡片、表格）
- **Ant Design**: 补充组件（模态框、表单等）
- **Headless UI**: 无样式组件（下拉菜单、对话框）
- **Lucide React**: 图标库

#### 样式
- **Tailwind CSS**: 实用优先的 CSS 框架
- **自定义颜色**: 见 `ui_colors.json`

#### 示例：修改按钮样式
```tsx
// 使用 Tailwind 类
<button className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
  点击我
</button>

// 使用 Tremor 组件
import { Button } from '@tremor/react';
<Button variant="primary" size="lg">点击我</Button>
```

### 4. 常用 Tailwind 类名

```css
/* 颜色 */
bg-blue-500        /* 蓝色背景 */
text-white         /* 白色文字 */
border-gray-300    /* 灰色边框 */

/* 间距 */
p-4                /* padding: 1rem */
m-2                /* margin: 0.5rem */
px-6 py-3          /* padding 左右和上下 */

/* 布局 */
flex               /* display: flex */
grid               /* display: grid */
items-center       /* align-items: center */
justify-between    /* justify-content: space-between */

/* 响应式 */
sm:text-lg         /* 小屏幕及以上 */
md:flex            /* 中等屏幕及以上 */
lg:grid-cols-3     /* 大屏幕及以上 */

/* 阴影和圆角 */
shadow-lg          /* 大阴影 */
rounded-md         /* 中等圆角 */
hover:shadow-xl    /* 悬停时大阴影 */
```

---

## 🔧 开发工具

### 推荐的 VS Code 扩展
- **Tailwind CSS IntelliSense**: 自动补全 Tailwind 类名
- **ES7+ React Snippets**: React 代码片段
- **Prettier**: 代码格式化
- **ESLint**: 代码检查

### 浏览器开发工具
- **React Developer Tools**: 检查 React 组件树
- **Tailwind CSS DevTools**: 实时调整 Tailwind 类

---

## 📝 开发命令

```bash
# 启动开发服务器（已运行）
npm run dev

# 代码格式化
npm run format

# 代码检查
npm run lint

# 运行测试
npm run test

# 构建生产版本
npm run build
```

---

## 🐛 调试技巧

### 1. 检查网络请求
打开浏览器开发者工具 → Network 标签，查看 API 请求

### 2. React 组件调试
使用 React DevTools 查看组件状态和 props

### 3. 查看后端日志
后端服务正在另一个终端运行，查看那里的日志输出

### 4. 清除缓存
如果遇到奇怪的问题：
```bash
# 删除 .next 缓存目录
rm -rf .next

# 重启开发服务器
npm run dev
```

---

## 🎯 美化建议

### 1. 颜色主题
参考 `ui_colors.json` 中的颜色定义，保持一致的颜色方案

### 2. 组件库优先
优先使用 Tremor React 组件，保持设计一致性

### 3. 响应式设计
使用 Tailwind 的响应式类名（sm:, md:, lg:）确保移动端体验

### 4. 性能优化
- 使用 Next.js 的 Image 组件加载图片
- 避免不必要的重新渲染
- 使用 React Query 进行数据缓存

---

## 📚 相关文档

- [Next.js 文档](https://nextjs.org/docs)
- [Tailwind CSS 文档](https://tailwindcss.com/docs)
- [Tremor React 文档](https://www.tremor.so/docs)
- [React Query 文档](https://tanstack.com/query/latest)
- [Lucide Icons](https://lucide.dev/icons/)

---

## 🆘 遇到问题？

### 端口被占用
如果端口 3000 被占用，Next.js 会自动使用下一个可用端口（如 3001、3002）

### UI 无法连接后端
检查 `.env.development` 文件中的 `NEXT_PUBLIC_BASE_URL` 是否正确设置为 `http://localhost:4001`

### 热重载不工作
尝试重启开发服务器或清除 `.next` 缓存目录

---

开始你的 UI 美化之旅吧！🎨✨
