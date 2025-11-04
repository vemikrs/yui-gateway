# YuiGateway ローカル使用ガイド

YuiGateway は Azure OpenAI に Entra ID (Azure AD) 認証で安全に接続するローカルプロキシです。このガイドでは、ローカル環境でのセットアップから実際の使用方法まで詳しく説明します。

## 目次

1. [前提条件](#前提条件)
2. [セットアップ手順](#セットアップ手順)
3. [設定ファイルの準備](#設定ファイルの準備)
4. [アプリケーションの起動](#アプリケーションの起動)
5. [使用方法](#使用方法)
6. [テストの実行](#テストの実行)
7. [トラブルシューティング](#トラブルシューティング)
8. [開発とカスタマイズ](#開発とカスタマイズ)

---

## 前提条件

### 必要なソフトウェア

- **Python 3.10 以上**
  ```bash
  python --version  # Python 3.10.0 以上であることを確認
  ```

- **Poetry** (推奨) または **pip**
  ```bash
  # Poetry のインストール
  curl -sSL https://install.python-poetry.org | python3 -
  
  # または pip を使用
  pip install poetry
  ```

- **Git**
  ```bash
  git --version
  ```

### Azure 側の前提条件

1. **Azure OpenAI リソース**
   - Azure Portal で Azure OpenAI Service リソースが作成済み
   - 少なくとも 1 つのモデルがデプロイ済み（例: gpt-4, gpt-35-turbo）

2. **Entra ID アプリ登録**
   - Azure Portal の「App registrations」でアプリが登録済み
   - クライアント ID とクライアントシークレットが発行済み
   - 以下の権限が付与済み:
     - `Cognitive Services User` ロール (Azure OpenAI リソースに対して)

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
# リポジトリをクローン
git clone https://github.com/vemikrs/yui-gateway.git
cd yui-gateway
```

### 2. 依存パッケージのインストール

**Poetry を使用する場合 (推奨):**

```bash
# 依存関係をインストール
poetry install

# 仮想環境をアクティブ化
poetry shell
```

**pip を使用する場合:**

```bash
# 仮想環境を作成
python -m venv .venv

# 仮想環境をアクティブ化
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 依存関係をインストール
pip install fastapi uvicorn[standard] msal httpx pydantic-settings python-dotenv
```

### 3. 設定ファイルの準備

```bash
# テンプレートをコピー
cp .env.template .env
```

`.env` ファイルを編集して、Azure の認証情報を設定します:

```env
# Azure AD (Entra ID) 認証情報
TENANT_ID=your-tenant-id-here
CLIENT_ID=your-client-id-here
CLIENT_SECRET=your-client-secret-here

# スコープ (通常はこのまま)
SCOPE=https://cognitiveservices.azure.com/.default

# Azure OpenAI エンドポイント
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
```

#### 認証情報の取得方法

**TENANT_ID の取得:**
1. Azure Portal にログイン
2. 「Azure Active Directory」（または「Microsoft Entra ID」）を開く
3. 「Overview」から「Tenant ID」をコピー

**CLIENT_ID と CLIENT_SECRET の取得:**
1. Azure Portal で「App registrations」を開く
2. 登録済みのアプリケーションを選択
3. 「Overview」から「Application (client) ID」をコピー → `CLIENT_ID`
4. 「Certificates & secrets」→「New client secret」でシークレットを作成
5. 作成されたシークレットの「Value」をコピー → `CLIENT_SECRET`
   - ⚠️ シークレットは作成時のみ表示されるので、必ずコピーしてください

**AZURE_OPENAI_ENDPOINT の取得:**
1. Azure Portal で Azure OpenAI リソースを開く
2. 「Keys and Endpoint」セクションから「Endpoint」をコピー
3. 例: `https://my-resource.openai.azure.com`

---

## アプリケーションの起動

### 方法 1: スクリプトを使用

```bash
bash scripts/start_local.sh
```

### 方法 2: 直接起動

```bash
# Poetry を使用している場合
poetry run uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000

# pip を使用している場合
uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000
```

起動成功時のログ:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## 使用方法

### 1. ヘルスチェック

アプリケーションが正常に起動しているか確認:

```bash
curl http://localhost:8000/health
```

**期待されるレスポンス:**
```json
{
  "status": "healthy"
}
```

### 2. サービス情報の取得

```bash
curl http://localhost:8000/
```

**期待されるレスポンス:**
```json
{
  "service": "YuiGateway",
  "version": "0.1.0",
  "description": "Entra ID-based local proxy to Azure OpenAI",
  "endpoints": ["/v1/chat/completions"]
}
```

### 3. チャット補完リクエスト

#### curl を使用

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "system", "content": "あなたは親切なアシスタントです。"},
      {"role": "user", "content": "こんにちは！"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

**注意:** `model` フィールドには Azure OpenAI の**デプロイメント名**を指定してください。

**レスポンス例:**
```json
{
  "id": "chatcmpl-8xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "こんにちは！何かお手伝いできることはありますか？"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 15,
    "total_tokens": 40
  }
}
```

#### Python から使用

##### 標準の openai ライブラリ (v0.x)

```python
import openai

# YuiGateway をベース URL として設定
openai.api_base = "http://localhost:8000/v1"
openai.api_key = "dummy"  # 認証は Entra ID で行われるため任意の値でOK

# チャット補完リクエスト
response = openai.ChatCompletion.create(
    model="gpt-4",  # Azure OpenAI のデプロイメント名
    messages=[
        {"role": "system", "content": "あなたは親切なアシスタントです。"},
        {"role": "user", "content": "Pythonについて教えてください。"}
    ],
    temperature=0.7,
    max_tokens=200
)

print(response.choices[0].message.content)
```

##### 新しい openai ライブラリ (v1.x)

```python
from openai import OpenAI

# クライアントを初期化
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # 任意の値でOK
)

# チャット補完リクエスト
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "あなたは親切なアシスタントです。"},
        {"role": "user", "content": "Pythonについて教えてください。"}
    ],
    temperature=0.7,
    max_tokens=200
)

print(response.choices[0].message.content)
```

##### httpx を使用（低レベルAPI）

```python
import httpx
import asyncio

async def chat():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "こんにちは！"}
                ]
            }
        )
        return response.json()

result = asyncio.run(chat())
print(result["choices"][0]["message"]["content"])
```

### 4. パラメータ説明

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|----------|---|-----|-----------|-----|
| `model` | string | ✅ | - | Azure OpenAI のデプロイメント名 |
| `messages` | array | ✅ | - | メッセージ配列（role と content を含む） |
| `temperature` | float | ❌ | 1.0 | ランダム性の制御 (0.0-2.0) |
| `max_tokens` | integer | ❌ | null | 生成する最大トークン数 |
| `top_p` | float | ❌ | 1.0 | 核サンプリングのしきい値 (0.0-1.0) |
| `n` | integer | ❌ | 1 | 生成する補完数 |
| `stream` | boolean | ❌ | false | ストリーミングレスポンス (未実装) |
| `presence_penalty` | float | ❌ | 0.0 | 新しいトピックの促進 (-2.0-2.0) |
| `frequency_penalty` | float | ❌ | 0.0 | 繰り返しの抑制 (-2.0-2.0) |

---

## テストの実行

### すべてのテストを実行

```bash
# Poetry を使用
poetry run pytest

# または pip を使用
pytest
```

### カバレッジ付きでテストを実行

```bash
poetry run pytest --cov=gateway --cov-report=html
```

カバレッジレポートは `htmlcov/index.html` に生成されます。

### 特定のテストファイルを実行

```bash
pytest tests/test_routes.py
pytest tests/test_auth.py
pytest tests/test_azure_proxy.py
pytest tests/test_settings.py
```

### 詳細な出力で実行

```bash
pytest -v -s
```

### テストマーカーを使用

```bash
# ユニットテストのみ実行
pytest -m unit

# スローテストをスキップ
pytest -m "not slow"
```

---

## トラブルシューティング

### 問題 1: トークン取得エラー

**エラー例:**
```
ERROR: Token acquisition failed: AADSTS700016: Application with identifier 'xxx' was not found
```

**解決方法:**
1. `TENANT_ID` が正しいか確認
2. `CLIENT_ID` が正しいか確認
3. Azure Portal でアプリが正しく登録されているか確認
4. アプリが削除されていないか確認

---

### 問題 2: 権限エラー

**エラー例:**
```
ERROR: 401 Unauthorized
```

**解決方法:**
1. Azure Portal で Azure OpenAI リソースを開く
2. 「Access control (IAM)」→「Add role assignment」
3. 「Cognitive Services User」ロールを選択
4. 登録済みのアプリケーションを追加

---

### 問題 3: エンドポイント接続エラー

**エラー例:**
```
ERROR: Failed to connect to Azure OpenAI endpoint
```

**解決方法:**
1. `AZURE_OPENAI_ENDPOINT` が正しいか確認（末尾にスラッシュ不要）
2. エンドポイントが `https://` で始まるか確認
3. ネットワーク接続を確認
4. ファイアウォールやプロキシ設定を確認

---

### 問題 4: デプロイメントが見つからない

**エラー例:**
```
ERROR: 404 Not Found - The API deployment for this resource does not exist
```

**解決方法:**
1. Azure Portal で Azure OpenAI リソースを開く
2. 「Model deployments」でデプロイ済みモデルを確認
3. リクエストの `model` フィールドにデプロイメント名を正しく指定
   - ❌ `"model": "gpt-4"` (モデル名)
   - ✅ `"model": "my-gpt4-deployment"` (デプロイメント名)

---

### 問題 5: .env ファイルが読み込まれない

**解決方法:**
1. `.env` ファイルがプロジェクトルートに存在するか確認
   ```bash
   ls -la .env
   ```
2. ファイル名が正確に `.env` であることを確認（`.env.template` ではない）
3. 環境変数を直接設定して試す:
   ```bash
   export TENANT_ID="your-tenant-id"
   export CLIENT_ID="your-client-id"
   export CLIENT_SECRET="your-client-secret"
   export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
   ```

---

### 問題 6: ポート 8000 が使用中

**エラー例:**
```
ERROR: [Errno 48] Address already in use
```

**解決方法:**
1. 別のポートを使用:
   ```bash
   uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8001
   ```
2. または既存のプロセスを停止:
   ```bash
   # ポートを使用しているプロセスを特定
   lsof -i :8000
   # プロセスを停止
   kill -9 <PID>
   ```

---

## 開発とカスタマイズ

### コードフォーマット

```bash
# Black でフォーマット
poetry run black gateway/ tests/

# Ruff でリント
poetry run ruff check gateway/ tests/
```

### ログレベルの変更

`.env` ファイルで設定:
```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

または環境変数で設定:
```bash
LOG_LEVEL=DEBUG uvicorn gateway.routes:app --reload
```

### タイムアウトの変更

`gateway/azure_proxy.py` の `AzureOpenAIProxy.__init__` でタイムアウトを調整:
```python
self.client = httpx.AsyncClient(timeout=180.0)  # 180秒に変更
```

### API バージョンの変更

`gateway/azure_proxy.py` の `chat_completion` メソッドで API バージョンを変更:
```python
params = {
    "api-version": "2024-08-01-preview"  # 新しいバージョンに変更
}
```

### カスタムエンドポイントの追加

`gateway/routes.py` に新しいエンドポイントを追加:
```python
@app.get("/v1/models")
async def list_models():
    """利用可能なモデルのリストを返す"""
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4", "object": "model"},
            {"id": "gpt-35-turbo", "object": "model"}
        ]
    }
```

---

## セキュリティのベストプラクティス

1. **シークレットの管理**
   - `.env` ファイルを Git にコミットしない（`.gitignore` に含まれています）
   - 本番環境では環境変数または Azure Key Vault を使用

2. **ネットワークセキュリティ**
   - 本番環境では `--host 127.0.0.1` でローカルホストのみからアクセス可能にする
   - リバースプロキシ（nginx など）を使用して HTTPS を有効化

3. **トークンキャッシュ**
   - MSAL はトークンをメモリ内でキャッシュ
   - ファイルシステムへの書き込みは行わない

4. **ログ**
   - トークンや認証情報をログに出力しない
   - `LOG_LEVEL=INFO` を本番環境で使用（DEBUG は避ける）

---

## よくある質問 (FAQ)

### Q1: ストリーミングレスポンスはサポートされていますか？

A: 現在は未実装です。将来のバージョンで追加予定です。

### Q2: 複数の Azure OpenAI リソースに接続できますか？

A: 現在は単一のエンドポイントのみをサポートしています。複数のリソースを使用するには、複数の YuiGateway インスタンスを異なるポートで起動してください。

### Q3: API キーベースの認証もサポートしていますか？

A: いいえ、YuiGateway は Entra ID 認証のみをサポートしています。これは API キーを露出しないという設計思想に基づいています。

### Q4: Docker で実行できますか？

A: はい、`Dockerfile` が含まれています:
```bash
docker build -t yui-gateway .
docker run -p 8000:8000 --env-file .env yui-gateway
```

### Q5: OpenAI ライブラリ以外のクライアントでも使用できますか？

A: はい、OpenAI API 互換のエンドポイントを提供しているため、あらゆる HTTP クライアントで使用可能です。

---

## サポートとフィードバック

- **GitHub Issues**: https://github.com/vemikrs/yui-gateway/issues
- **ドキュメント**: `docs/` ディレクトリ
- **開発ガイド**: `gateway/README.dev.md`

---

## 次のステップ

- [アーキテクチャ概要](./overview.md) を読む
- [ユースケース](./use-cases.md) を確認する
- [開発ガイド](../gateway/README.dev.md) でカスタマイズ方法を学ぶ

---

**最終更新:** 2024-11-04
