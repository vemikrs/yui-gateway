# YuiGateway セットアップ手順

## 前提条件

- Python 3.10 以上
- Poetry（Python パッケージマネージャー）
- Azure OpenAI リソースへのアクセス
- Entra ID アプリ登録（クライアントクレデンシャル）

## セットアップ

### 1. 依存関係のインストール

```bash
# Poetry を使用する場合
poetry install

# または pip を使用する場合
pip install -r requirements.txt
```

### 2. 環境設定の選択肢

#### オプションA: 自動プロビジョニング（推奨）

全自動でAzureリソースのセットアップ、アプリ登録、RBAC付与、`.env`作成を実行：

```bash
# GUIログイン + 対話式選択（推奨）
python scripts/provision_env.py --login interactive --select

# CLIログイン済みの場合
python scripts/provision_env.py --login cli

# デバイスコードログイン
python scripts/provision_env.py --login devicecode
```

#### オプションB: 手動設定

組織ポリシーや権限上の理由で自動プロビジョニングが使えない場合：

```bash
# 簡易セットアップ（.envファイルのみ作成）
python scripts/setup_env.py
```

または手動で`.env`を作成：

```env
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
SCOPE=https://cognitiveservices.azure.com/.default
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
```

### 3. アプリケーションの起動

```bash
# スクリプトを使用（自動プロビジョニング対応）
bash scripts/start_local.sh
# .envが無い場合、自動でプロビジョニングを実行してから起動

# または直接起動
uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000

# VS Codeタスクでも実行可能
# コマンドパレット → "Tasks: Run Task" → "Start YuiGateway Server"
```

## 使用方法

### デプロイメント情報の確認

```bash
# 利用可能なモデルとバージョンを確認
python scripts/list_deployments.py
```

### ヘルスチェック

```bash
curl http://localhost:8000/health
```

### チャット補完リクエスト

```bash
# 新しいモデル（gpt-5-miniなど）の場合
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5-mini",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "max_completion_tokens": 100
  }'

# 従来のモデル（gpt-4など）の場合
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4-deployment",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 100
  }'
```

### OpenAI ライブラリから使用

```python
# 新しい openai ライブラリ (v1.x) - 推奨
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # 認証は Entra ID で行われるため任意の値
)

# 新しいモデルの場合
response = client.chat.completions.create(
    model="gpt-5-mini",  # 実際のデプロイメント名
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    max_completion_tokens=100
)

print(response.choices[0].message.content)

# 従来の openai ライブラリ (v0.x)
import openai

openai.api_base = "http://localhost:8000/v1"
openai.api_key = "dummy"

response = openai.ChatCompletion.create(
    model="gpt-4-deployment",  # 実際のデプロイメント名
    messages=[{"role": "user", "content": "Hello!"}],
    max_tokens=100
)

print(response.choices[0].message.content)
```

## トラブルシューティング

### トークン取得エラー

- `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` が正しいか確認
- Azure Portal でアプリ登録の権限設定を確認
- `SCOPE` が正しいか確認（通常は `https://cognitiveservices.azure.com/.default`）

### Azure OpenAI 接続エラー

- `AZURE_OPENAI_ENDPOINT` が正しいか確認
- Azure OpenAI リソースでデプロイメントが作成されているか確認
- リクエストの `model` フィールドがデプロイメント名と一致しているか確認

## 開発

### テストの実行

```bash
pytest tests/
```

### コードフォーマット

```bash
black gateway/
```

## 次のステップ

- ログ記録機能の追加
- ストリーミングレスポンスのサポート
- 複数モデルのルーティング機能
- メトリクス収集（Prometheus/OpenTelemetry）
