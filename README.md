# AI新闻推送飞书工具

一个自动获取AI新闻并推送到飞书的Python工具，支持定时推送、多种消息格式和文章去重。

## ✨ 功能特性

- **多源支持**: 从多个RSS源获取AI新闻（Google AI Blog、OpenAI Blog、机器之心等）
- **智能去重**: 基于文章哈希值自动过滤重复内容
- **多种消息格式**: 支持纯文本、卡片、混合消息格式
- **定时推送**: 可通过GitHub Actions定时运行（如每天9点）
- **配置灵活**: 支持YAML配置文件、环境变量、命令行参数
- **错误处理**: 完善的错误处理和重试机制
- **数据统计**: 记录处理统计，支持按来源、分类、日期查看

## 📋 安装要求

- Python 3.8+
- 飞书企业账号和自建应用
- GitHub账号（用于定时推送）

## 🔧 安装步骤

### 1. 克隆项目
```bash
git clone https://github.com/yourusername/ai-news-feishu.git
cd ai-news-feishu
```

### 2. 创建虚拟环境
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置环境变量
复制环境变量模板并填写实际值：
```bash
cp .env.example .env
```

编辑`.env`文件：
```bash
# 飞书应用凭证（必填）
LARK_APP_ID=your_app_id_here
LARK_APP_SECRET=your_app_secret_here

# 飞书接收者（必填，群聊ID或用户open_id）
LARK_RECEIVER_ID=ou_xxx

# 运行模式
ENVIRONMENT=development  # development, testing, production
DRY_RUN=false           # 干跑模式，不实际发送消息
```

### 5. 配置RSS源
编辑`config/rss_sources.yaml`文件，可以添加或修改RSS源：
```yaml
sources:
  - name: "Google AI Blog"
    url: "https://ai.googleblog.com/feeds/posts/default"
    category: "AI"
    enabled: true
    max_articles: 10
    language: "en"
    description: "Google AI官方博客"

  - name: "OpenAI Blog"
    url: "https://openai.com/blog/rss/"
    category: "AI"
    enabled: true
    max_articles: 5
    language: "en"
    description: "OpenAI官方博客"
```

### 6. 飞书应用配置
1. 登录[飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取`App ID`和`App Secret`
4. 为应用添加以下权限：
   - `im:message`（发送消息）
   - `im:message:send_as_bot`（以机器人身份发送消息）
5. 发布应用
6. 将机器人添加到群聊或获取用户的`open_id`

## 🚀 使用方法

### 命令行工具

```bash
# 运行一次新闻推送
python src/main.py run

# 干跑模式（不实际发送消息）
python src/main.py run --dry-run

# 测试配置和连接
python src/main.py test-config

# 列出所有RSS源
python src/main.py list-sources

# 清理30天前的数据库记录
python src/main.py clean-db --days 30

# 显示最近7天的统计数据
python src/main.py stats

# 显示版本信息
python src/main.py version
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--dry-run` | 干跑模式，不实际发送消息 | false |
| `--limit` | 最大处理文章数量 | 50 |
| `--message-type` | 消息类型：text/card/mixed | mixed |
| `--days` | 清理或统计的天数 | 30/7 |

## ⚙️ 配置说明

### 配置文件结构
```
config/
├── config.yaml          # 主配置文件
└── rss_sources.yaml     # RSS源配置文件
```

### 环境变量优先级
1. 命令行参数
2. 环境变量
3. YAML配置文件
4. 默认值

### 飞书消息格式

1. **纯文本消息**: 简洁的文字摘要
2. **卡片消息**: 富文本卡片，支持按钮、链接、格式化
3. **混合消息**: 文本摘要 + 详细卡片（默认）

## 🤖 GitHub Actions 定时推送

### 1. 设置GitHub Secrets
在GitHub仓库的 Settings → Secrets and variables → Actions 中添加：
- `LARK_APP_ID`: 飞书应用ID
- `LARK_APP_SECRET`: 飞书应用密钥
- `LARK_RECEIVER_ID`: 飞书接收者ID

### 2. 手动触发推送
在GitHub仓库的 Actions 标签页，选择 "Manual News Push" 工作流，点击 "Run workflow"。

### 3. 定时推送（可选）
编辑 `.github/workflows/manual-push.yml` 中的 `schedule` 部分：
```yaml
schedule:
  - cron: '0 9 * * *'  # 每天北京时间9点运行
```

## 📊 数据库管理

项目使用SQLite数据库存储处理记录，位于`data/news.db`。

### 数据库表结构
- `processed_articles`: 已处理文章记录
- `rss_source_status`: RSS源状态记录

### 维护命令
```bash
# 查看数据库大小
ls -lh data/news.db

# 备份数据库
cp data/news.db data/news.db.backup

# 清理旧记录
python src/main.py clean-db --days 30
```

## 🧪 测试

运行测试：
```bash
pytest tests/
```

## 📁 项目结构

```
ai-news-feishu/
├── src/                    # 源代码
│   ├── config/            # 配置管理
│   ├── rss/               # RSS处理模块
│   ├── lark/              # 飞书API模块
│   ├── content_processor/ # 内容处理模块
│   ├── storage/           # 数据存储模块
│   ├── utils/             # 工具模块
│   └── main.py            # 主入口点
├── config/                # 配置文件
├── data/                  # 数据文件（数据库、日志）
├── tests/                 # 测试文件
├── .github/workflows/     # GitHub Actions工作流
├── requirements.txt       # Python依赖
├── .env.example           # 环境变量模板
├── .gitignore            # Git忽略文件
└── README.md             # 项目说明
```

## 🔍 故障排除

### 常见问题

1. **飞书消息发送失败**
   - 检查应用权限是否完整
   - 确认接收者ID是否正确
   - 检查应用是否已发布

2. **RSS源获取失败**
   - 检查网络连接
   - 验证RSS URL是否有效
   - 检查源网站是否有反爬虫机制

3. **数据库错误**
   - 检查`data/`目录是否有写入权限
   - 确认数据库文件没有损坏

4. **GitHub Actions运行失败**
   - 检查Secrets是否设置正确
   - 查看Actions日志获取详细错误信息

### 日志查看

日志默认输出到控制台，JSON格式：
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "message": "成功获取RSS源",
  "module": "fetcher",
  "function": "fetch_feed"
}
```

## 📄 许可证

MIT License

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📞 支持与反馈

- 提交 [GitHub Issues](https://github.com/yourusername/ai-news-feishu/issues)
- 查看 [Wiki](https://github.com/yourusername/ai-news-feishu/wiki)

---

**注意**: 本工具仅供学习和个人使用，请遵守相关网站的使用条款和飞书开放平台的规范。