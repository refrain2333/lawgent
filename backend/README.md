# 后端服务 - 刑事法律服务助手

## 技术栈

- **框架**: FastAPI
- **向量检索**: Lawformer (768维向量)
- **知识图谱**: NetworkX + 自建KG
- **LLM集成**: DeepSeek
- **Agent框架**: LangChain
- **数据库**: 向量数据(pkl) + 知识图谱(pkl)
- **实时通信**: WebSocket

## 目录结构

```
backend/
├── app/
│   ├── api/            # API路由
│   │   └── v1/
│   ├── models/         # 数据模型
│   ├── schemas/        # 请求/响应模型
│   ├── services/       # 业务逻辑
│   │   └── agent/      # Agent核心模块
│   ├── core/           # 配置文件
│   ├── db/             # 数据加载
│   └── utils/          # 工具函数
├── data/               # 数据文件（链接原始数据）
└── tests/              # 测试文件
```

## 核心模块

### 1. 搜索服务 (Search Service)
- 5阶段智能搜索管道
- 向量检索 (Lawformer)
- BM25混合搜索
- 知识图谱增强

### 2. Agent服务 (Agent Service)
- 罪名识别工具
- 信息检索工具 (复用搜索服务)
- 信息收集工具
- 风险评估工具
- 多轮对话管理

### 3. LLM客户端
- DeepSeek API 集成
- 提示词模板管理

## 核心规范

### 代码规范
- 使用 type hints
- 数据库操作仅在 service 层
- 函数参数多行时闭合括号同缩进
- 数据库查询: `select() + exec()` 不用旧版 query
- HTTP 状态码用数字(400/401/404)
- Service 返回 Schema 不返回 Model
- `__init__.py` 仅在必要时创建(非必要不创建)

### 测试规范
- 测试文件结构按开发结构组织
- 测试文件命名: `test_*.py`
- 使用 pytest + TestClient
- 每个模块独立的测试文件
- 使用内存数据库(SQLite)进行测试
- 测试类按功能分组(如 TestRegister, TestLogin)

示例:
```
backend/app/tests/
├── api/
│   └── v1/
│       ├── test_auth.py      # 对应 api/v1/auth.py
│       └── test_users.py     # 对应 api/v1/users.py
```

### API 文档注释
- 路由必须有 `summary` 和简洁 docstring(1-2行)
- Schema 类必须有文档字符串
- Schema/Model 字段定义写成一行,保持紧凑
- 字段必须有 `description` 和 `examples`
- Router 必须指定 `tags`
- 避免空行,保持紧凑
- 不要在路由注释中重复 Schema 字段说明

示例:
```python
@router.post("/login", response_model=Token, summary="用户登录")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录接口(JSON格式),支持用户名或邮箱登录
    返回JWT令牌(有效期7天)
    """
    return user_service.login(db, login_data)

class UserCreate(UserBase):
    """用户注册请求模型"""
    username: str = Field(min_length=3, max_length=50, description="用户名,3-50个字符", examples=["zhangsan"])
    password: str = Field(min_length=6, description="密码,至少6个字符", examples=["password123"])

class User(BaseModel, table=True):
    """用户模型"""
    __tablename__ = "users"
    username: str = Field(..., min_length=3, max_length=50, unique=True, index=True, sa_column_kwargs={"comment": "用户名"})
    email: str = Field(..., max_length=100, unique=True, index=True, sa_column_kwargs={"comment": "邮箱"})
```

### 安全要点
- 密码加密存储(bcrypt)
- 敏感配置用环境变量
- API 认证保护(除登录注册)

### 性能要点
- 数据库查询用索引
- 列表接口必须分页
- 响应数据仅返回必要字段

### API 文档
- 路由必须有 `summary` 和简洁 docstring
- Schema 类必须有文档字符串
- 使用 Swagger UI 自动生成文档

### 安全要点
- 敏感配置用环境变量 (.env)
- API 认证保护
- 免责声明（法律咨询仅供參考）

## 数据说明

- 刑法条文: 446条 + 向量
- 刑事案例: 17,131个
- 知识图谱: 500+ 节点
