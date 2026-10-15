# uSciTec BioAge AI

一个不依赖 DNA 甲基化的 AI 生物年龄与健康管理系统（MVP）。Sprint 1 交付确定性的 **Levine 2018 Clinical PhenoAge** 计算引擎、标准化检测数据模型、计算 API 和四个页面。

> ⚠️ **仅供研究和内部验证使用。** 系统不生成疾病诊断或治疗结论；所有年龄都来自确定性算法引擎，不调用大语言模型。

## 目录结构

```
.
├── backend/                     FastAPI + Python 3.12
│   ├── app/
│   │   ├── domain/              纯函数领域层（无 I/O）
│   │   │   ├── phenoage.py      Levine 2018 公式、常数、指纹
│   │   │   ├── biomarkers.py    9 项指标：模型单位、可接受单位、可接受范围、参考区间
│   │   │   ├── units.py         严格单位规范化与换算
│   │   │   └── validation.py    缺失 / 非法 / 范围 / CRP 检出限 / 日期校验
│   │   ├── services/            计算编排、审计
│   │   ├── api/v1/              bioage, patients, audit_logs 路由
│   │   ├── core/                配置（环境变量）、角色权限、日志脱敏
│   │   ├── db/                  SQLAlchemy 模型与会话
│   │   └── schemas/             Pydantic 请求 / 响应模型
│   ├── alembic/                 数据库迁移
│   ├── scripts/seed_synthetic.py  合成演示数据
│   └── tests/                   算法 / 单位 / 边界 / 接口测试 + 独立参考实现
├── frontend/                    Next.js 15 + TypeScript
│   ├── app/
│   │   ├── patients/new/                      新建患者
│   │   ├── patients/[id]/labs/new/            手工录入指标
│   │   ├── patients/[id]/results/[resultId]/  计算结果
│   │   ├── patients/[id]/                     指标概览
│   │   └── api/backend/[...path]/             同源代理（令牌只在服务端）
│   ├── lib/                     类型、格式化、客户端校验（含测试）
│   └── e2e/                     Playwright 端到端（合成数据）
├── docs/                        PRODUCT_SPEC / CLINICAL_MODEL / API_SPEC / VALIDATION_PLAN / demo 截图
├── docker-compose.yml
└── .env.example
```

## 快速开始（Docker）

```bash
cp .env.example .env        # 把所有 REPLACE / change-me 值改成随机值
docker compose up --build
# 前端 http://localhost:3000   API 文档 http://localhost:8000/api/docs
API_TOKEN=<clinician token> docker compose exec backend python scripts/seed_synthetic.py
```

## 本地开发

```bash
# 后端
cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://bioage:bioage@localhost:5432/bioage AUTH_TOKENS='[...]'
.venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --reload --no-access-log
.venv/bin/pytest                    # 默认使用 SQLite；设置 DATABASE_URL 即可改用 PostgreSQL
.venv/bin/ruff check . && .venv/bin/mypy app

# 前端
cd frontend && npm ci
BACKEND_URL=http://localhost:8000 BACKEND_API_TOKEN=<token> npm run dev
npm test && npm run typecheck
npm run e2e                         # 需要前后端都已启动
```

## Sprint 1 实施计划与状态

| # | 任务 | 状态 |
|---|---|---|
| 1 | 前后端工程、数据库、Docker 开发环境 | ✅（compose 配置已校验；镜像未在本环境构建） |
| 2 | Levine PhenoAge 2018（9 项指标 + 实际年龄） | ✅ `backend/app/domain/phenoage.py` |
| 3 | 标准化检测数据模型（单位、日期、来源、参考范围、质量状态） | ✅ `lab_results` |
| 4 | 严格单位换算、范围校验、缺失处理、CRP 对数 / 零值 / 检出限 | ✅ |
| 5 | `POST /api/v1/bioage/phenoage` | ✅ |
| 6 | 新建患者 / 录入 / 结果 / 概览 四个页面 | ✅ |
| 7 | 算法单元测试、边界值测试、接口测试 | ✅ |
| 8 | 角色权限、审计日志、环境变量、日志不含患者数据 | ✅ |
| 9 | docs/*.md | ✅ |
| 10 | 不调用大语言模型 | ✅（有测试强制检查） |

详见 [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)、[docs/CLINICAL_MODEL.md](docs/CLINICAL_MODEL.md)、[docs/API_SPEC.md](docs/API_SPEC.md)、[docs/VALIDATION_PLAN.md](docs/VALIDATION_PLAN.md)。
