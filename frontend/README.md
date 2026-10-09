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
