# YuiGateway 応用ガイド

詳細設定、カスタマイズ、トラブルシューティングの完全ガイドです。

## 目次

1. [手動セットアップ](#手動セットアップ)
2. [外部設定ファイル](#外部設定ファイル)
3. [モデルパラメータの詳細](#モデルパラメータの詳細)
4. [プラグインシステム](#プラグインシステム)
5. [本番環境への展開](#本番環境への展開)
6. [詳細なトラブルシューティング](#詳細なトラブルシューティング)
7. [開発とカスタマイズ](#開発とカスタマイズ)

---

## 手動セットアップ

自動プロビジョニングが使用できない環境（企業ポリシーなど）での設定方法。

### 必要な権限

**Entra ID側:**
- アプリ登録を作成する権限（Application Administrator相当）
- または既存のアプリ登録情報を取得する権限

**Azure側:**
- Azure OpenAIリソースへのロール付与権限
- または`Cognitive Services User`ロールが付与済み

### 手順1: Entra IDアプリ登録

1. [Azure Portal](https://portal.azure.com) → **Microsoft Entra ID**
2. **App registrations** → **New registration**
3. アプリ名を入力（例: `YuiGateway-Manual`）
4. **Supported account types**: Single tenant
5. **Register**をクリック

**認証情報の取得:**
- **Application (client) ID**をコピー → `CLIENT_ID`
- **Directory (tenant) ID**をコピー → `TENANT_ID`

### 手順2: クライアントシークレット作成

1. 作成したアプリ → **Certificates & secrets**
2. **New client secret**
3. Description入力 → **Add**
4. **Value**をコピー → `CLIENT_SECRET`
   - ⚠️ この画面でしか表示されないため必ずコピー

### 手順3: RBAC設定

1. Azure Portal → **Azure OpenAI** リソース
2. **Access control (IAM)**
3. **Add** → **Add role assignment**
4. **Role**: `Cognitive Services User`
5. **Assign access to**: User, group, or service principal
6. **Select**: 手順1で作成したアプリ名を検索
7. **Save**

### 手順4: .env ファイル作成

プロジェクトルートに`.env`を作成:

```env
# Entra ID認証
TENANT_ID=<手順1でコピーしたTenant ID>
CLIENT_ID=<手順1でコピーしたClient ID>
CLIENT_SECRET=<手順2でコピーしたSecret Value>

# スコープ（通常は変更不要）
SCOPE=https://cognitiveservices.azure.com/.default

# Azure OpenAIエンドポイント
AZURE_OPENAI_ENDPOINT=https://<your-resource-name>.openai.azure.com

# オプション設定
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 手順5: 認証確認

```bash
python scripts/verify_auth.py
```

成功すると:
```
✓ Authentication successful
✓ Token acquired: eyJ0eXAiOiJKV1QiLCJhbGc...
✓ Ready to use YuiGateway
```

---

## 外部設定ファイル

YAML形式の設定ファイルで詳細な設定を管理できます。

### 設定ファイルの自動生成

初回起動時に`config.yaml`が自動生成されます:

```bash
bash scripts/start_local.sh
# → config.yaml が存在しない場合、テンプレートから自動生成
```

### config.yaml の構造

```yaml
core:
  environment: production
  log_level: INFO

  azure_openai:
    endpoint: ${AZURE_OPENAI_ENDPOINT}
    api_version: "2024-10-21"
    available_models:
      - gpt-5-mini
      - gpt-4o
      - gpt-35-turbo

  auth:
    tenant_id: ${TENANT_ID}
    client_id: ${CLIENT_ID}
    client_secret: ${CLIENT_SECRET}
    scope: https://cognitiveservices.azure.com/.default

plugins:
  # A5M2互換性プラグイン（必要な場合のみ有効化）
  a5m2_compatibility:
    enabled: false
    model_aliases:
      gpt-4: gpt-5-mini
      gpt-3.5-turbo: gpt-35-turbo
```

### 環境変数の展開

`${VAR_NAME}`形式で環境変数を参照:

```yaml
azure_openai:
  endpoint: ${AZURE_OPENAI_ENDPOINT}
  available_models:
    - ${PRIMARY_MODEL}    # 環境変数から読み込み
    - ${SECONDARY_MODEL}
    - gpt-35-turbo       # 固定値
```

### 設定の優先順位

1. コード内のデフォルト値（最低優先）
2. `config.yaml`
3. 環境変数（最高優先）

詳細: [EXTERNAL_CONFIG.md](EXTERNAL_CONFIG.md)

---

## モデルパラメータの詳細

### 新旧モデルの違い

**新しいモデル（gpt-5-mini, gpt-4o-2024など）:**
```json
{
  "model": "gpt-5-mini",
  "max_completion_tokens": 100,  // 新パラメータ
  "messages": [...]
}
```

**従来モデル（gpt-4, gpt-35-turboなど）:**
```json
{
  "model": "gpt-4",
  "max_tokens": 100,  // 旧パラメータ
  "messages": [...]
}
```

### 全パラメータ一覧

| パラメータ | 型 | デフォルト | 新モデル | 旧モデル | 説明 |
|----------|---|-----------|---------|---------|-----|
| `model` | string | - | ✅ | ✅ | デプロイメント名 |
| `messages` | array | - | ✅ | ✅ | メッセージ配列 |
| `max_completion_tokens` | int | null | ✅ | ❌ | 生成トークン数上限（新） |
| `max_tokens` | int | null | ❌ | ✅ | 生成トークン数上限（旧） |
| `temperature` | float | 1.0 | ✅ | ✅ | ランダム性 (0.0-2.0) |
| `top_p` | float | 1.0 | ✅ | ✅ | 核サンプリング |
| `n` | int | 1 | ✅ | ✅ | 生成数 |
| `stream` | bool | false | ✅ | ✅ | ストリーミング |
| `stop` | string/array | null | ✅ | ✅ | 停止シーケンス |
| `presence_penalty` | float | 0.0 | ✅ | ✅ | 新トピック促進 |
| `frequency_penalty` | float | 0.0 | ✅ | ✅ | 繰り返し抑制 |
| `logit_bias` | object | null | ✅ | ✅ | トークン確率調整 |
| `user` | string | null | ✅ | ✅ | ユーザーID |

### デプロイメント情報の確認

```bash
python scripts/list_deployments.py
```

出力例:
```
Available deployments:
  - gpt-5-mini
    Model: gpt-5-mini (version: 2025-08-07)
    → Use: max_completion_tokens

  - gpt-4-deployment
    Model: gpt-4 (version: 0613)
    → Use: max_tokens
```

---

## プラグインシステム

カスタム機能を追加するためのプラグイン機能。

### A5M2互換性プラグイン

A5M2（Azure OpenAI Studio Mockup Model 2）からの移行時に使用:

```yaml
plugins:
  a5m2_compatibility:
    enabled: true
    model_aliases:
      gpt-4: my-gpt4-deployment
      gpt-3.5-turbo: my-gpt35-deployment
```

**動作:**
- リクエストの`model`フィールドを変換
- A5M2が送信する`gpt-4` → 実際のデプロイメント名`my-gpt4-deployment`

### カスタムプラグインの作成

`gateway/plugins/`に新しいファイルを作成:

```python
# gateway/plugins/custom_plugin.py
from gateway.plugins.base import PluginBase

class CustomPlugin(PluginBase):
    def process_request(self, request: dict) -> dict:
        # リクエストを加工
        return request

    def process_response(self, response: dict) -> dict:
        # レスポンスを加工
        return response
```

`config.yaml`で有効化:

```yaml
plugins:
  custom_plugin:
    enabled: true
    priority: 100
    config:
      custom_setting: value
```

---

## 本番環境への展開

### Docker での実行

```bash
# イメージのビルド
docker build -t yui-gateway .

# コンテナの起動
docker run -d \
  --name yui-gateway \
  -p 8000:8000 \
  --env-file .env \
  yui-gateway
```

### systemd サービス化（Linux）

`/etc/systemd/system/yui-gateway.service`:

```ini
[Unit]
Description=YuiGateway - Azure OpenAI Proxy
After=network.target

[Service]
Type=simple
User=yuigateway
WorkingDirectory=/opt/yui-gateway
Environment="PATH=/opt/yui-gateway/.venv/bin"
EnvironmentFile=/opt/yui-gateway/.env
ExecStart=/opt/yui-gateway/.venv/bin/uvicorn gateway.routes:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

起動:
```bash
sudo systemctl daemon-reload
sudo systemctl enable yui-gateway
sudo systemctl start yui-gateway
```

### nginx リバースプロキシ

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # タイムアウト設定
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### セキュリティ強化

**1. ファイアウォール設定:**
```bash
# ローカルホストのみアクセス許可
sudo ufw allow from 127.0.0.1 to any port 8000
```

**2. 環境変数の保護:**
```bash
# .env のパーミッション設定
chmod 600 .env
chown yuigateway:yuigateway .env
```

**3. ログ管理:**
```yaml
# config.yaml
core:
  log_level: WARNING  # 本番環境ではWARNING以上
  log_file: /var/log/yui-gateway/app.log
```

---

## 詳細なトラブルシューティング

### 認証関連

#### エラー: `AADSTS700016: Application not found`

**原因:** アプリ登録が削除された、またはテナントIDが間違っている

**解決:**
```bash
# 環境変数を確認
echo $TENANT_ID
echo $CLIENT_ID

# Azure Portalで確認
# Entra ID → App registrations → 該当アプリが存在するか
```

#### エラー: `AADSTS7000215: Invalid client secret`

**原因:** シークレットの有効期限切れ、または値が間違っている

**解決:**
```bash
# 新しいシークレットを作成
# Azure Portal → App registrations → Certificates & secrets → New client secret

# .env を更新
CLIENT_SECRET=<新しいシークレット>
```

### ネットワーク関連

#### エラー: `Connection timeout`

**診断:**
```bash
# エンドポイントへの接続確認
curl -v https://your-resource.openai.azure.com

# DNS解決確認
nslookup your-resource.openai.azure.com

# ネットワーク経路確認
traceroute your-resource.openai.azure.com
```

**解決:**
- プロキシ設定を確認
- ファイアウォールルールを確認
- Azure OpenAIリソースのネットワーク設定を確認

### API関連

#### エラー: `404 DeploymentNotFound`

**診断:**
```bash
# 利用可能なデプロイメントを確認
python scripts/list_deployments.py

# リクエストのmodelフィールドを確認
# ❌ "model": "gpt-4"  # モデル名
# ✅ "model": "gpt-5-mini"  # デプロイメント名
```

#### エラー: `400 Bad Request - Unsupported parameter`

**診断:**
```bash
# モデルバージョンを確認
python scripts/list_deployments.py

# 新しいモデル → max_completion_tokens
# 古いモデル → max_tokens
```

### パフォーマンス

#### レスポンスが遅い

**診断:**
```bash
# タイムアウト設定を確認
grep -r "timeout" gateway/

# ログでレスポンス時間を確認
LOG_LEVEL=DEBUG bash scripts/start_local.sh
```

**解決:**
```python
# gateway/azure_proxy.py
self.client = httpx.AsyncClient(timeout=180.0)  # タイムアウト延長
```

---

## 開発とカスタマイズ

### 開発環境のセットアップ

```bash
# 開発依存関係を含めてインストール
poetry install --with dev

# プリコミットフックの設定
pre-commit install
```

### コードフォーマットとリント

```bash
# フォーマット
poetry run black gateway/ tests/

# リント
poetry run ruff check gateway/ tests/

# 自動修正
poetry run ruff check --fix gateway/ tests/
```

### テストの実行

```bash
# 全テスト
poetry run pytest

# カバレッジ付き
poetry run pytest --cov=gateway --cov-report=html

# 特定のテスト
poetry run pytest tests/test_routes.py -v

# マーカー指定
poetry run pytest -m "not slow"
```

### VS Code タスク

`.vscode/tasks.json`に定義済み:

- **Start YuiGateway Server**: サーバー起動
- **Run Tests**: テスト実行
- **Format Code (Black)**: コードフォーマット
- **Lint Code (Ruff)**: リント実行
- **Provision .env**: 自動プロビジョニング

### カスタムエンドポイントの追加

```python
# gateway/routes.py
@app.get("/v1/models")
async def list_models():
    """利用可能なモデルのリストを返す"""
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-5-mini",
                "object": "model",
                "owned_by": "azure"
            }
        ]
    }
```

### ミドルウェアの追加

```python
# gateway/middleware/rate_limit.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # レート制限ロジック
        response = await call_next(request)
        return response

# gateway/routes.py
app.add_middleware(RateLimitMiddleware)
```

---

## 関連ドキュメント

- **[QUICK_START.md](QUICK_START.md)** - 基本的なセットアップ
- **[EXTERNAL_CONFIG.md](EXTERNAL_CONFIG.md)** - 外部設定ファイルの詳細
- **[overview.md](overview.md)** - アーキテクチャ概要
- **[use-cases.md](use-cases.md)** - ユースケース集
- **[../gateway/README.dev.md](../gateway/README.dev.md)** - 開発者ガイド

---

**最終更新**: 2025-11-16
