# Frontend 环境说明

## 环境要求
- Node.js: 22.13.x
- npm: 10.x

## 安装与运行
```bash
# 安装依赖（严格按 lock 文件）
npm ci

# 启动开发服务器
npm run dev
```

## 注意事项
- 必须使用 `npm ci` 而非 `npm install`
- 项目使用 package-lock.json 锁定依赖版本
- 默认请求同源 `/api/v1`。如前后端分开部署，构建时设置 `VITE_API_BASE_URL=https://你的后端域名`（不含 `/api/v1`）；后端需允许前端域名的 CORS 请求。开发模式使用该地址作为 Vite 代理目标。
